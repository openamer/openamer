# Reject triage, retry count, and the second process on `.il_rotation` (16.10.26)

Cron run 16.10.26 03:01–03:05. Entry state: `cycle_b_papers: rejected, not trained
(shallow + deep read both gated)`. Outcome: 3 invocations → 1 learned, 2 rejected.

## One invocation is NOT the rotation — run 2–3 before reporting "nothing learned"

`next_cycle()` advances `.il_rotation` by ONE per invocation and picks
`CYCLES[n % 8]`, so a single gated reject says nothing about the other seven
sources. Measured, three chained `--once` calls:

| invocation | cycle | result | elapsed |
|---|---|---|---|
| 1 | `cycle_b_papers` | rejected (both gated) | 84.0 s |
| 2 | `cycle_d_docs` | rejected (both gated) | 51.6 s |
| 3 | `cycle_e_competitors` | **learned** (stored) | 49.9 s |

Stopping after invocation 1 would have produced a false "the learner is dead"
report. Rule: retry until you have seen **≥2 distinct outcomes or 4 invocations**,
then report the mixed result (e.g. "2 gated rejects, 1 learned"). Do not report a
single rejection as the cycle's outcome, and do not re-run until success either —
the value is the honest mix.

## Identify YOUR cycle in the log — a second learner process writes too

At 03:01:52 the log gained `cycle_b_papers` (84.0 s, mine) and at **03:02:01**
`cycle_c_github` (57.9 s, a *different* process — the ~30-min learner cron, which
had started at 03:01:03). The tail of `internet_learn_log.jsonl` is therefore not
necessarily "my last cycle". Match on **`ts` AND `elapsed_s`** (the wall time your
own terminal call measured) before quoting a result. Two processes sharing one
`.il_rotation` counter can also hand you the same cycle twice.

## The standard diagnosis, with the numbers (so the next run can skip it)

`diagnose_learn_rates.py --training-dir scripts/training`:

```
2026-10-10 36.8% | 10-11 40.3% | 10-12 52.3% | 10-13 47.2%
2026-10-14 55.4% | 10-15 64.3% | 10-16 57.1%  (partial day, 8 ok / 6 rej)
```

Inside the documented post-13.09 band **48–68 %** → rotation noise, no gate change
warranted. `wc -l online_buffer.jsonl` = **300 / cap**. Last 30 `buffer_junk.jsonl`
reasons = **23 duplicate / 6 writer-gate / 1 junk** = the documented saturated shape.

Writer-gate census run through the REAL gates (`buffer_store._is_nav_chrome` +
`internet_learner._is_junk`, rows read via `split(b"\r\n")` — never `readlines()`):
**0 writer-flagged**, 7 learner-flagged, of which 6 are the preserved
`Both situations describe …` structural-connection family and 1 is a short
fragment (`Common failure causes.`). Those 7 are baseline — do NOT "clean" them
(it is the 53-row synthesis family, not chrome). A census that returns 7 flagged
rows on an ostensibly clean buffer is the expected reading, not a finding.

## One `u`, several candidate `a`s — writer-gate rows under a stored `u` are extractions, not FPs

`cycle_e_competitors` (u = `Competitor intelligence: OKF Agent Memory …`) wrote
THREE candidates to `buffer_junk.jsonl` for the same query: a SERP title chain
(`GitHub - okf-memory/… — …; OKF Agent Memory is an independent open…`), a
feature-matrix / price-table weld (`Cost Escalation: Wastes 75%+ … OKF Memory
Pattern Progressive Disclosure (In-Memory BM25) 917 Tokens…`), and the one that
was stored. A writer-gate row sharing the `u` of a just-stored row is that query
taking a second extraction path. Read the `a`, not the `u`, before calling it
collateral damage.

## Verify the named artifact before relaying a "learned" line

The stored `a` named a project + repo (`OKF Agent Memory`,
`okf-memory/okf-agent-memory`). One `web_search` returned 5 independent sources
(okf-memory.dev, Hysen Labs, Automations Cookbook, aiindigo, lavx news) → the
attribution is real. If the name does not resolve, report the insight as
**unverified attribution** rather than relaying it as learned (the class-156
hallucinated-query family in the sibling `internet-learner-stall-fix` skill).
Separate the two in the report: the *claim* ("context-window cost/latency from
re-uploading thousands of tokens; progressive disclosure over an in-memory BM25
index ≈ −80 % token overhead") is generic and holds either way; the *attribution*
is what needs the lookup.

## Root-cause-AG rows (deep_learn ranked the wrong page): do not gate, do not clean mid-run

The same run stored `u = Internet learning ('Rogue' Cursor AI agent loses control
and wipes company's database)…` with `a = Amazon Prime customers could get
automatic refunds … - see if you qualify 26 comment s share s Texas good samaritan
found $128,514 in cash…` (a news-aggregator double-headline weld). Both gates read
`False` — as designed: the defect is which PAGE `deep_learn` ranked, not what the
text looks like, so every candidate marker ("news-ness", a promo word, a price)
is a topic word. Leave it: at the 300-row cap the buffer rotates ≈200 rows/day, so
it ages out within about a day, and editing a store with concurrent writers costs
more risk than the one contaminated row is worth. Say so in the report.
