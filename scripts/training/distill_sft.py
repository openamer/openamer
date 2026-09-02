#!/usr/bin/env python3
"""Distill brain trajectories -> compact SFT dataset (ChatML-style pairs).

Takes full session trajectories (too long for SFT) and cuts them into
small teaching examples: each user message + the assistant answer that
followed, filtered by quality heuristics (length, tool-free, German-friendly).
Output: scripts/training/sft_openamer.jsonl  ({"messages":[...]})
"""
import json, os, random, re

SRC = r"C:/Users/damir/.openamer/a2a/openamer-brain.jsonl"
OUT = r"C:/Users/damir/AppData/Local/openamer-laptop/scripts/training/sft_openamer.jsonl"
MAX_TURN_CHARS = 6000    # cap per example
MIN_ANSWER = 30          # too short = "yes"/"ok" noise
MAX_ANSWER = 4000

pairs = []
for line in open(SRC, encoding="utf-8"):
    d = json.loads(line)
    msgs = d.get("messages") or []
    # find user -> (skip tool msgs) -> assistant pairs
    last_user = None
    for m in msgs:
        r = m.get("role")
        if r == "user":
            last_user = (m.get("content") or "").strip()
        elif r == "assistant" and last_user:
            ac = (m.get("content") or "").strip()
            uc = last_user
            if not uc or not ac:
                last_user = None
                continue
            # skip trivial
            if len(ac) < MIN_ANSWER or len(ac) > MAX_ANSWER:
                last_user = None
                continue
            if len(uc) < 3 or len(uc) > 4000:
                last_user = None
                continue
            if not ac:
                last_user = None
                continue
            if uc.startswith("[") and any(uc.startswith(s) for s in (
                    "[System note:", "[CONTEXT COMPACTION",
                    "[IMPORTANT: You are running as a scheduled cron job")):
                last_user = None
                continue
            # trim very long contexts: keep last 3000 chars of user msg
            if len(uc) > 3000:
                uc = uc[-3000:]
            pairs.append({
                "messages": [
                    {"role": "system", "content": "Du bist OpenAmer Agent - ein autonomer KI-Agent auf Damirs Windows-Laptop. Antworte praegnant, ehrlich, mit echten Beweisen (Tests/Tool-Output). Deutsch im Chat, Englisch im Code."},
                    {"role": "user", "content": uc},
                    {"role": "assistant", "content": ac},
                ]
            })
            last_user = None

# dedupe by (user, first 100 of answer) — but keep distinct multi-turn repeats
# (a repeated greeting with DIFFERENT answers is real signal, not noise)
seen, uniq = set(), []

# Dream-weighting: recurring error motifs (3+ nights) get DUPLICATED in the
# training set so the model sees them more often — bio-inspired: the brain
# strengthens neural paths for things that repeat. One-shot motifs stay 1x.
try:
    dreams = json.load(open(os.path.join(os.path.dirname(os.path.dirname(DATA)),
                                         "..", "dreams.json"), encoding="utf-8"))
except Exception:
    dreams = []
motif_weight = {}
for dream in dreams:
    for ins in dream.get("insights", []):
        m = ins.get("motif")
        if m:
            motif_weight[m] = motif_weight.get(m, 0) + 1
# threshold: recurring nightmare = 3+ nights → weight 3x in training
NIGHTMARE_THRESHOLD = 3
weighted_motifs = {m: NIGHTMARE_THRESHOLD for m, c in motif_weight.items() if c >= NIGHTMARE_THRESHOLD}

for p in pairs:
    key = (p["messages"][1]["content"][:120], p["messages"][2]["content"][:100])
    if key in seen:
        continue
    seen.add(key)
    uniq.append(p)
    # nightmare duplication: check if the answer mentions a recurring motif
    ans_lower = p["messages"][2]["content"].lower()
    for m in weighted_motifs:
        if m in ans_lower:
            # duplicate the pair (model sees nightmares 3x)
            uniq.append(p)
            break

random.seed(42)
random.shuffle(uniq)
os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w", encoding="utf-8") as f:
    for p in uniq:
        f.write(json.dumps(p, ensure_ascii=False) + "\n")

print(f"distilled pairs: {len(uniq)} (from {len(pairs)} raw)")
print("avg answer chars:", sum(len(p['messages'][2]['content']) for p in uniq) // max(len(uniq), 1))
