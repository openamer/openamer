# A stored row is not a GOOD row (non-English distillate defect, 23.09.26)

**CLASS NUMBER: UNVERIFIED — do not cite one.** The instinct is to number this
`class 164`, but that is a COLLISION: this project's class numbers are NOT a
unique key, and prior cron rounds already took 164 (161 also collided -> 162).
The collision check is `grep -o 'class [0-9]*'` over ALL class lists including
the **uncommitted git diff** (a foreign claim is only visible there), and it
could not be run in the session that wrote this file. So this entry is named
descriptively. Grep first, assign a number second.

## Symptom

`internet_learner.py --once` reports SUCCESS — `security-learn:
Anwendungsmöglichkeiten: Einen Sekretariats-Agent für Erreichbarkeit, ...` — and
the row is really written to `online_buffer.jsonl`, yet the example is WRONG: a
German Azure call-center paragraph welded to an unrelated ENGLISH `u`
(`Security learning (jailbreak prevention ...)`,
`Latest research insight: Open-sourced jev architecture ...`).

So "did the cycle accept?" and "did the cycle learn something good?" are two
different questions. An accept-rate census (SKILL.md, "Measure health BEFORE
calling it a stall") answers only the first.

## Root cause

The SECONDARY extraction door — `deep_learn` -> smart_route,
`internet_learner.py` ~L5860 (`LIVE + "/v1/chat/completions"`, `model:
mini-openamer`, prompt "Distill the ONE most valuable technical insight ...
Start with [INSIGHT]"). The distill prompt does **not** constrain the LANGUAGE,
so when the routed model answers in the page's own language the distillate is
stored as-is. The fallback below it is local Ollama
(`qwen3.5:4b-q4_K_M`, port 11434) with the same unconstrained wording.

## Measurement (all 300 buffer rows, 23.09.26)

- `a` with >=3 German marker tokens: **2 of 300** — both the same call-center
  paragraph, both under a thematically foreign `u`.
- `a` appearing under MORE THAN ONE distinct `u`: 10. Most are LEGITIMATE
  cross-`u` repeats (the vLLM doc page repeats ~5x/day inside one rolling
  window). Only 2 are the defect. Do not read "10" as 10 defects.
- The identical `Sekretariats-Agent` string had already been REFUSED **15x** in
  `buffer_junk.jsonl` (every one logged `reason: duplicate`), and appears **5x**
  in `internet_learn_log.jsonl` spanning 15.09.26 .. 23.09.26, the early ones as
  `doc-learn`/`domain-learn`. Same page, new `u` each time -> it slips past the
  exact-match duplicate gate whenever the question drifts.

## The two obvious fixes are ALREADY SPENT — do not re-ship them

Both are measured-and-rejected in-repo. Shipping either is a regression:

1. **A language rule.** Forbidden by the class around the Chinese Q&A-portal
   detectors (`_is_qa_portal_chrome`, `buffer_store.py` ~L871): "Keyed on the
   portal's own LABEL CHAIN, never on the language ... a language-agnostic 'is
   CJK' rule, which would have eaten that real knowledge, is deliberately NOT
   used." Measured 16.09.26 over the live 5013-row corpus: the two genuine
   Chinese technical rows carried no marker and stayed learnable. Keying on
   language eats those too.
2. **A near-duplicate rule keyed on `a` alone.** Measured-and-rejected at
   `buffer_store.py` ~L3641: "the sentence DRIFTS, so exact `_is_duplicate`
   missed it; same-`u` Jaccard MEASURED-AND-REJECTED, 0.24-0.33 vs a legitimate
   0.40". A naive `a`-based dedupe would now delete the real vLLM doc cycles in
   order to save 2 rows.

## Honest state

The defect is REAL and MEASURED at 2/300; both cheap predicates are spent. The
next attempt needs an `a`-**drift-tolerant** match (same page's `a` under a
DIFFERENT `u`) **with a control** proving it spares the legitimately-repeating
vLLM rows. Do NOT ship a rule on 2/300 alone. 2/300 is also the honest number to
report — it is not a crisis and must not be rounded up.

## Related, do not re-open

- **class 160** (`is_off_topic_page`) — same FAMILY (a result PAGE that does not
  belong to its query), different mechanism: 160 rejects at the gate, this
  defect is let through by the LLM fallback.
- **root cause AG** (`deep_learn` ranks the WRONG page) — deliberately
  unpatched; this names the same function's second door, not a reason to re-open
  AG.

## Where a new class is normally recorded

Per-class narratives belong in the `internet-learner-stall-fix` skill's
`references/root-causes-archive.md`, which is **LF-native** — append with a
BINARY `'ab'` write (a CRLF append flips ~60 lines; verify `count(b'\r\n')` is
unchanged afterwards). NOTE: that skill is **user-owned**, so an autonomous
curator pass CANNOT write it — the write is refused. Record the finding here and
surface `openamer curator adopt internet-learner-stall-fix` in the reply so a
future session can promote it.
