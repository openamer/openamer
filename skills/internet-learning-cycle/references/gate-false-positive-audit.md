# Gate false-positive audit — run this BEFORE proposing any gate change

Companion to `rejection-triage.md` §3. §3 answers *which rule* killed a candidate.
This file answers the next question, which is the only one that justifies a patch:
**would tightening/loosening that rule destroy already-stored knowledge?**

Never propose a gate edit on the strength of a rejected candidate. Two predicates
that agree on the audit trail can differ completely on the *stored* corpus, and the
stored corpus is what the LoRA trains on. A single rejection is a sample of one.

## The two-sided replay (no model calls, seconds to run)

Pick the candidate predicate `P` (e.g. `_is_nav_list`, `_is_junk`,
`_has_alpha_signal`). Then measure BOTH sides:

**Side A — false-positive floor: replay the STORED corpus through `P`.**
```python
import json, re, sys; sys.path.insert(0, 'scripts/training')
import internet_learner as il
buf = [json.loads(l) for l in open("scripts/training/online_buffer.jsonl",
                                   encoding="utf-8") if l.strip()]
killed = [r["a"] for r in buf if il._is_nav_list(r["a"])]
prosey = [a for a in killed
          if il._VERB_RE.search(a) and len(re.findall(r"\b[a-z]{3,}\b", a)) >= 8]
print(f"stored={len(buf)} killed={len(killed)} prosey={len(prosey)}")
```
A **sound** predicate must kill **0** stored rows that carry a verb plus >=8
lowercase words — that is the shape of real prose. Any survivor here is a false
positive and a hard veto: the gate is already destroying knowledge, and the fix is
to narrow `P`, not to touch the reject path.

**Side B — true-positive yield: replay the audit trail through `P`.**
```python
rows = [json.loads(l) for l in open("scripts/training/buffer_junk.jsonl",
                                    encoding="utf-8") if l.strip()][-4000:]
hits = [r for r in rows if il._is_nav_list(str(r.get("a") or ""))]
```
Then **hand-read every survivor**, not just the count. Score each on
`_VERB_RE` + lowercase-word density and read the top ones yourself. The decision:

- survivors are all reasoning-trace leaks / `Self-critique:` stubs / site nav
  → `P` is earning its keep, keep it, **no patch**;
- survivors include genuine prose the gates wrongly killed
  → now you have a real bug, and Side A tells you how much room you have.

`buffer_junk.jsonl` is a SHARED store (see `rejection-triage.md` §2) — filter by
the `u` question-prefix before quoting a ratio, or the denominator is wrong.

## Worked example — 21.09.26, `_is_nav_list` on `cycle_d_docs`

Measured: stored 202, **killed 0**, prosey 0 → no false positives on the corpus.
Audit trail, last 4000 rows: **73** killed, of which 17 scored "prosey" by the
verb/lowercase test. Hand-reading all 17: every one was a leaked reasoning trace
(`"Here's a thinking process: 1. **Analyze the User's Request:**..."`), a
`Self-critique:` stub, a `Need formulate. Maybe mention:` scaffold, or site nav
(a `Sign in - Claude — FAQ` footer). Zero genuine knowledge lost.

Verdict: **keep the predicate, patch nothing** — the rejection was a true positive.

### The mechanism worth recognising on sight: "headline with no comma"
The rejected candidate was an article lede fused to its read-time header:
`Best vLLM Optimization Guide: VRAM, Quantization, … — 18. Aug. 2026 · Learn how to
improve tokens per second…`. `_clean_insight` ran
`_strip_trailing_read_time_header`, which stripped the header and left
`Inference Serving Time to First Token: What Actually Determines LLM API Latency
Time to first token dictates how fast your AI product feels…`, which `_is_nav_list`
then killed.

Read that as a **chain, not a bug**: `_is_nav_list` fires on >=6 TitleCase words
with **no comma/semicolon**. A title-plus-lede fused fragment is exactly that shape
— capitalised headline words, then prose with its punctuation already eaten by the
strip helpers. So a two-helper chain (strip → nav-list) is the usual cause of a
"mysterious" `no-tech-signal`/`junk` reject on a docs cycle. Attribute a chain by
replaying the strip helpers **in `_clean_insight` order** on the raw candidate and
printing the length at each step — the step that shortens the string is the culprit,
and `_is_nav_list` is only the verdict at the end.

## Where the lever actually is

When Sides A and B are both clean, the reject rate is a **source** problem, not a
gate problem. 21.09.26, all 8 sources: 233 cycles, 98 stored (42 %), reject rate
31→72 % over the week, while the novelty-ledger ratio was 800 lines / 177 unique
(`rejection-triage.md` §1b) and the buffer sat at 202 of 300 — i.e. not a cap
artifact. Shared bottleneck: the HN Algolia headline pool that `_fresh_headline()`
draws from. The lever is **adding sources** (arXiv listing pages, HF papers, docs
changelogs) — report that, do not tune gates. Consistent with the standing rule in
`rejection-triage.md` §5 and root cause AG in `internet-learner-stall-fix`.

## Replay hazards — two ways Side A lies to you

Both of these produced a phantom "gate is destroying knowledge" reading on
21.09.26 before being caught. Neither was a real bug. Run this checklist on the
Side-A number before letting it become the hard veto.

### Hazard 1 — standalone replay of a CONJUNCTIVE predicate invents false positives
A predicate that is only *consulted* under an extra guard must be replayed **with
that guard**, or it scores rows the live pipeline would never show it.

Measured: `_has_alpha_signal` called bare over the 205-row stored corpus flagged
**130 killed / 90 "prosey"** — an alarming FP count. But at its call site it sits
behind `if len(t) < 90 and not _has_alpha_signal(t):` (the short-fragment guard).
It only ever sees sub-90-char strings; fed full prose it trivially "fires".
Replayed faithfully (pipeline order, guard included) the count collapses to
**7 killed / 1 prosey**.

Rule: before trusting a Side-A FP count, `grep -n '<predicate>('` and copy every
boolean/`len()` condition from the call site into the replay. In `_clean_insight`
the order is fixed and non-negotiable:
```python
if len(t) < 20 or _is_junk(t):                 return ""
if _is_nav_list(t):                            return ""
if len(t) < 90 and not _has_alpha_signal(t):   return ""
```
Replay in exactly that sequence; a predicate measured out of position is not
evidence.

### Hazard 2 — a Side-A hit is not automatically a false positive; the corpus may BE the leak class
Stored rows are a *sample of what was kept*, not a sample of prose. Some retained
rows are known-leak legacy rows that a class comment deliberately documents.

Measured: `_is_junk` flagged 3 of 205 stored rows. That looked like data loss —
until the sub-predicate was printed: `_is_platform_sdk_family_weld` (class 126),
and all 3 rows were the `youtubei-*` SDK-family weld *itself* (the same page
deep-read 3× with drifted wording, which is exactly why `_is_duplicate` could not
catch it). The regex comment above it already records 10 hits over 7.9 MB, all
that leak, **0 false positives**.

Rule: print WHICH sub-predicate fired before scoring anything —
```python
preds = [n for n in dir(il) if n.startswith("_is_") and callable(getattr(il, n))]
fired = [n for n in preds if n != "_is_junk" and getattr(il, n)(t)]
```
then read the class comment above that regex. If the stored rows match the leak
class the comment describes, the gate is correct and the *corpus* is the FP sample
— patch nothing.

### Consequence for the report
A gated cycle whose cause survives both sides stays clean (Side A 0 real FPs,
Side B survivors all trace-leak/nav chrome) **and** with the headline pool live and
the novelty ledger at saturation (800 lines / 177 unique) is the documented
source-exhaustion case — the normal ~57 % at a 5-min cadence, not an incident.
Report `[SILENT]`; do not file a gate finding per tick. Verify the pool is live
before concluding exhaustion, else you risk mislabelling the old degenerate-pool
bug as exhaustion:
```python
import random; random.seed(7)
print([bool(il._fresh_headline("LLM agents", avoid)) for _ in range(6)])
```
All-False over fresh seeds means the pool is degenerate (root cause AG) — that is a
real bug, and the opposite verdict.
