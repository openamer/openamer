---
name: asi-integration-architecture
description: 'Use when integrating ASI as native in-process tools.'
---

# ASI Integration Architecture

Class-level pattern for how ASI capabilities are built into OpenAmer: **native in-process tools, not standalone scripts**. All 104 cron jobs → 1 ASI Heartbeat with 10 subsystem pulses.

## Core Rule

**ASI capabilities are NOT standalone `.py` scripts called via subprocess.** They are native `tools/asi_*.py` or `tools/asi/*.py` modules that:

1. `registry.register()` at module level — same as all other tools
2. Import their core logic from the existing `scripts/training/*.py` via `sys.path.insert` + `importlib.import_module` (no subprocess)
3. Fall back to `subprocess.run()` only when a script has side effects at module level and cannot be imported cleanly
4. Export 1-5 model-accessible tools (asi_status, asi_think, asi_learn, asi_remember, asi_trigger)
5. Are part of the `asi` toolset in `toolsets.py`

## Heartbeat Architecture (replaces 104 cron jobs)

Single `asi-heartbeat-tick` cron job (every 5 min) runs `scripts/asi_heartbeat.py` which calls `tools/asi/heartbeat.Heartbeat.tick()`. Each subsystem has its own cadence:

| Subsystem | Cadence | What it does |
|---|---|---|
| darwin | 15m | Skill evolution, autopatch, publish |
| swarm | 30m | Multi-agent coordination, autonomous loop |
| a2a | 240m | Brain export, peer communication |
| learning | 5m | Internet learner, active learn, self-model, KTA |
| senses | 30m | Circadian rhythm, watchtower, trend scout |
| system | 5m | Self-healer, resource monitor, traffic cop, smart cache |
| security | 240m | Bugbot, CVE scan, pen tester, code review |
| outreach | 180m | Social & GitHub outreach, growth |
| infra | 30m | Browser, env-check, plugin loader, mesh daemon |
| meta | 60m | Self-reflection, self-rewriter, metacognition, goal engine |

State persisted in `memory/asi_heartbeat.json` (last_run per subsystem survives cron process restarts).

## Key Files

| File | Role |
|---|---|
| `tools/asi_core.py` | 5 ASI tools (asi_status, asi_think, asi_learn, asi_remember, asi_trigger) |
| `tools/asi/__init__.py` | Subsystem package namespace |
| `tools/asi/self_model.py` | Self-model — wraps `scripts/training/self_model.py` |
| `tools/asi/world_model.py` | World model — wraps `scripts/training/world_model.py` |
| `tools/asi/reasoning.py` | Recursive reasoning — wraps `scripts/training/reasoning_loop.py` |
| `tools/asi/prediction.py` | Prediction validation — wraps `scripts/training/predict_validate.py` |
| `tools/asi/improvement.py` | Self-improvement — wraps `scripts/training/self_improve.py` |
| `tools/asi/heartbeat.py` | Zentraler Herzschlag mit 10 Subsystem-Pulsen |
| `scripts/asi_heartbeat.py` | Cron-Einstiegspunkt für den Heartbeat |
| `toolsets.py` | `asi`-toolset registriert + Tools in `_OPENAMER_CORE_TOOLS` |

## Pitfalls

- **An organ can be BUILT and still DEAD (orphaned).** A subsystem script that
  runs fine by hand is dead if no cron schedules it AND no subsystem lists it in
  `scripts=[...]`. Found this way: `homeostasis`/`calibration`/`metacognition`
  were runnable but appeared in neither list → never ticked, while
  `last_status: ok` proved nothing. Audit: (1) missing? scan for expected organ
  names; (2) orphaned? check each existing organ appears in a subsystem
  `scripts=[...]` or a cron; (3) wire it in AND raise that subsystem's `timeout`
  if the list grew (observed: `meta` 15 scripts → `timeout=180`, `system` →
  `240`, or the tick cuts the organ off).
- **A TICK must PROBE, never RUN the heavy job.** A subsystem tick runs every few
  minutes; a full filesystem backup in a tick took ~7 min and blew the timeout.
  Split it: the CRON does the labour, the heartbeat runs a light `*_health.py`
  freshness probe (mtime age vs threshold), silent when healthy.
- **A no-arg script invoked bare by a cron must DO the useful thing.** If a new
  organ's `main()` falls through to `print_help()` on no args, its cron is a
  silent no-op (frozen state, `last_status` stays `ok`). Test with ZERO
  arguments and assert it acted, not that it printed usage.
- **`tools/asi/heartbeat.py` has multiple writers** (cron commits/pushes too).
  Confirm no foreign `index.lock` before editing; **never delete a foreign
  `index.lock`**; land changes on a branch rather than a shared `main` other
  crons also push to.
- Full recipe (three-pass audit, probe-vs-run split, wiring table): see
  `autonomous-learning-architecture` → `references/heartbeat-organ-wiring.md`.
- **Do NOT add new external scripts as standalone cron jobs.** Add a subsystem to `tools/asi/heartbeat.py` instead.
- **Direct import over subprocess.** Always try `importlib.import_module` + `mod.function()` first. Fall back to `subprocess.run()` only when import fails due to module-level side effects.
- **State persistence matters.** The heartbeat cron is a separate process each tick. Use `memory/asi_heartbeat.json` for last-run timestamps, not in-memory state.
- **Subsystem cadences must not be shorter than the heartbeat interval** (5 min). Use 5, 15, 30, 60, 120, 180, 240, 360, 720, or 1440 minutes.
- **asi_trigger(capability='heartbeat', params={'system': '...', 'force': true})** triggers heartbeat live during a session.

## The integrated cycle: chaining blocks in ONE run (2026-10-11)

Ticking blocks separately is this architecture's default failure: each subsystem
runs its scripts on its own cadence and **nothing links them**. Measured cost
(live, this laptop):

```
world model:  484 facts | 168 predictions | 0 corrections
calibration:  19/204 correct -> adjustment floored at 0.3
```

The system predicted 168 times and NEVER turned a failed prediction into a
correction — because `training/predict_validate.py` and `training/self_model.py`
were ticked in SEPARATE subsystems, and nothing ever saw a prediction together
with its outcome.

`tools/asi/cognition.py` closes that. ONE `cycle()` run chains

    perceive -> recall -> predict (calibrated) -> score -> correct -> validate -> reflect

and uses **world_model + prediction + self_model in the same pass**. It writes
`kind="correction"` edges — the first corrections this store ever held.

### Native subsystems (no cron behind them)

A subsystem normally derives its scripts from `jobs.json` via `cron_ids`
(`_reconcile_scripts`). An integrated loop has no cron job, and wiring one would
be the cron-wrapper anti-pattern. `Subsystem(native=True)` marks it:
reconciliation skips it, its explicit script list stays, and the script is routed
by `native_map` (`"cognition_cycle.py" -> "tools.asi.cognition.cycle"`).
Register in `_init_subsystems` with `cron_ids=[]`, `native=True`, `timeout=300`.

### Traps the integration exposed (all real, all fixed)

1. **The wrapper did not mirror the real module.** `tools/asi/world_model.recall`
   had no `exclude`; `tools/asi/prediction` exposed `apply_confidence_adjustments`
   while the real module defines `apply_confidence_to_new_predictions`. Nothing
   noticed, because the blocks were never called in a chain. **Chain them and
   their signatures diverge.** Check signatures before wiring.
2. **An edge is always its own nearest neighbour (cosine 1.0).** A first version
   scored 4/4 "hit" at sim=1.0 — it was confirming itself. Fix needs BOTH
   `recall(..., exclude={edge_key})` AND dropping priors whose `ts` is not
   strictly older than the observation; either alone still self-confirms.
3. **`python tools/asi/<module>.py` puts `tools/asi/` on `sys.path[0]`**, so a
   wrapper's `importlib.import_module("<name>")` re-imports ITSELF →
   `RecursionError`. Remove the script directory from `sys.path` first.
4. **`OPENAMER_HOME` must be a native path.** An MSYS `/c/...` value makes every
   `SCRIPTS_TRAINING` lookup miss → `ModuleNotFoundError: world_model`.
5. **A native function called bare by the tick must be safe with no args.** The
   heartbeat calls `cycle()` with nothing; every parameter needs a default.

See `references/cognition-cycle-integration-2026-10-11.md` for the full integration story: the 5 traps discovered (signature drift, self-match, sys.path recursion, OPENAMER_HOME path form, bare-call safety), the native subsystem pattern (`Subsystem(native=True)` + `native_map`), correction path proof (first `corrected: true` in system history), and the canonical repo ship via `scripts/ship.py` with CRLF normalization.

```bash
export OPENAMER_HOME="C:/Users/<u>/AppData/Local/openamer-laptop"    # native!
cd <install>/openamer-agent
./venv/Scripts/openamer.exe asi cycle --status
./venv/Scripts/openamer.exe asi cycle --limit 6                       # autonomous
./venv/Scripts/openamer.exe asi cycle --situation "X" --effect "Y"     # proves the correction path
./venv/Scripts/openamer.exe asi heartbeat --tick --system cognition --force
<laptop-venv>/Scripts/python.exe -m pytest tests/tools/test_asi_cognition.py -q
```

## Verification

```bash
# Test all imports (no subprocess)
cd /c/Users/damir/AppData/Local/openamer-laptop/openamer-agent
python -c "from tools.asi_core import get_asi_core; from tools.asi.heartbeat import get_heartbeat"

# Full heartbeat status
python tools/asi/heartbeat.py --status

# Dry-run one subsystem
python tools/asi/heartbeat.py --tick --system infra --force

# Registry test
scripts/run_tests.sh tests/tools/test_registry.py
```