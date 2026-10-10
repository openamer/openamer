#!/usr/bin/env python3
"""Long-term episodic memory for OpenAmer — local, embedding-based, forever.

Builds a persistent vector index over conversation highlights (user turns +
assistant key answers + insights) from the brain dataset + session DB.
Retrieval: cosine similarity via Ollama nomic-embed-text (768d).

Storage: memory_store.jsonl (append-only, the "episodes") + in-memory cosine
(no external vector DB needed at this scale; brute-force is fine < 100k).

CLI:
  python longterm_memory.py index        # (re)build index from brain data
  python longterm_memory.py add "text"   # add one episode
  python longterm_memory.py query "..."  # top-5 relevant episodes
  python longterm_memory.py stats
"""
import datetime
import hashlib
import json
import math
import os
import sys
import urllib.request
from pathlib import Path

BASE = os.environ.get("OPENAMER_HOME", str(Path.home() / "AppData" / "Local" / "openamer"))
STORE = os.path.join(BASE, "memory", "longterm_episodes.jsonl")
EMBED_CACHE = os.path.join(BASE, "memory", "embed_cache.json")   # energy-saving: skip re-embed
BRAIN = os.path.join(BASE, "a2a", "openamer-brain.jsonl")
EMBED_MODEL = "nomic-embed-text"

os.makedirs(os.path.dirname(STORE), exist_ok=True)

def _load_cache():
    if not os.path.exists(EMBED_CACHE):
        return {}
    try:
        return json.load(open(EMBED_CACHE, encoding="utf-8"))
    except json.JSONDecodeError:
        return {}

def _save_cache(cache):
    # keep cache bounded (LRU-ish: drop oldest beyond 5000 entries)
    if len(cache) > 5000:
        cache = dict(list(cache.items())[-5000:])
    with open(EMBED_CACHE, "w", encoding="utf-8") as f:
        json.dump(cache, f)

def embed(text):
    """Embedding with persistent cache — identical text costs 0 compute."""
    key = hashlib.sha256(text[:4000].encode("utf-8")).hexdigest()[:24]
    cache = _load_cache()
    if key in cache:
        return cache[key]
    req = urllib.request.Request(
        "http://localhost:11434/api/embeddings",
        data=json.dumps({"model": EMBED_MODEL, "prompt": text[:4000]}).encode(),
        headers={"Content-Type": "application/json"})
    vec = json.load(urllib.request.urlopen(req, timeout=30))["embedding"]
    cache[key] = vec
    _save_cache(cache)
    return vec

def _load():
    """Load valid episodes only. Foreign/heartbeat records (no text/embedding)
    are skipped so one bad line can never crash index/query/stats."""
    if not os.path.exists(STORE):
        return []
    out = []
    with open(STORE, encoding="utf-8") as fh:
        for l in fh:
            try:
                e = json.loads(l)
            except json.JSONDecodeError:
                continue
            if isinstance(e, dict) and "text" in e and "embedding" in e:
                out.append(e)
    return out

def _save(episodes):
    """Write the store back without losing a single byte the store already held.

    ``_load()`` deliberately yields only records carrying both ``text`` and an
    ``embedding``, so index/query/stats can never crash on a foreign line. The bug
    was that ``_save()`` wrote back exactly that list and therefore DELETED every
    record ``_load()`` had skipped. Measured 2026-10-10 before the fix: 2898 of
    3065 records were ``kind="compressed"`` with no embedding, so one ``index`` run
    would have erased 3 MB of real episodes. Skipped records - and an unparseable
    line, which is data too - are now carried through untouched.
    """
    kept_lines: list[str] = []
    if os.path.exists(STORE):
        with open(STORE, encoding="utf-8") as fh:
            for line in fh:
                if not line.strip():
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    kept_lines.append(line if line.endswith("\n") else line + "\n")
                    continue
                if not (isinstance(rec, dict) and "text" in rec and "embedding" in rec):
                    kept_lines.append(json.dumps(rec, ensure_ascii=False) + "\n")
    with open(STORE, "w", encoding="utf-8") as f:
        f.writelines(kept_lines)
        for e in episodes:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")

def _cos(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1
    nb = math.sqrt(sum(y * y for y in b)) or 1
    return dot / (na * nb)

def add_episode(text, kind="manual", meta=None):
    eps = _load()
    ep = {"ts": datetime.datetime.now().isoformat(), "kind": kind,
          "text": text[:6000], "meta": meta or {}}
    ep["embedding"] = embed(text)
    eps.append(ep)
    _save(eps)
    return len(eps)

def index_brain(max_episodes=3000):
    """Index user turns + assistant answers as episodes (dedup by text hash)."""
    eps = _load()
    have = {e.get("text", "")[:200] for e in eps}
    added = 0
    skipped = 0
    for line in open(BRAIN, encoding="utf-8"):
        if added >= max_episodes:
            break
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        for m in d.get("messages", []):
            if m.get("role") not in ("user", "assistant"):
                continue
            t = (m.get("content") or "").strip()
            if len(t) < 60 or t[:200] in have or t.startswith("[IMPORTANT:"):
                continue
            ep = {"ts": datetime.datetime.now().isoformat(),
                  "kind": f"brain_{m['role']}", "text": t[:6000], "meta": {}}
            try:
                ep["embedding"] = embed(t)
            except Exception as exc:
                # A blind `continue` here silently skipped rows, so a broken
                # embedder would index nothing and the store would look healthy
                # while staying frozen. Record the failure instead.
                ep["embedding"] = None
                ep["embed_error"] = f"{type(exc).__name__}: {exc}"
                skipped += 1
            eps.append(ep)
            have.add(t[:200])
            added += 1
            if added % 50 == 0:
                _save(eps)
                print(f"  ... {len(eps)} episodes indexed")
    _save(eps)
    return len(eps), skipped

def query(q, k=5):
    eps = _load()
    if not eps:
        return []
    qv = embed(q)
    scored = sorted(((_cos(qv, e["embedding"]), e) for e in eps),
                    key=lambda x: -x[0])
    return [(round(s, 3), e) for s, e in scored[:k]]

def stats():
    eps = _load()
    kinds = {}
    for e in eps:
        kinds[e["kind"]] = kinds.get(e["kind"], 0) + 1
    return {"total": len(eps), "kinds": kinds, "file": STORE}

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "stats"
    if cmd == "index":
        # Optional per-run cap: the default 3000 would need ~92 minutes at the
        # measured 1.85 s per fresh embedding and could never finish inside a
        # cron window. Progress is saved every 50 rows, so bounded runs work the
        # backlog off across several runs instead of being killed mid-way.
        cap = int(sys.argv[2]) if len(sys.argv) > 2 else 3000
        total, skipped = index_brain(cap)
        print(f"indexed: {total} episodes ({skipped} embed failures)")
        if skipped:
            # A failed embed means the store did not grow. Say so loudly: the old
            # blind `continue` let a broken embedder freeze this store for 17 days
            # while every status stayed green.
            sys.exit(1)
    elif cmd == "add":
        print("episodes:", add_episode(sys.argv[2]))
    elif cmd == "query":
        for s, e in query(" ".join(sys.argv[2:])):
            print(f"[{s}] ({e['kind']}) {e['text'][:200]}")
    else:
        print(json.dumps(stats(), indent=1))
