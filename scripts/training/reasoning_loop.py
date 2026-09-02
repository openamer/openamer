#!/usr/bin/env python3
"""Recursive Reasoning Loop + World-Model Builder for Mini-OpenAmer.

The 2B model alone cannot reason deeply. But it doesn't need to — it needs
a SYSTEM that forces reasoning depth. This script is that system.

## Recursive Reasoning Loop (think -> check -> correct -> repeat)
Given a question, the mini model generates an answer, then CRITIQUES its own
answer (2nd call), then generates a corrected version (3rd call). Each cycle
doubles effective reasoning depth without more parameters.

## World-Model Builder (cause -> effect graph)
Every observed cause-effect pair (e.g. "RAM-Guard stopped server" →
"server down until restart") is stored as a typed edge in a persistent
graph. Over time this becomes the model's PHYSICS INTUITION — not learned
in weights, but IN THE GRAPH, retrievable by similarity.

CLI:
  python reasoning_loop.py ask "frage"            # recursive answer
  python reasoning_loop.py observe "cause" "effect"   # add world-model edge
  python reasoning_loop.py predict "situation"    # retrieve relevant causes
  python reasoning_loop.py graph-stats
"""
import json, sys, os, time, urllib.request, math, hashlib, datetime, pathlib

BASE = r"C:/Users/damir/AppData/Local/openamer-laptop"
WORLD = os.path.join(BASE, "memory", "world_model.jsonl")
LIVE = "http://localhost:8081"
MAX_ROUNDS = 2

os.makedirs(os.path.dirname(WORLD), exist_ok=True)

def chat(messages, max_tokens=250):
    req = urllib.request.Request(LIVE + "/v1/chat/completions",
        data=json.dumps({"model": "mini-openamer", "messages": messages,
                         "max_tokens": max_tokens}).encode(),
        headers={"Content-Type": "application/json"})
    r = json.load(urllib.request.urlopen(req, timeout=300))
    return r["choices"][0]["message"]["content"].strip()

def embed(text):
    req = urllib.request.Request("http://localhost:11434/api/embeddings",
        data=json.dumps({"model": "nomic-embed-text", "prompt": text[:2000]}).encode(),
        headers={"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=30))["embedding"]

def recursive_ask(question, rounds=MAX_ROUNDS):
    """Think -> critique -> improve. Each round = deeper reasoning."""
    system = ("Du bist OpenAmer Agent. Antworte präzise und ehrlich. "
              "Wenn du unsicher bist, sage es.")
    answer = chat([{"role": "system", "content": system},
                   {"role": "user", "content": question}])
    history = [answer]
    for rnd in range(1, rounds):
        critique_q = (f"Frage: {question}\n\nDeine bisherige Antwort:\n{answer}\n\n"
                      f"Prüfe diese Antwort kritisch: Was fehlt? Was ist falsch? "
                      f"Welche Annahmen sind ungetestet? Antworte kompakt.")
        critique = chat([{"role": "user", "content": critique_q}], max_tokens=200)
        if len(critique) < 50 or "nichts zu korrigieren" in critique.lower():
            break
        improve_q = (f"Frage: {question}\n\nEntwurf:\n{answer}\n\n"
                     f"Kritik: {critique}\n\nBringe die Antwort auf Basis der Kritik "
                     f"auf den Punkt. Antworte kurz, klar, nur die finale verbesserte Antwort. Maximal 150 Wörter.")
        answer = chat([{"role": "user", "content": improve_q}], max_tokens=300)
        history.append(critique)
        history.append(answer)
    return {"answer": answer, "rounds": len(history), "history": history}

# ---- World Model ----
def observe(cause, effect):
    """Store a cause->effect edge with embedding for similarity retrieval."""
    edge = {"ts": datetime.datetime.now().isoformat(),
            "cause": cause[:500], "effect": effect[:500],
            "embedding": embed(cause + " → " + effect)}
    with open(WORLD, "a", encoding="utf-8") as f:
        f.write(json.dumps(edge, ensure_ascii=False) + "\n")
    return "observed"

def _load_world():
    if not os.path.exists(WORLD):
        return []
    out = []
    for l in open(WORLD, encoding="utf-8"):
        try: out.append(json.loads(l))
        except: continue
    return out

def _cos(a, b):
    dot = sum(x*y for x, y in zip(a, b))
    na = math.sqrt(sum(x*x for x in a)) or 1
    nb = math.sqrt(sum(y*y for y in b)) or 1
    return dot / (na * nb)

def predict(situation, k=3):
    """Given a new situation, retrieve the most relevant known cause-effect pairs."""
    edges = _load_world()
    if not edges: return []
    qv = embed(situation)
    scored = sorted(((_cos(qv, e["embedding"]), e) for e in edges), key=lambda x: -x[0])
    return [(round(s,3), e) for s, e in scored[:k]]

def graph_stats():
    edges = _load_world()
    return {"edges": len(edges)}

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"
    if cmd == "ask":
        r = recursive_ask(" ".join(sys.argv[2:]))
        print(json.dumps(r, ensure_ascii=False, indent=1))
    elif cmd == "observe":
        print(observe(sys.argv[2], sys.argv[3]))
    elif cmd == "predict":
        for s, e in predict(" ".join(sys.argv[2:])):
            print(f"[{s}] {e['cause'][:80]} → {e['effect'][:80]}")
    elif cmd == "graph-stats":
        print(json.dumps(graph_stats(), indent=1))
    else:
        print(__doc__)
