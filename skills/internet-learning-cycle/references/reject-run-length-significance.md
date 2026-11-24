# Is a reject-run a STALL? — run-length significance test

Measured 13.10.26 (cron, `internet_learner.py --once`). Companion to SKILL.md
§"Measure health BEFORE calling it a stall" and
`references/signal-vs-regression-triage.md`.

## The trap this closes

The SKILL.md rule says "measure the accept rate first" — but the accept rate
alone does **not** answer the question a cron run actually faces:

> I just ran 5 cycles and every one was `rejected, not trained
> (shallow + deep read both gated)`. Six rejects in a row including the one
> before mine. Is the learner stalled?

Eyeballing "6 in a row" reads as alarming. It is not. With the measured
`p_reject ≈ 0.48` and ~137 cycles/day, the **expected longest reject-run** is
about 6 — so a run of 6 is the single most likely outcome of a normal day.
Filing a gate candidate or patching a gate on that signal is a *signal-reading
error* (the class triaged in `references/signal-vs-regression-triage.md`).

## Decision rule

Run the length test, not the eye test. Reject a stall claim when
`P(longest run >= observed) > 0.1`.

| quantity | source |
|---|---|
| `n` | today's rows in `scripts/training/internet_learn_log.jsonl` |
| `p_reject` | today's rejected rows / n (`"rejected" in result`) |
| observed longest run | longest consecutive today-rows with `"rejected" in result` |
| significance | 20k-draw simulation of `n` cycles at `p_reject` |

`scripts/reject_run_significance.py` implements this — run it, don't hand-roll.

## Measured reference point (13.10.26)

```
today: 137 cycles, 67 rejected (p_rej=0.489), 70 accepted
longest reject-run observed today: 6
sim @ p=0.489 over 137 cycles: mean longest run=6.26, median=6, P(run>=6)=0.623
=> 62nd percentile of what today's volume produces. NORMAL. No gate touched.
```

A run of 6 is the *median* day. Only a run materially above the simulated mean
(≈ 9+ here) starts to justify investigation. Cross-check the *time-scoped*
accept rate too: today 70/137 = **51 % accepted**, matching the multi-day
baseline (~48 % reject) — the definitive "not a stall" number.

## Where the reject REASON lives (`buffer_junk.jsonl`)

`store()` audits every refusal with a `reason`. Schema is exactly
`{reason, u, a}` — **no timestamp field**. Reasons:
`junk` (page chrome), `no-tech-signal`, `writer-gate`, `duplicate`.

Consequence: `tail -100 buffer_junk.jsonl` is a **row-scoped** window, NOT a
time window. Never read "writer-gate = 32 % of the last 100 audit rows" as
"writer-gate is rising right now" — those rows may span many hours. To make a
*time-scoped* claim, use `internet_learn_log.jsonl` (has `ts`) to pick the
window, then join by query text (`u`).

Observed split that looks alarming but matched baseline: last-100 audits →
duplicate 51 %, writer-gate 32 %, junk 14 %; all-history → duplicate 48 %,
junk 36 %, writer-gate 11 %. The row-scoped window over-weights recent
duplicate-heavy cycles; the day's overall reject rate was dead-on baseline.

## Do NOT

- Do not treat a reject-run as a stall without the length test.
- Do not patch a gate on a cluster signal alone (half-applied gate = AV trap,
  see SKILL.md). File in `references/pending-candidates.md` instead — and only
  after `P(run >= observed) <= 0.1`.
- Do not time-slice `buffer_junk.jsonl` (no `ts`).

## Reporting one line for a gated cron run

Per `references/learning-cycle-reporting.md`: a gated cycle means no
`*-learn:` prefix was stored → report the gated outcome honestly, give the
one-line health measurement (n, accepted %, longest-run percentile), and cite
the freshest *verified* stored insight if you want substance (read the buffer,
not the truncated log headline).
