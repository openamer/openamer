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
import json, sys, math, os, datetime, urllib.request, hashlib

BASE = r"C:/Users/damir/AppData/Local/openamer-laptop"
STORE = os.path.join(BASE, "memory", "longterm_episodes.jsonl")
EMBED_CACHE = os.path.join(BASE, "memory", "embed_cache.json")   # energy-saving: skip re-embed
BRAIN = r"C:/Users/damir/.openamer/a2a/openamer-brain.jsonl"
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
    if not os.path.exists(STORE):
        return []
    out = []
    for l in open(STORE, encoding="utf-8"):
        try:
            out.append(json.loads(l))
        except json.JSONDecodeError:
            continue
    return out

def _save(episodes):
    with open(STORE, "w", encoding="utf-8") as f:
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
    have = {e["text"][:200] for e in eps}
    added = 0
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
            except Exception:
                continue
            eps.append(ep)
            have.add(t[:200])
            added += 1
            if added % 50 == 0:
                _save(eps)
                print(f"  ... {len(eps)} episodes indexed")
    _save(eps)
    return len(eps)

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
        print("indexed:", index_brain())
    elif cmd == "add":
        print("episodes:", add_episode(sys.argv[2]))
    elif cmd == "query":
        for s, e in query(" ".join(sys.argv[2:])):
            print(f"[{s}] ({e['kind']}) {e['text'][:200]}")
    else:
        print(json.dumps(stats(), indent=1))
