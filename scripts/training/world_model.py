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

# Schema versioning: every edge carries its schema_version. When the shape
# changes, bump SCHEMA_VERSION and add a migration in _migrate_edge(). This
# is what stops silent schema breaks (the kind that made predict_validate
# find 0 predictions after the kind/type rename).
SCHEMA_VERSION = 2

_lock = threading.Lock()


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
            out.append(_migrate_edge(json.loads(line)))
        except Exception:
            continue
    return out


def prune(max_dupes=2):
    """Remove near-duplicate edges (cosine > 0.97 on same kind).

    Forgetting is part of learning: the internet-learner observes similar
    pages every night; without pruning the store grows with repetition,
    not signal. Keeps the FIRST occurrence of each duplicate cluster
    (oldest = the one that has been validated longest).
    Guarded like migrate(): refuses to shrink the store drastically.
    """
    edges = _load()
    if not edges:
        return {"removed": 0, "kept": 0}
    kept, removed = [], 0
    seen_buckets = []  # list of (embedding, [indices of cluster])
    for e in edges:
        emb = e.get("embedding") or []
        if not emb or not e.get("embed_ok"):
            kept.append(e)  # never drop un-embedded edges — they carry info
            continue
        dup_found = False
        for cluster in seen_buckets:
            if _cosine(emb, cluster[0]) > 0.97:
                dup_found = True
                break
        if dup_found:
            removed += 1
        else:
            seen_buckets.append((emb, [e]))
            kept.append(e)
    # SAFETY: if pruning would remove >30% something is wrong (embeddings
    # collapsed?) — abort instead of destroying the store
    if removed > len(edges) * 0.3:
        return {"error": f"refusing to prune {removed}/{len(edges)} (>30%) — "
                         "possible embedding collapse", "removed": 0, "kept": len(edges)}
    if removed and len(kept) > 0:
        with _lock:
            with open(WM, "w", encoding="utf-8") as f:
                for e in kept:
                    f.write(json.dumps(e, ensure_ascii=False) + "\n")
    return {"removed": removed, "kept": len(kept)}


def _cosine(a, b):
    """Cosine similarity for two equal-length vectors."""
    import math
    num = sum(x * y for x, y in zip(a, b))
    da = math.sqrt(sum(x * x for x in a)) or 1.0
    db = math.sqrt(sum(y * y for y in b)) or 1.0
    return num / (da * db)


def observe(cause, effect, kind="fact", confidence=None):
    """Record a cause→effect edge with a real embedding.

    Deduplicates exact (cause, effect) repeats by incrementing a counter
    instead of appending another line — the nightly loops re-observe the
    same errors every night; 1186 exact dupes accumulated before this fix.
    """
    os.makedirs(os.path.dirname(WM), exist_ok=True)
    key = (str(cause)[:500], str(effect)[:500])
    with _lock:
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
                        with open(WM, "w", encoding="utf-8") as fw:
                            fw.writelines(lines)
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
    edges = _load()  # _load already migrates in-memory
    existing = sum(1 for _ in open(WM, encoding="utf-8"))
    if edges and existing > 0 and len(edges) < existing // 2:
        return {"error": f"refusing to shrink {existing} -> {len(edges)} edges "
                         f"(would lose {existing - len(edges)} memories)",
                "schema_version": SCHEMA_VERSION}
    if not edges and existing > 0:
        return {"error": f"refusing to truncate {existing} edges to 0 "
                         f"(empty read = bug, not intent)",
                "schema_version": SCHEMA_VERSION}
    with _lock:
        with open(WM, "w", encoding="utf-8") as f:
            for e in edges:
                f.write(json.dumps(e, ensure_ascii=False) + "\n")
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
