#!/usr/bin/env python3
"""Analogy Engine — cross-domain transfer for Mini-OpenAmer.

Turns episodic memories into ABSTRACT STRUCTURES (skeletons), indexes them,
and finds structurally similar past situations for new problems. This is
analogy reasoning: transfer by shape, not by surface text.

Pipeline:
  1. EXTRACT  — LLM strips an episode to its abstract skeleton
                (e.g. "RAM-Guard kills server" -> "resource limit -> process
                termination -> recovery on restart")
  2. INDEX    — skeletons stored with embeddings in structures.jsonl
  3. ANALOGY  — for a new problem: extract skeleton, find nearest skeletons
                from OTHER domains, return the transferred solution

CLI:
  python analogy_engine.py extract "<episode text>"   # skeletonize one episode
  python analogy_engine.py extract-batch              # skeletonize latest episodes
  python analogy_engine.py find "<new problem>"       # find analogies
  python analogy_engine.py stats
"""
import json, sys, os, math, urllib.request, datetime, pathlib

BASE = r"C:/Users/damir/AppData/Local/openamer-laptop"
STRUCTS = os.path.join(BASE, "memory", "structures.jsonl")
BRAIN = r"C:/Users/damir/.openamer/a2a/openamer-brain.jsonl"
LIVE = "http://localhost:8081"
OLLAMA_EMBED = "http://localhost:11434/api/embeddings"
MAX_STRUCTURED = 500

SYSTEM_PROMPT = (
    "Extract the ABSTRACT STRUCTURE of a situation. Ignore all names, "
    "technologies and domains. Use ONLY generic pattern terms such as: "
    "resource exhaustion, filter barrier, feedback loop, selection pressure, "
    "single point of failure, rate limiting, cascading failure, hidden "
    "dependency, state corruption, authentication wall, retry loop. "

    "EXAMPLE: Situation: The RAM guard killed the mini server because only "
    "2GB RAM were free. Training worked again after freeing RAM. "
    "Correct skeleton: resource exhaustion causes process termination; "
    "recovery requires releasing the constrained resource. "

    "Now reply ONLY with the skeleton (1-2 sentences, generic terms only, "
    "no names of specific technologies)."
)

def chat(messages, max_tokens=120):
    req = urllib.request.Request(LIVE + "/v1/chat/completions",
        data=json.dumps({"model": "mini-openamer", "messages": messages,
                         "max_tokens": max_tokens}).encode(),
        headers={"Content-Type": "application/json"})
    r = json.load(urllib.request.urlopen(req, timeout=300))
    return r["choices"][0]["message"]["content"].strip()

def embed(text):
    req = urllib.request.Request(OLLAMA_EMBED,
        data=json.dumps({"model": "nomic-embed-text", "prompt": text[:2000]}).encode(),
        headers={"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=30))["embedding"]

def _load():
    if not os.path.exists(STRUCTS):
        return []
    out = []
    for l in open(STRUCTS, encoding="utf-8"):
        try: out.append(json.loads(l))
        except: continue
    return out

def _save(items):
    with open(STRUCTS, "w", encoding="utf-8") as f:
        for e in items:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")

def extract(episode_text, source="manual"):
    """Turn one concrete episode into an abstract skeleton + index it."""
    skeleton = chat([
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": episode_text[:2000]}])
    entry = {"ts": datetime.datetime.now().isoformat(), "source": source,
             "episode": episode_text[:400], "skeleton": skeleton[:400],
             "embedding": embed(skeleton)}
    items = _load()
    # dedupe on skeleton text
    if any(e["skeleton"] == entry["skeleton"] for e in items):
        return {"skipped": "duplicate skeleton"}
    items.append(entry)
    _save(items)
    return {"skeleton": skeleton, "total": len(items)}

def extract_batch(limit=20):
    """Skeletonize the newest brain episodes not yet processed."""
    items = _load()
    done = {e["episode"][:200] for e in items}
    added = 0
    for line in open(BRAIN, encoding="utf-8"):
        if added >= limit:
            break
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        lu = None
        for m in d.get("messages", []):
            r = m.get("role")
            if r == "user":
                lu = (m.get("content") or "").strip()
            elif r == "assistant" and lu:
                ac = (m.get("content") or "").strip()
                text = f"User: {lu[:600]}\nAssistant: {ac[:400]}"
                if (30 <= len(ac) <= 2000 and 3 <= len(lu) <= 2000 and ac
                        and not lu.startswith("[")
                        and text[:200] not in done):
                    res = extract(text, source="brain")
                    if "skeleton" in res:
                        added += 1
                lu = None
                break
    return {"added": added, "total": len(_load())}

def find(problem, k=3):
    """Find structurally similar past situations for a new problem."""
    # 1. skeletonize the new problem (structure level, not surface)
    new_skel = chat([
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": problem[:2000]}])
    qv = embed(new_skel)
    items = _load()
    scored = sorted(((_cos(qv, e["embedding"]), e) for e in items), key=lambda x: -x[0])
    return {"new_skeleton": new_skel,
            "analogies": [{"sim": round(s, 3), "skeleton": e["skeleton"],
                           "episode": e["episode"][:200]}
                          for s, e in scored[:k] if s > 0.3]}

def _cos(a, b):
    dot = sum(x*y for x, y in zip(a, b))
    na = math.sqrt(sum(x*x for x in a)) or 1
    nb = math.sqrt(sum(y*y for y in b)) or 1
    return dot / (na * nb)

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"
    if cmd == "extract":
        print(json.dumps(extract(" ".join(sys.argv[2:])), ensure_ascii=False, indent=1))
    elif cmd == "extract-batch":
        print(json.dumps(extract_batch(), indent=1))
    elif cmd == "find":
        print(json.dumps(find(" ".join(sys.argv[2:])), ensure_ascii=False, indent=1))
    else:
        print(json.dumps({"structures": len(_load())}, indent=1))
