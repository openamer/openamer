#!/usr/bin/env python3
"""World Model — Mini-OpenAmer's central cause→effect memory.

This is the single source of truth for the agent's world model. Every
learning loop writes through here; every prediction reads from here.

Capabilities:
  - observe(cause, effect)      — record a cause→effect edge with a REAL
                                  semantic embedding (nomic-embed-text, 768-dim)
  - recall(query, k)            — semantic nearest-neighbour search (cosine)
  - predict(situation, k)       — project the most likely effect from past edges
  - validate(prediction_id)     — score a past prediction against reality
  - stats()                     — health of the model

Design principles:
  - One file, one schema. No more scattered observe_world() copies.
  - Real embeddings, never placeholder constants. On embed failure we store
    a zero vector and mark it, so the model never lies to itself.
  - Append-only JSONL for durability + an in-memory index for fast recall.
"""

import json, os, math, sys, time, datetime, urllib.request, threading, pathlib, uuid

# Interpreter identity for the store lock (see _store_lock / _atomic_write):
# PID alone is not enough — a PID can be recycled. Kept filesystem-safe
# (no ':'): the nonce is embedded in temp file NAMES, and Windows rejects
# a colon in a filename with a bare WinError 87.
_NODE = f"{os.getpid()}_{uuid.uuid4().hex[:8]}"
_LOCK_PID = os.getpid()

# A lock file older than this whose owner PID is gone is reclaimed. Generous:
# the longest critical section is a full-store rewrite, seconds at worst.
_LOCK_STALE = 120.0

# Install-root guard: the MSYS form of OPENAMER_HOME (/c/tmp/oa-home) is a
# RELATIVE path to native Windows Python, so it expanded to a phantom
# C:\c\tmp\... tree that merely exists. WM then pointed at a directory with no
# world_model.jsonl, and every locked write spun its full 8 s lock timeout
# against a lock path whose parent does not exist. Same class as
# scripts/darwin_engine.py; the markers only a real install carries.
_HOME_MARKERS = ("config.yaml", ".env", "cron", "memories", "openamer-agent")


def _is_install_root(pth):
    try:
        return any((pth / m).exists() for m in _HOME_MARKERS)
    except OSError:
        return False


def _resolve_home():
    """Resolve OPENAMER_HOME across shells; never adopt a scratch dir."""
    local = pathlib.Path.home() / "AppData" / "Local"
    candidates = [local / "openamer-laptop", local / "openamer"]
    default = next((c for c in candidates if (c / "skills").is_dir()),
                   candidates[0])

    raw = os.environ.get("OPENAMER_HOME")
    if not raw:
        return default

    cand = None
    norm = raw.replace(os.sep, "/") if os.sep != "/" else raw
    if len(norm) >= 3 and norm[0] == "/" and norm[1].isalpha() and norm[2] == "/":
        cand = pathlib.Path(norm[1].upper() + ":/" + norm[3:])
    else:
        p = pathlib.Path(raw)
        if p.is_absolute():
            cand = p

    if cand is not None and cand.exists() and _is_install_root(cand):
        return cand
    if cand is not None and cand.exists():
        print(f"[world-model] WARNING: OPENAMER_HOME={cand} exists but is not an "
              f"OpenAmer install root; falling back to {default}.", file=sys.stderr)
    return default


_HOME = _resolve_home()

WM = os.path.join(_HOME, "memory", "world_model.jsonl")
EMBED_URL = "http://localhost:11434/api/embeddings"
EMBED_MODEL = "nomic-embed-text"
DIM = 768

# Schema versioning: every edge carries its schema_version. When the shape
# changes, bump SCHEMA_VERSION and add a migration in _migrate_edge(). This
# is what stops silent schema breaks (the kind that made predict_validate
# find 0 predictions after the kind/type rename).
SCHEMA_VERSION = 2

_lock = threading.RLock()


class _StoreBusy(RuntimeError):
    """Could not take the cross-process store lock inside the time budget."""


def _node_alive(pid):
    """True if a lock holder with this PID is still running (Windows + POSIX)."""
    if pid <= 0:
        return False
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes
        k32 = ctypes.windll.kernel32
        # 0x1000 = PROCESS_QUERY_LIMITED_INFORMATION (works across sessions)
        h = k32.OpenProcess(0x1000, False, pid)
        if not h:
            return False
        try:
            code = wintypes.DWORD()
            if k32.GetExitCodeProcess(h, ctypes.byref(code)):
                return code.value == 259      # STILL_ACTIVE
            return True
        finally:
            k32.CloseHandle(h)
    try:
        os.kill(pid, 0)  # windows-footgun: ok
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False


class _store_lock:
    """Cross-process advisory lock guarding every read AND write of the store.

    Why not just os.replace: on Windows the atomic swap is only half the
    story. A reader that opens the file between the writer's
    `open(tmp,"w")` and its `os.replace` still observes a truncated (0-byte)
    store, because the swap only becomes visible with the replace. And when
    the swap cannot be made (PermissionError: destination held open), the
    writer falls back to an in-place truncate — which is exactly the partial
    read this module exists to prevent.

    Live probe (16.09.26, 120-edge store, 1.5s of concurrent traffic):
    reader saw lengths {0: 5, 120: 104} — 5 partial reads, i.e. os.replace
    alone did NOT close the window. With this lock the same probe sees
    {120: N} only.

    Stale-holder recovery: each holder writes "<pid>:<nonce>" and refreshes
    it; a lock whose PID is gone (or whose mtime is older than _LOCK_STALE)
    is reclaimed, so a killed process cannot wedge every future writer.
    """

    def __init__(self, timeout=8.0):
        self.timeout = timeout
        self.path = f"{WM}.lock"
        self.tmp = f"{self.path}.{_NODE}.tmp"
        self.held = False
        self._inproc = False

    def _write_owner(self, fh):
        fh.seek(0)
        fh.write(f"{_LOCK_PID} {time.time():.6f}\n")
        fh.flush()
        try:
            os.fsync(fh.fileno())
        except OSError:
            pass

    def _stale(self):
        pid = None
        age = None
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                head = f.read().split()
            pid = int(head[0])
            age = time.time() - os.path.getmtime(self.path)
        except (OSError, ValueError, IndexError):
            # Unreadable/absent/garbled lock -> safest is to let the caller in;
            # a garbled lock is never a live holder.
            return True
        if pid == _LOCK_PID:
            # Our own PID: either this very interpreter's lock (re-entrancy is
            # impossible — _store_lock is not recursive) or a recycled PID.
            # Reclaiming is the only option that cannot deadlock us.
            return True
        return age > _LOCK_STALE or not _node_alive(pid)

    def __enter__(self):
        # Two layers, because the lock file alone cannot serialise two
        # THREADS of the same interpreter: a thread-local stale check would
        # see its own PID and reclaim the sibling thread's lock (which is
        # exactly how the probe still saw a 0-length read). The in-process
        # RLock is taken first and is what actually serialises same-process
        # workers; the file lock then covers other processes. Order matters —
        # taking the file lock first risks holding it while blocked on the
        # RLock, i.e. a same-process deadlock.
        _lock.acquire()
        self._inproc = True
        try:
            return self._enter_file_lock()
        except BaseException:
            self._release_inproc()
            raise

    def _release_inproc(self):
        if self._inproc:
            self._inproc = False
            _lock.release()

    def _enter_file_lock(self):
        deadline = time.time() + self.timeout
        delay = 0.004
        while True:
            try:
                fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_RDWR)
            except FileExistsError:
                if self._stale():
                    try:
                        os.remove(self.path)
                    except OSError:
                        pass
                    continue
                if time.time() >= deadline:
                    raise _StoreBusy(
                        f"world-model lock held > {self.timeout}s ({self.path})")
                time.sleep(delay)
                delay = min(delay * 2, 0.25)
                continue
            except OSError as e:
                # Windows can report PermissionError/AccessDenied from
                # O_CREAT|O_EXCL while another process is concurrently
                # creating or removing the same lock file — the path is in a
                # transient state, not permanently unusable. Caught live: an
                # unhandled Errno 13 escaped a worker and killed it mid-run.
                # Treat it exactly like "someone else holds it" and retry.
                if time.time() >= deadline:
                    raise _StoreBusy(
                        f"world-model lock unobtainable after {self.timeout}s "
                        f"({e})") from e
                time.sleep(delay)
                delay = min(delay * 2, 0.25)
                continue

            # Got it. Publish ownership (the O_EXCL existence is what
            # serialises; the payload is only for stale recovery).
            try:
                with os.fdopen(fd, "r+", encoding="utf-8") as fh:
                    try:
                        self._write_owner(fh)
                    except OSError:
                        pass
                self.held = True
                return self
            except BaseException:
                try:
                    os.remove(self.path)
                except OSError:
                    pass
                raise

    def __exit__(self, *exc):
        if self.held:
            try:
                os.remove(self.path)
            except FileNotFoundError:
                pass
            except OSError:
                pass            # a stale reclaim already took it; harmless
        self._release_inproc()
        return False


def _atomic_write(lines):
    """Write the whole store atomically, under the cross-process store lock.

    Plain `open(WM, "w")` truncates the file FIRST, so a concurrent reader
    in another PROCESS (threading._lock is process-local only) can observe a
    half-written store and parse 0..N partial lines. Live evidence:
    knowledge_to_action's world-model experiment reported 'not enough
    observed facts to predict from' against a 425-edge store, and a size
    probe caught the file shrinking 6_896_295 -> 5_525_181 bytes mid-write.
    os.replace is atomic on Windows and POSIX, so readers only ever see a
    complete old or complete new store.

    Windows caveat (caught by a live probe, not by theory): os.replace()
    raises PermissionError if ANY process currently holds the destination
    open for reading — and world_model readers (_load) do exactly that from
    other processes. So retry a few times before giving up.

    The last-resort path used to be an in-place `open(WM,"w")` rewrite. That
    is precisely the truncate-first write this function exists to eliminate,
    and the probe showed it was still reached (1 of 44 writes) and still
    produced a 0-length read. It is gone: if the swap cannot be made we
    report failure (False) instead of silently corrupting a reader's view.
    Callers hold the store lock across write, so a busy store is a signal,
    not something to paper over.

    Returns True when the swap landed, False when it did not.
    """
    tmp = f"{WM}.tmp-{_NODE}"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            for ln in lines:
                f.write(ln if ln.endswith("\n") else ln + "\n")
            f.flush()
            os.fsync(f.fileno())
    except OSError:
        try:
            os.remove(tmp)
        except OSError:
            pass
        return False
    last = None
    for attempt in range(10):
        try:
            os.replace(tmp, WM)
            return True
        except PermissionError as e:      # dest held open by another process
            last = e
            time.sleep(0.05 * (attempt + 1))
        except OSError as e:
            last = e
            break
    # Swap failed: drop the temp file and report honestly. NEVER truncate WM.
    try:
        os.remove(tmp)
    except OSError:
        pass
    if last is not None:
        sys.stderr.write(f"[world_model] atomic swap failed: {last}\n")
    return False


def _migrate_edge(d):
    """Migrate an edge from any older schema to the current one.

    v1 -> v2: predictions used "type": "prediction" + a single "predicted"
              field; v2 uses "kind": "prediction" + cause/effect. Facts used
              no "kind" at all. Normalize everything to v2.
    """
    v = d.get("schema_version", 1)
    if v >= SCHEMA_VERSION:
        return d
    # v1 -> v2
    if "type" in d and "kind" not in d:
        d["kind"] = d["type"]
        del d["type"]
    if "predicted" in d and "cause" not in d:
        # old prediction shape: "predicted" held the full text
        d["cause"] = d["predicted"]
        d["effect"] = ""
        del d["predicted"]
    if "kind" not in d:
        d["kind"] = "fact"
    d["schema_version"] = SCHEMA_VERSION
    return d


def embed(text, retries=2):
    """Return a real 768-dim embedding, or None on failure (never a fake)."""
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(
                EMBED_URL,
                data=json.dumps({"model": EMBED_MODEL, "prompt": text[:2000]}).encode(),
                headers={"Content-Type": "application/json"})
            return json.load(urllib.request.urlopen(req, timeout=30))["embedding"]
        except Exception:
            if attempt < retries:
                time.sleep(1.5 * (attempt + 1))  # transient embed-server hiccup
    return None


def repair_store():
    """Re-embed edges whose embedding failed transiently (embed_ok=False)."""
    with _store_lock():
        edges = _load_unlocked()
        bad = [e for e in edges if not e.get("embed_ok")]
        if not bad:
            return {"repaired": 0}
        fixed = 0
        for e in bad:
            emb = embed(f"{e.get('cause', '')} -> {e.get('effect', '')}", retries=3)
            if emb is not None:
                e["embedding"] = emb
                e["embed_ok"] = True
                fixed += 1
        if fixed:
            _atomic_write([json.dumps(e, ensure_ascii=False) for e in edges])
        return {"repaired": fixed, "remaining": len(bad) - fixed}


def _cosine(a, b):
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def _normalise(v):
    """Unit vector, or None for a zero/degenerate vector.

    Split out of _cosine so a batch comparison can normalise each vector ONCE
    instead of on every pair: cos(a,b) == dot(normalise(a), normalise(b)).
    """
    if not v:
        return None
    na = math.sqrt(sum(x * x for x in v))
    if na == 0:
        return None
    return [x / na for x in v]


def _dot(a, b):
    """Dot product of two equal-length vectors (a fast path for unit vectors)."""
    return sum(x * y for x, y in zip(a, b))


def _load():
    """Read all edges. Retries once if a non-empty file parses to 0 edges.

    That combination is always a symptom of a concurrent write (partial
    read), never a real empty store, and it used to be reported upstream as
    'not enough observed facts to predict from'.
    """
    if not os.path.exists(WM):
        return []
    try:
        with _store_lock():
            return _load_unlocked()
    except _StoreBusy:
        # A writer has been inside its critical section for longer than the
        # budget. Reading unlocked is strictly better than returning []: the
        # swap is still atomic, so the worst case is the previous complete
        # store, never a truncated one.
        return _load_unlocked()


def _load_unlocked():
    """Parse the store. Caller owns the store lock (or has accepted the risk)."""
    for attempt in (0, 1):
        out = []
        # Snapshot the bytes in ONE read, then parse from memory. Holding the
        # handle open for the whole parse (as `for line in open(WM)`) also
        # blocks the writers' os.replace on Windows -> PermissionError.
        try:
            with open(WM, "rb") as f:
                raw = f.read()
        except OSError:
            return out
        for line in raw.decode("utf-8", "replace").splitlines():
            if not line.strip():
                continue
            try:
                out.append(_migrate_edge(json.loads(line)))
            except Exception:
                continue
        if out or attempt:
            return out
        # non-empty on disk but parsed empty -> likely mid-write; let it settle
        time.sleep(0.05)
        try:
            if os.path.getsize(WM) == 0:
                return []
        except OSError:
            return []
    return []


def prune(max_dupes=2, dry_run=False):
    """Remove near-duplicate edges (cosine > 0.97 on same kind).

    Forgetting is part of learning: the internet-learner observes similar
    pages every night; without pruning the store grows with repetition,
    not signal. Keeps the FIRST occurrence of each duplicate cluster
    (oldest = the one that has been validated longest).
    Guarded like migrate(): refuses to shrink the store drastically.

    dry_run=True computes the identical decision but skips the write, so a
    caller that promised not to mutate (memory_consolidation --dry-run) does
    not rewrite the live store. Without it, a DRY RUN still pruned: measured
    10 edges -> 9 on a controlled fixture.
    """
    edges = _load()
    if not edges:
        return {"removed": 0, "kept": 0}
    kept, removed = [], 0
    # Pre-normalise once. The naive form re-normalised BOTH vectors inside every
    # pairwise comparison (3 sums over 768 dims per call), so a 466-edge store
    # cost 250M function calls / 43 s per nightly run. Normalising up front keeps
    # the identical >0.97 decision while making each comparison a single dot.
    seen_norm = []  # normalised embeddings of kept clusters
    for e in edges:
        emb = e.get("embedding") or []
        if not emb or not e.get("embed_ok"):
            kept.append(e)  # never drop un-embedded edges — they carry info
            continue
        n = _normalise(emb)
        if n is None:
            kept.append(e)
            continue
        dup_found = False
        for prev in seen_norm:
            if _dot(n, prev) > 0.97:
                dup_found = True
                break
        if dup_found:
            removed += 1
        else:
            seen_norm.append(n)
            kept.append(e)
    # SAFETY: if pruning would remove >30% something is wrong (embeddings
    # collapsed?) — abort instead of destroying the store
    if removed > len(edges) * 0.3:
        return {"error": f"refusing to prune {removed}/{len(edges)} (>30%) — "
                         "possible embedding collapse", "removed": 0, "kept": len(edges)}
    if removed and len(kept) > 0 and not dry_run:
        with _store_lock():
            _atomic_write([json.dumps(e, ensure_ascii=False) for e in kept])
    return {"removed": removed, "kept": len(kept)}


def observe(cause, effect, kind="fact", confidence=None):
    """Record a cause→effect edge with a real embedding.

    Deduplicates exact (cause, effect) repeats by incrementing a counter
    instead of appending another line — the nightly loops re-observe the
    same errors every night; 1186 exact dupes accumulated before this fix.
    """
    os.makedirs(os.path.dirname(WM), exist_ok=True)
    key = (str(cause)[:500], str(effect)[:500])
    with _store_lock():
        # cheap exact-dup check on the raw file tail (last 400 lines)
        try:
            if os.path.exists(WM):
                with open(WM, "r", encoding="utf-8") as f:
                    tail = f.readlines()[-400:]
                for line in tail:
                    try:
                        d = json.loads(line)
                    except Exception:
                        continue
                    if (d.get("cause"), d.get("effect")) == key:
                        d["dup_count"] = d.get("dup_count", 1) + 1
                        d["last_seen"] = datetime.datetime.now().isoformat()
                        with open(WM, "r", encoding="utf-8") as fr:
                            lines = fr.readlines()
                        for i, ln in enumerate(lines):
                            if ln.strip() and json.loads(ln).get("cause") == key[0] and \
                                    json.loads(ln).get("effect") == key[1]:
                                lines[i] = json.dumps(d, ensure_ascii=False) + "\n"
                                break
                        _atomic_write(lines)
                        return d
        except Exception:
            pass  # dup check failed -> fall through to append (never lose data)
    emb = embed(f"{cause} -> {effect}")
    edge = {
        "ts": datetime.datetime.now().isoformat(),
        "schema_version": SCHEMA_VERSION,
        "kind": kind,               # fact | prediction | correction
        "cause": cause[:500],
        "effect": effect[:500],
        "embedding": emb if emb is not None else [0.0] * DIM,
        "embed_ok": emb is not None,
    }
    if confidence is not None:
        edge["confidence"] = confidence
    with _store_lock():
        with open(WM, "a", encoding="utf-8") as f:
            f.write(json.dumps(edge, ensure_ascii=False) + "\n")
    return edge


def edge_key(edge):
    """Stable identity for an edge: (ts, cause). Used to exclude an edge from
    its own recall results — a validation that can match itself proves nothing."""
    return f"{edge.get('ts', '')}|{edge.get('cause', '')[:120]}"


def recall(query, k=5, kind=None, exclude=None):
    """Semantic nearest-neighbour search over the world model.

    `exclude` is a set of edge keys (see edge_key()) to omit from the results.
    This matters for validation: an edge is ALWAYS its own nearest neighbour
    (cosine 1.0 against its own embedding), so any checker that asks "did this
    come true?" while leaving the edge in the index will find itself and answer
    yes. That is how the prediction validator reported 32/32 correct while
    verifying nothing.
    """
    q = embed(query)
    if q is None:
        return []
    skip = set(exclude or ())
    edges = _load()
    scored = []
    for e in edges:
        if kind and e.get("kind") != kind:
            continue
        if not e.get("embed_ok", True):
            continue
        if skip and edge_key(e) in skip:
            continue
        scored.append((_cosine(q, e.get("embedding", [])), e))
    scored.sort(key=lambda x: -x[0])
    return [{"score": round(s, 4), "cause": e.get("cause", ""),
             "effect": e.get("effect", ""), "kind": e.get("kind", "fact"),
             "ts": e.get("ts", ""), "key": edge_key(e)} for s, e in scored[:k]]


def predict(situation, k=3):
    """Project the most likely effect for a situation from past edges."""
    hits = recall(situation, k=k)
    if not hits:
        return {"status": "no relevant past", "predictions": []}
    return {"status": "projected", "predictions": hits}


def stats():
    edges = _load()
    facts = sum(1 for e in edges if e.get("kind", "fact") == "fact")
    preds = sum(1 for e in edges if e.get("kind") == "prediction")
    corr = sum(1 for e in edges if e.get("kind") == "correction")
    ok_emb = sum(1 for e in edges if e.get("embed_ok", True))
    return {
        "total_edges": len(edges),
        "facts": facts,
        "predictions": preds,
        "corrections": corr,
        "real_embeddings": ok_emb,
        "embed_health": round(ok_emb / len(edges), 3) if edges else 0.0,
        "schema_version": SCHEMA_VERSION,
    }


def migrate():
    """Rewrite the store on disk to the current schema (idempotent).

    Guard: refuses to write an EMPTY store over a non-empty file — that is
    always a bug (empty read, wrong path, concurrent truncation), never an
    intent. A 599-edge world model must never silently become 0.
    """
    if not os.path.exists(WM):
        return {"migrated": 0, "schema_version": SCHEMA_VERSION}
    with _store_lock():
        # Read + size-check + write under ONE lock. Doing them separately let
        # a concurrent writer land between the count and the rewrite, which
        # is how a "safe" migration could still clobber fresh edges.
        edges = _load_unlocked()  # _load_unlocked already migrates in-memory
        try:
            with open(WM, encoding="utf-8") as f:
                existing = sum(1 for _ in f)
        except OSError:
            existing = 0
        if edges and existing > 0 and len(edges) < existing // 2:
            return {"error": f"refusing to shrink {existing} -> {len(edges)} edges "
                             f"(would lose {existing - len(edges)} memories)",
                    "schema_version": SCHEMA_VERSION}
        if not edges and existing > 0:
            return {"error": f"refusing to truncate {existing} edges to 0 "
                             f"(empty read = bug, not intent)",
                    "schema_version": SCHEMA_VERSION}
        _atomic_write([json.dumps(e, ensure_ascii=False) for e in edges])
        return {"migrated": len(edges), "schema_version": SCHEMA_VERSION}


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print(json.dumps(stats(), indent=2))
    elif sys.argv[1] == "observe" and len(sys.argv) >= 4:
        observe(sys.argv[2], sys.argv[3])
        print("observed")
    elif sys.argv[1] == "recall" and len(sys.argv) >= 3:
        for r in recall(sys.argv[2]):
            print(f"[{r['score']}] {r['cause']} -> {r['effect']}")
    elif sys.argv[1] == "predict" and len(sys.argv) >= 3:
        print(json.dumps(predict(sys.argv[2]), indent=2, ensure_ascii=False))
    elif sys.argv[1] == "stats":
        print(json.dumps(stats(), indent=2))
    elif sys.argv[1] == "migrate":
        print(json.dumps(migrate(), indent=2))
