# KTA Cycle: Observed Behavior (live 10.09, re-measured live 12.09)

## How to verify a KTA cycle actually ran (rotation-prediction recipe, live 12.09)

`knowledge_to_action.py` is a **fire-and-forget script with a one-line stdout** — that
single line is easy to lose (piped through `tail`, swallowed by a cron wrapper, or
truncated by a terminal outage). Do NOT verify by counting log lines: `kta_log.jsonl`
is heterogeneous (see "Log format traps" below) and the counter grows by 1 **or 2**
per cycle depending on the experiment.

The reliable three-step check, in this order:

1. **Read `.kta_rotation` BEFORE running** (`scripts/training/.kta_rotation`, a bare
   integer, no newline).
2. **Predict the experiment before you run it** — `EXPERIMENTS[n % len(EXPERIMENTS)]`
   with the list order in the file: `[0]=experiment_lora_rank`,
   `[1]=experiment_predict_world`, `[2]=experiment_tune_buffer`,
   `[3]=experiment_competitor_gap`, `[4]=experiment_meta_insight`.
   **Verified twice live 12.09**: `n=461 % 5 = 1` → ran `predict_world` ✓;
   `n=462 % 5 = 2` → ran `tune_buffer` ✓. So rotation 460 → lora, 461 → predict,
   462 → buffer, 463 → competitor, 464 → meta.
3. **After the run: `tail -1 kta_log.jsonl`** and assert the `experiment` field equals
   your prediction. A mismatch (or an unchanged rotation) is the only reliable
   signal that the cycle errored — the error is swallowed into the entry's `result`
   field (`error: ...`) by the try/except at the call site, so it still logs and
   still prints as if it worked.

`.kta_rotation` increments **before** the experiment function is invoked
(`write` happens, then the try/except), so rotation = **attempts**, log = **results**.
A rotation delta with no new log line means the process died between the two writes.

## Log format traps (live 12.09)

- **`experiment_meta_insight` writes TWO lines per cycle**: a `{"type": "meta_lesson", ...}`
  row (from the inner `log()` call in the function) **plus** the normal experiment entry.
  Any "log grew by exactly 1" assertion breaks on every 5th cycle.
- **`meta_lesson` rows carry NO `ts` field** — they are the only rows in the file without
  one (the normal entry path stamps `ts`, the inner call does not). A consumer that
  sorts/filters/dedupes by `ts` must tolerate a missing key or it crashes / silently
  drops those rows. `session_outcome.py`'s `_already_reported`-style "compare the last
  log entry" checks must therefore key on something that exists on both shapes.
- **Don't parse the file by line index** for recent state — always `tail` + JSON-parse
  the LAST line, since the file is append-only from multiple producers.

## Baseline measurements from 397 runs over 6 days

### Rotation state
- `.kta_rotation` counter at 329 (monotonically incrementing across all experiments)
- 5 experiments rotate round-robin: `experiment_lora_rank`, `experiment_predict_world`, `experiment_tune_buffer`, `experiment_competitor_gap`, `experiment_meta_insight`

### Stagnation pattern
Every experiment returns the **exact same result** on every invocation:

| Experiment | Output | Status |
|---|---|---|
| `experiment_lora_rank` | `"current server: 9 tools, loss history in meta_state"` (or `"server down"` on :8081 dead) | Static — hardcoded health check |
| `experiment_predict_world` | Latest world-model edge text (always changes slightly as new edges form) | Dynamic but derivative — reads `_load()[-1]` and re-wraps it |
| `experiment_tune_buffer` | `"buffer at cap 300 — trim enforced on every write"` (`measurable: true`) | Static — cap constant, no growth signal |
| `experiment_competitor_gap` | `"OpenHands has a modular SDK design — our tool_server.py is monolithic"` | **Identical string for 397 runs** — hardcoded |
| `experiment_meta_insight` | `"Meta-RL insight: replay=3 vs fresh=1 uses. Boosting exploration..."` | **Identical for 397 runs** — counters never increment |

### Root causes
1. **`experiment_competitor_gap`** — the `insight_analyzed` field varies (it shows whichever URL happened to be in the buffer), but the `identified_gap` / `proposed_fix` are hardcoded strings. The function never parses the insight to derive a new gap.
2. **`experiment_meta_insight`** — `meta_state.json` `strategy_stats.replay.uses = 3` and `strategy_stats.fresh.uses = 1` are stuck. These counters are presumably supposed to increment as strategies are selected, but no code path writes back to them. Result: the exploration-boost lesson fires every time.
3. **`experiment_tune_buffer`** — buffer re-measured live 12.09 at exactly 300 (cap 300) with `buffer_store.enforce_cap()` returning 300; the cap now really is enforced on every write (the 10.09 "near cap, meta_learn will trim" wording is superseded — the writer-side choke point landed, see the "buffer is TRAINING DATA" section of SKILL.md). It stays static because the buffer is at steady state, which is correct behaviour, not a bug.
4. **`experiment_lora_rank`** — just pings `:8081/health` for tool count. Doesn't actually measure LoRA performance (that requires GPU training, which doesn't run on laptop).

### `experiment_predict_world` amplification — the `If '…' recurs` prefix defeats world-model dedupe (mechanism, live 12.09)

This is the one experiment that produces new persistent state per cycle, and that is
exactly why it needs watching. It reads the newest edge (`_load()[-1]`) and writes a
NEW edge with the cause text wrapped:

```
fact  edge:  cause="Competitor update: Devin AI agent new features 2026"
             effect="OpenAmer should evaluate: Recent Updates - Devin Docs — …"
             dup_count=2, last_seen=<refreshed>      ← observe() deduped it correctly
prediction:  cause="If 'Competitor update: Devin AI agent new features 2026' recurs"
             effect="expect: OpenAmer should evaluate: Recent Updates - Devin Docs — …"
             confidence=0.6                          ← brand-new row, every cycle
```

`world_model.observe()` dedupe keys on the **cause string**, and the `If '…' recurs`
prefix guarantees the prediction never matches the original edge — so predictions
accumulate **one row per predict_world cycle** (304 edges total live 12.09) and each
new one is derived from whichever edge another producer happened to append last
(here: a competitor fact from the internet learner). Two consequences worth knowing
before "improving" the loop:

- The chain is **self-referential and unbounded**: nothing caps prediction depth, and a
  prediction edge can itself become the `_load()[-1]` input on a later cycle.
- Recall quality degrades quietly — derivative rows dilute nearest-neighbour results
  without any error surfacing anywhere. If prediction edges ever dominate the store,
  fix it at the experiment (dedupe on the *underlying* cause, or cap `kind="prediction"`
  rows), not at recall time.

### What the loop DOES actually achieve
- `experiment_predict_world` adds a real PREDICTION edge each time (the only experiment that produces new state — and note the amplification caveat above)
- The round-robin mechanism prevents the same experiment from dominating
- The KTA log serves as a health baseline (:8081 availability, buffer size trend, world-model count)

### Design implication
The "action → measure" loop is currently a **health monitor with a prediction append**, not a true closed-loop experiment system. The experiments are placeholders for where the real experiments go once GPU capacity, adaptive insight parsing, and self-modifying code become available. The architecture is correct — the implementation is still at the scaffolding stage.

## Reporting a cycle (delivery contract)

For a cron whose job is "run one cycle and report which experiment ran + its result in
one line", the report should carry: experiment name, the `result` field verbatim,
whether it was `measurable: true`, and the rotation delta as proof it ran. State the
measured values (buffer 300/cap 300, edge count) rather than adjectives — and do not
claim a closed loop; `competitor_gap` / `meta_insight` / `lora_rank` are static
strings, so reporting them as "experiments" without that caveat overstates the result.
