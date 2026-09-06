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
import os
import json, sys, os, time, urllib.request, math, hashlib, datetime, pathlib
from pathlib import Path

BASE = os.environ.get("OPENAMER_HOME", str(Path.home() / "AppData" / "Local" / "openamer"))
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

# ---- World Model (delegated to the central module) ----
def observe(cause, effect):
    """Store a cause->effect edge via the central world model."""
    import world_model
    world_model.observe(cause, effect)
    return "observed"

def _load_world():
    import world_model
    return world_model._load()

def _cos(a, b):
    import world_model
    return world_model._cosine(a, b)

def predict(situation, k=3):
    """Given a new situation, retrieve the most relevant known cause-effect pairs."""
    import world_model
    hits = world_model.recall(situation, k=k)
    return [(h["score"], {"cause": h["cause"], "effect": h["effect"]}) for h in hits]

def graph_stats():
    import world_model
    return {"edges": world_model.stats()["total_edges"]}

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
