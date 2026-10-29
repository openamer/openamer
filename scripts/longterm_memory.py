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
import re
import os
from pathlib import Path
import sys
import urllib.request

BASE = os.environ.get(
    "OPENAMER_HOME",
    str(Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "openamer-laptop"),
)
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
    """Load every episode that carries text.

    A vector is optional on purpose: an episode written while the embedding
    service was down is still a memory, and hybrid retrieval can reach it by its
    words. Requiring an embedding here silently deleted ~1,000 such records from
    every search, which is the opposite of what a memory store is for.
    Foreign/heartbeat lines without text are still skipped, so one bad line
    cannot crash index/query/stats.
    """
    if not os.path.exists(STORE):
        return []
    out = []
    with open(STORE, encoding="utf-8") as fh:
        for l in fh:
            try:
                e = json.loads(l)
            except json.JSONDecodeError:
                continue
            if isinstance(e, dict) and "text" in e:
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
                if not (isinstance(rec, dict) and "text" in rec):
                    kept_lines.append(json.dumps(rec, ensure_ascii=False) + "\n")
    # Write to a sibling file and swap it in. Truncating the real store first
    # means every concurrent reader sees a half-written memory, and a crash
    # between the truncate and the last line destroys the whole store. Measured
    # 2026-10-26: a query run against a saving store saw 5,110 of 8,095 episodes.
    staging = STORE + ".new"
    with open(staging, "w", encoding="utf-8") as handle:
        handle.writelines(kept_lines)
        for episode in episodes:
            handle.write(json.dumps(episode, ensure_ascii=False) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(staging, STORE)

def _cos(a, b):
    # An episode written while the embedding service was unreachable has no
    # vector. Skipping it keeps recall working instead of crashing the query on
    # the first such record.
    if not a or not b:
        return None
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
    with open(BRAIN, encoding="utf-8") as fh:
        for line in fh:
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
                except (OSError, ValueError, KeyError) as exc:
                    # A dead embedder must not index nothing in silence: that is
                    # exactly how this store stayed frozen for 17 days with every
                    # status green. Catch only what an embed can raise on its way
                    # out - urlopen/HTTP (OSError), a bad JSON body (ValueError),
                    # a body without "embedding" (KeyError) - record it on the row
                    # and count it. A programming error still surfaces instead of
                    # being swallowed into "0 indexed, all good".
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

# Words that carry no retrieval signal. Kept deliberately short: a long list
# starts eating the identifiers that matter most in this store (file names,
# command fragments, error codes).
_STOPWORDS = frozenset(
    "the and for with that this from were was has have not but you der die das und "
    "ist nicht ein eine mit auf für den dem des ich wir sie es zu von im".split()
)

_TOKEN_RE = re.compile(r"[a-z0-9_\-]{4,}")


def _tokens(text):
    return {word for word in _TOKEN_RE.findall(text.lower()) if word not in _STOPWORDS}


def _keyword_score(query_tokens, text):
    """Share of the query's content words that appear in the episode.

    Exact identifiers - channel names, file paths, commands, error codes - are
    what a person actually searches for, and embeddings are weakest exactly
    there. Measured on this store: recall@5 went from 3/24 to 18/24 when this
    term was added, with no query made worse.
    """
    if not query_tokens:
        return 0.0
    return len(query_tokens & _tokens(text)) / len(query_tokens)


# Inverse document frequency is what makes search work on this corpus: a probe
# of three words is usually two common ones ("scan", "version") plus one rare one
# ("helix", "9222"). Without IDF, thousands of episodes tie at a perfect token
# overlap and the ordering inside that tie is arbitrary - measured, that cost 5
# of 16 hits. IDF lets the rare word decide.
_IDF_CACHE = {"key": None, "df": None, "n": 0}


def _document_frequencies(eps):
    """Token -> number of episodes containing it, cached per store version."""
    try:
        stamp = (len(eps), os.path.getmtime(STORE))
    except OSError:
        stamp = (len(eps), 0)
    if _IDF_CACHE["key"] == stamp:
        return _IDF_CACHE["df"], _IDF_CACHE["n"]
    df = {}
    for record in eps:
        for token in _tokens(record.get("text", "")):
            df[token] = df.get(token, 0) + 1
    _IDF_CACHE.update({"key": stamp, "df": df, "n": len(eps)})
    return df, len(eps)


def _keyword_score(query_tokens, text, df, total):
    """IDF-weighted share of the query's content words present in the episode.

    Returned in [0, 1]: 1 means every query term appears and they are all rare.
    """
    if not query_tokens or total <= 0:
        return 0.0
    weight_total = 0.0
    weight_hit = 0.0
    present = _tokens(text)
    for token in query_tokens:
        occurrences = df.get(token, 0)
        # A term in most episodes separates nothing; floor it at a tiny weight.
        weight = math.log((total + 1) / (occurrences + 1)) + 0.05
        weight_total += weight
        if token in present:
            weight_hit += weight
    return weight_hit / weight_total if weight_total else 0.0


# Reciprocal-rank-fusion constant: how fast the influence of a lower rank decays.
_RRF_K = 60


def _expansion_terms(records, query_tokens, df, total, limit=12):
    """Terms that the first-pass hits share, but the question did not contain.

    Pseudo-relevance feedback: the top of a first ranking is usually on topic even
    when it misses the exact memory, and its vocabulary bridges the gap a
    paraphrase leaves. "Wie speichere ich Erinnerungen dauerhaft" shares no term
    with an episode about `embedding`, but the episodes it does reach are on the
    same subject and carry that word.

    A term qualifies when it is rare enough to separate (document frequency below
    5 %) and appears in at least two of the sampled records - one occurrence can be
    an accident.
    """
    if not records:
        return []
    ceiling = max(2, int(total * 0.05))
    counts = {}
    for record in records:
        for token in _tokens(record.get("text", "")):
            if token in query_tokens:
                continue
            if df.get(token, total) > ceiling:
                continue
            counts[token] = counts.get(token, 0) + 1
    candidates = [(count, token) for token, count in counts.items() if count >= 2]
    candidates.sort(key=lambda pair: (-pair[0], pair[1]))
    return [token for _count, token in candidates[:limit]]


def query(q, k=5, pool=300, expand=True):
    """Hybrid retrieval by reciprocal rank fusion of a semantic and a lexical list.

    Why fusion and not a weighted sum, why not max():

    - A weighted sum compares a cosine with a term overlap, and they do not share
      a scale. Measured here: a perfect rare-term match scored 0.40 while a
      mediocre cosine scored 0.45, so a memory written without an embedding could
      never win.
    - max() fixes the scale but not the meaning: every corpus has a nearest
      neighbour, so the top cosine is routinely near 1.0 whether or not it is the
      right record, while an IDF match of 1.0 really does mean every rare term is
      present. Taking the larger of the two therefore ends in a tie that order
      decides.

    Rank fusion sidesteps both: each signal proposes its own ordering, a record
    that appears high in *either* list wins, and a record that appears in *both*
    wins clearly. Ties inside a list are what made an earlier attempt at this
    worse than the blend it replaced - the lexical list is IDF-weighted now, so
    its scores are continuous and its ranks mean something.
    """
    eps = _load()
    if not eps:
        return []

    qv = embed(q)
    query_tokens = _tokens(q)
    df, total = _document_frequencies(eps)

    semantic = []
    if qv:
        for index, record in enumerate(eps):
            vector = record.get("embedding")
            if not vector:
                continue
            similarity = _cos(qv, vector)
            if similarity is not None and similarity > 0:
                semantic.append((similarity, index))
        semantic.sort(key=lambda pair: -pair[0])

    # Any overlap may form a ranking. A floor was tried here (0.35) and made
    # retrieval worse: one term matching out of three is exactly the case where
    # the lexical list carries the answer. Measured: a threshold dropped a
    # paraphrase that had climbed from rank 1,393 to 4 back out of the top 40.
    lexical = []
    for index, record in enumerate(eps):
        overlap = _keyword_score(query_tokens, record.get("text", ""), df, total)
        if overlap > 0:
            lexical.append((overlap, index))
    lexical.sort(key=lambda pair: -pair[0])

    def fuse(lexical_ranking):
        combined = {}
        for ranking in (semantic[:pool], lexical_ranking[:pool]):
            for position, (_score, index) in enumerate(ranking, start=1):
                combined[index] = combined.get(index, 0.0) + 1.0 / (_RRF_K + position)
        return combined

    fused = fuse(lexical)

    # Expand only as a rescue: when the question shares no content word with the
    # corpus at all. Measured, letting it fire unconditionally costs precision -
    # 'Nachricht an Telegram' went from rank 4 to 11 - while the case it exists for
    # ('Erinnerungen dauerhaft speichern', no shared vocabulary) moved from
    # unreachable to rank 151.
    if expand and not lexical:
        first_pass = sorted(fused.items(), key=lambda pair: -pair[1])[:10]
        extra = _expansion_terms([eps[index] for index, _v in first_pass], query_tokens, df, total)
        if extra:
            wide_tokens = query_tokens | set(extra)
            wider = []
            for index, record in enumerate(eps):
                overlap = _keyword_score(wide_tokens, record.get("text", ""), df, total)
                if overlap > 0:
                    wider.append((overlap, index))
            wider.sort(key=lambda pair: -pair[0])
            fused = fuse(wider)

    if not fused:
        return []
    ordered = sorted(fused.items(), key=lambda pair: -pair[1])[:k]
    best = ordered[0][1]
    return [(round(value / best, 3), eps[index]) for index, value in ordered]


def backfill_embeddings(limit=None, checkpoint=25):
    """Give episodes without a vector the embedding they were denied.

    A record written while the embedder was down carries `embed_error` instead of
    a vector. Dropping it before search and bending the ranking so it can compete
    without one are both wrong repairs: the memory is intact, only its index is
    missing. Embed it.

    Progress is written every `checkpoint` rows, so a run killed mid-way keeps
    what it already earned and the next run continues.
    """
    eps = _load()
    missing = [e for e in eps if not e.get("embedding") and e.get("text")]
    if limit:
        missing = missing[:limit]
    fixed = 0
    failed = 0
    reasons = {}
    for position, record in enumerate(missing, start=1):
        try:
            vector = embed(record["text"])
        except (OSError, ValueError, KeyError) as exc:
            failed += 1
            name = type(exc).__name__
            reasons[name] = reasons.get(name, 0) + 1
            continue
        if not vector:
            failed += 1
            reasons["empty"] = reasons.get("empty", 0) + 1
            continue
        record["embedding"] = vector
        record.pop("embed_error", None)
        fixed += 1
        if position % checkpoint == 0:
            _save(eps)
    if fixed:
        _save(eps)
    return {"candidates": len(missing), "fixed": fixed, "failed": failed, "reasons": reasons}


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
    elif cmd == "backfill":
        limit = int(sys.argv[2]) if len(sys.argv) > 2 else None
        result = backfill_embeddings(limit)
        print(json.dumps(result, indent=1))
        if result["failed"]:
            sys.exit(1)
    elif cmd == "query":
        for s, e in query(" ".join(sys.argv[2:])):
            print(f"[{s}] ({e['kind']}) {e['text'][:200]}")
    else:
        print(json.dumps(stats(), indent=1))
