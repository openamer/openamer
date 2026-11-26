# Beyond Bench — what this install can actually do, measured

Two harnesses live here. Both score with per-task verifiers, so a "pass" is a
computed fact and never an opinion.

| script | question it answers |
|---|---|
| `scripts/bench/run.py` | how good is a **model** on the 10-task catalog |
| `scripts/bench/cross_agent.py` | how good is an **agent** (scaffolded CLI) on the same catalog |
| `scripts/bench/verifier_audit.py` | is the **ruler** right, or only self-consistent |

```bash
python scripts/bench/cross_agent.py --subjects openamer,bare-cloud,npu
python scripts/bench/verifier_audit.py
python -m pytest tests/scripts/test_cross_agent.py -q
```

## Cross-agent subset — 10 tasks, measured 2026-11-26

Catalog signature `389ef7284baec9a2`, temperature 0, host `Emilija`, checkout
`45ef7806`. Full log: `cross-agent-20261126T041537Z.json` / `.md`.

| subject | kind | passed | scored | pass rate | median latency |
|---|---|---|---|---|---|
| `openamer-agent` | agent (`openamer -z`, full scaffold) | 9 | 10 | **90 %** | 15.3 s |
| `bare:minimax-m3.1-flash:cloud` | model only, no scaffold | 10 | 10 | **100 %** | 2.1 s |
| `local-npu` | model only, Qwen3.5-4B on the NPU | 6 | 10 | **60 %** | 3.1 s |

Subset size: **10 tasks**. That is the number, and it is small on purpose — it is
what one laptop can run honestly in four minutes, not a leaderboard.

### What the numbers mean

- The **local 4B core is at 60 %** of a catalog that a cloud model clears
  completely. Its failures are real answers, not transport errors: `10` instead
  of `75`, `5` instead of `6`, a sentence containing `z` under a "no z"
  constraint, `12` instead of `10` marbles.
- The **scaffold did not make the agent smarter on this catalog**: the bare
  cloud model scored higher. The catalog measures single-turn answer quality,
  which is exactly the axis a tool-using scaffold is *not* for. A scaffold can
  only pay off on tasks that need tools; this one does not, and the report says
  so instead of implying the agent is better.
- **Language is a documented confound.** The agent answers in the configured
  interaction language (German here) and its one failure is commentary added
  around a correct sentence ("10 Wörter, enthält recall, kein z") under a
  one-sentence / max-12-words constraint. The bare model answered in English
  with the bare sentence. The verifier is right to reject the extra text; the
  comparison is not language-neutral.

## A verifier defect this harness caught, and the fix

The first run (2026-11-26T04:11Z) scored two independent agents wrong on
`arith.rate.v1`: the task asked for 340 units / 8 h, +15 %, over 10 h — the true
value is **488.75**, the verifier demanded **488**, and both agents answered
**489**. Nobody was wrong except the task, which never said how to round.

- Fixed by making the arithmetic exact: 320 units / 8 h → 460 units, so no
  rounding rule is needed.
- `tests/scripts/test_cross_agent.py` now **recomputes** that expectation with
  `Fraction` instead of trusting the constant, and does the same for the marbles
  task (surplus equals deficit; 10, not 12 — a mistake I made myself in review,
  which is why the test derives it).

The catalog signature changed from `825929d671bd9259` to `389ef7284baec9a2`
because of this fix. Numbers from the two signatures are not comparable, and the
earlier file is kept rather than overwritten.

### The audit that keeps it from happening again

`verifier_audit.py` runs every task through two independent models and flags a
task when both agree on an answer the verifier rejects — the exact shape of the
defect above. Measured 2026-11-26T04:24Z on the corrected catalog: **0 of 10
tasks flagged** (`verifier-audit-20261126T042458Z.json`).

An audit that never fires proves nothing, so `tests/scripts/test_cross_agent.py`
replays the historical defect with stubs: two subjects answering `489` against
the old `488` expectation must produce `flagged:consensus_rejected`, two
answering `488` must not, and a raising verifier must be surfaced as
`verifier_raises`. All three assertions run without a network or a model.

## What this is not

- **Not a SWE-bench Verified score.** No official row exists for this install.
  Measured 2026-11-26: no container runtime on the host (`docker` and `podman`
  both absent), 38 GB free on a 97 %-full disk — the official harness is a
  container workload and cannot run here. A third-party agent arm (Claude Code
  2.1.302) is installed but refused with `Not logged in`, so it could not compete.
  No leaderboard claim is made without a row.
- **Not a rotation-proof ranking.** The catalog is a fixed 10-task set; repeated
  runs measure the same tasks. Treat a single run as one sample, not a trend.
