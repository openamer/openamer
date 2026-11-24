---
name: asi-core-integration
description: 'Use when building or extending ASI Core native tool layer.'
---

# ASI Core Integration — Native Tools, Not External Scripts

## Purpose

The ASI Core (`tools/asi_core.py`) wraps all 16 ASI capabilities as native agent tools with a unified lifecycle. Instead of calling `python scripts/training/xxx.py` as external processes, the model interacts through registered tools: `asi_status`, `asi_think`, `asi_learn`, `asi_remember`, `asi_trigger`.

## Architecture

```
tools/asi_core.py          ← Main module: ASICore class + tool registrations
  └── tools/asi/            ← Subsystem subpackage (direct imports, no subprocess)
       ├── __init__.py      ← Imports all subsystems
       ├── self_model.py    ← Wraps scripts/training/self_model.py
       ├── world_model.py   ← Wraps scripts/training/world_model.py
       ├── reasoning.py     ← Wraps scripts/training/reasoning_loop.py
       ├── prediction.py    ← Wraps scripts/training/predict_validate.py
       ├── improvement.py   ← Wraps scripts/training/self_improve.py
       └── heartbeat.py     ← Central ASI Heartbeat (10 subsystems, 104 legacy jobs)
```

### Layer 1: ASICore — Native Tools

Each capability now calls the training script's **core functions directly via import**, not subprocess. The script files still exist and work standalone (for cron/legacy), but the ASICore bypasses them:

```python
# BEFORE (subprocess bridge — now obsolete):
import subprocess
subprocess.run([sys.executable, "scripts/training/self_model.py"])

# AFTER (direct import):
from tools.asi import self_model as asi_self_model
state = asi_self_model.gather_state()
```

### Layer 2: ASI Heartbeat — Unified Lifecycle

Replaces 104 separate cron jobs with a single `tools/asi/heartbeat.py` module and one cron job (`asi-heartbeat-tick` every 5 min).

```
Heartbeat ─┬─ darwin    (every 15m) — Evolution, Grid, AutoPatch, Publish, Probe
           ├─ swarm     (every 30m) — Swarm Intelligence, Autonomous Loop
           ├─ a2a       (every 240m) — Brain Export, Peer Communication
           ├─ learning  (every 5m) — Internet Learner, Active Learn, KTA, etc.
           ├─ senses    (every 30m) — Circadian, Watchtower, Trend Scout
           ├─ system    (every 5m) — Self-Healer, Resource Monitor, Traffic Cop
           ├─ security  (every 240m) — Bugbot, CVE Scan, Pen Tester, Code Review
           ├─ outreach  (every 180m) — Social, GitHub, Growth Report, Funding
           ├─ infra     (every 30m) — Env Check, Browser, Plugin, Mesh, Cache
           └─ meta      (every 60m) — Reflection, Self-Rewriter, Goal, Research
```

Each subsystem stores its last-run timestamp in `memory/asi_heartbeat.json` for process-persistent state across cron ticks. The `tick()` method checks `is_due()` before executing — subsystems only run when their cadence timer has elapsed.

## Registered Tools

| Tool | Emoji | Schema | Purpose |
|---|---|---|---|
| `asi_status` | 🧬 | `ASI_STATUS_SCHEMA` | Full ASI system status + Heartbeat subsystem health |
| `asi_think` | 🧠 | `ASI_THINK_SCHEMA` | Deep recursive reasoning (in-process) |
| `asi_learn` | 📚 | `ASI_LEARN_SCHEMA` | Internet learning cycle (in-process) |
| `asi_remember` | 💭 | `ASI_REMEMBER_SCHEMA` | Episodic memory + world model recall (in-process) |
| `asi_trigger` | ⚡ | `ASI_TRIGGER_SCHEMA` | Fire any specific capability + Heartbeat tick |

`asi_trigger` accepts a `capability` enum with 17 values (incl. `heartbeat`) and optional `params` dict. The `heartbeat` capability calls `get_heartbeat().tick(system=params.get('system'), force=params.get('force'))` to run the central ASI Heartbeat.

`asi_status` now also shows the Heartbeat subsystem states (10 subsystems with their cadence and due-status).

`asi_trigger` accepts a `capability` enum with 16 values and optional `params` dict. The `method_map` dict in the handler routes each capability to the correct ASICore method.

## Toolset Integration

Add to `toolsets.py`:

1. Define the `"asi"` toolset:
```python
"asi": {
    "description": "Integrated ASI Core — 16 capabilities...",
    "tools": ["asi_status", "asi_think", "asi_learn", "asi_remember", "asi_trigger"],
    "includes": []
}
```

2. Add tools to `_OPENAMER_CORE_TOOLS` (or per-platform toolset):
```python
"asi_status", "asi_think", "asi_learn", "asi_remember", "asi_trigger",
```

## Registry Integration

The module auto-registers via `registry.register()` at module level:

```python
from tools.registry import registry

registry.register(
    name="asi_status",
    toolset="asi",
    schema=ASI_STATUS_SCHEMA,
    handler=handle_asi_status,
    check_fn=check_asi_requirements,
    emoji="🧬",
)
```

The `check_fn` verifies `scripts/training/` exists. Discovery is automatic — `discover_builtin_tools()` finds the file because it contains `registry.register(` at the top level.

## Pitfalls

- **Import order**: The `tools/asi/` subpackage must import before `asi_core.py` calls subsystem methods. Module-level registration handles this (Python import system ensures subpackage init runs first).
- **Script legacy**: Old scripts in `scripts/training/` are still used by legacy cron jobs and subprocess fallback. Don't delete them until all cron jobs migrate to the Heartbeat.
- **Heartbeat state file**: `memory/asi_heartbeat.json` is written by the cron `asi-heartbeat-tick` job and read by `asi_trigger(capability='heartbeat')`. If a subsystem's `last_run` is stale, it will run on the next tick. Corrupted state → delete file, subsystems reset to "never run".
- **Timeout**: The subprocess fallback (for scripts that can't be imported directly) has a 120s timeout. Most subsystems now use direct imports and are instant.
- **State loading**: `_load_state()` reads `memory/self_model/current_state.json`. If the file is missing or corrupt, it returns defaults.
- **Singleton**: `get_asi_core()` returns a module-level singleton. Do not instantiate `ASICore` directly outside this pattern.
- **Tool visibility**: Tools only appear after the module is imported. The registry's `discover_builtin_tools()` handles this automatically on agent start.
- **Heartbeat ticks**: The cron job runs every 5 min, but each subsystem only fires when its cadence timer has elapsed. A 5-min tick with no due subsystems produces no work — that's correct.
