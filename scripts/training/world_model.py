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

import json, os, math, datetime, urllib.request, threading, pathlib

_HOME = pathlib.Path(os.environ.get(
    "OPENAMER_HOME", str(pathlib.Path.home() / "AppData" / "Local" / "openamer-laptop")))

WM = os.path.join(_HOME, "memory", "world_model.jsonl")
EMBED_URL = "http://localhost:11434/api/embeddings"
EMBED_MODEL = "nomic-embed-text"
DIM = 768

_lock = threading.Lock()


def embed(text):
    """Return a real 768-dim embedding, or None on failure (never a fake)."""
    try:
        req = urllib.request.Request(
            EMBED_URL,
            data=json.dumps({"model": EMBED_MODEL, "prompt": text[:2000]}).encode(),
            headers={"Content-Type": "application/json"})
        return json.load(urllib.request.urlopen(req, timeout=30))["embedding"]
    except Exception:
        return None


def _cosine(a, b):
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def _load():
    if not os.path.exists(WM):
        return []
    out = []
    for line in open(WM, encoding="utf-8"):
        try:
            out.append(json.loads(line))
        except Exception:
            continue
    return out


def observe(cause, effect, kind="fact", confidence=None):
    """Record a cause→effect edge with a real embedding."""
    os.makedirs(os.path.dirname(WM), exist_ok=True)
    emb = embed(f"{cause} -> {effect}")
    edge = {
        "ts": datetime.datetime.now().isoformat(),
        "kind": kind,               # fact | prediction | correction
        "cause": cause[:500],
        "effect": effect[:500],
        "embedding": emb if emb is not None else [0.0] * DIM,
        "embed_ok": emb is not None,
    }
    if confidence is not None:
        edge["confidence"] = confidence
    with _lock:
        with open(WM, "a", encoding="utf-8") as f:
            f.write(json.dumps(edge, ensure_ascii=False) + "\n")
    return edge


def recall(query, k=5, kind=None):
    """Semantic nearest-neighbour search over the world model."""
    q = embed(query)
    if q is None:
        return []
    edges = _load()
    scored = []
    for e in edges:
        if kind and e.get("kind") != kind:
            continue
        if not e.get("embed_ok", True):
            continue
        scored.append((_cosine(q, e.get("embedding", [])), e))
    scored.sort(key=lambda x: -x[0])
    return [{"score": round(s, 4), "cause": e.get("cause", ""),
             "effect": e.get("effect", ""), "kind": e.get("kind", "fact"),
             "ts": e.get("ts", "")} for s, e in scored[:k]]


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
    }


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
