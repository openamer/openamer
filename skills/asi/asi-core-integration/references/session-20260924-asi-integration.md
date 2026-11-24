# Session: ASI Core + Heartbeat Integration (2026-09-24)

## User Signals

1. *"du kanst ASI in deine sitem integrieren, nicht als seperate .py"* — Integrate ASI into the agent core, not as external scripts.
2. *"du kanst alle cron jobs in deine system integrieren, oder? Wie A2A, Swarm, Darwin"* — All 104 cron jobs should become one integrated system.

Both were architectural corrections from external-script approach to native in-process subsystems.

## What Was Built

### Layer 1: Direct-Import Subsystems (`tools/asi/`)

Replaced the transitional subprocess calls with direct function imports:

| File | What it wraps | Key functions |
|---|---|---|
| `tools/asi/__init__.py` | Package namespace | Imports all 5 subsystems |
| `tools/asi/self_model.py` | `scripts/training/self_model.py` | `gather_state()`, `update_identity()`, `run_cycle()` |
| `tools/asi/world_model.py` | `scripts/training/world_model.py` | `recall()`, `predict()`, `observe()`, `stats()` |
| `tools/asi/reasoning.py` | `scripts/training/reasoning_loop.py` | `recursive_ask()`, `predict()`, `graph_stats()` |
| `tools/asi/prediction.py` | `scripts/training/predict_validate.py` | `validate_predictions()`, `apply_confidence_adjustments()` |
| `tools/asi/improvement.py` | `scripts/training/self_improve.py` | `improve_once()`, `propose_improvement()`, `apply_and_test()` |

Each subsystem adds `scripts/training/` to `sys.path` and lazily imports the core functions via `importlib.import_module()`. The `if __name__ == "__main__"` guards in the original scripts remain intact — scripts still work standalone for cron/legacy use.

### Layer 2: ASI Heartbeat (`tools/asi/heartbeat.py`)

Replaces 104 cron jobs with one central heartbeat + 10 subsystem modules:

| Subsystem | Cadence | Legacy Jobs Replaced | Key Scripts |
|---|---|---|---|
| darwin | 15m | 6 | darwin-cron.py, darwin-grid.py, darwin-autopatch-cron.py, darwin_publish.py, darwin-probe-cron.py |
| swarm | 30m | 5 | swarm_intelligence.py, autonomous_loop.py |
| a2a | 240m | 1 | brain_collect.py |
| learning | 5m | 9 | internet_learner.py, active_learn.py, knowledge_to_action.py, auto_skill_creation.py, self_model.py, predict_validate.py, session_outcome.py, learning-loop.py, morning_brief.py |
| senses | 30m | 5 | circadian.py, senses.py, autonom_watchtower.py, trend_scout.py, self_evolve.py |
| system | 5m | 15 | self-healer.py, resource-monitor.py, smart-cache.py, service-watchdog.py, self-hosted-cron.py, traffic-cop.py, notification-engine.py, identity-watchdog.py, global-sync.py |
| security | 240m | 5 | bugbot.py, cve-scan.py, pen-tester.py, auto-code-review.py, skill-safety-scan.py |
| outreach | 180m | 7 | social-outreach.py, github-outreach.py, growth-report.py, funding-tracker.py, autonom-growth.py |
| infra | 30m | 14 | env-checker.py, ab-test.py, model-sync.py, token-harbor-watchdog.py, gpu-worker-watchdog.py, plugin-loader.py, browser-watchdog.py, stealth-server.py, wiki-generator.py, deepseek-import.py, hub-cache.py, mesh-daemon.py, context-compressor.py, file-organizer.py |
| meta | 60m | 37 | self-reflection, self_improve.py, goal-engine.py, domain_mastery.py, self-directed-research, cross-domain-synthesis, tool-invention, model-benchmarker.py, asi-audit, dream-cron.py, provenance_cleanup.py |

### Files Created/Modified

| File | Type |
|---|---|
| `tools/asi_core.py` | Refactored — direct imports instead of subprocess |
| `tools/asi/__init__.py` | New — subpackage namespace |
| `tools/asi/self_model.py` | New — direct-import wrapper |
| `tools/asi/world_model.py` | New — direct-import wrapper |
| `tools/asi/reasoning.py` | New — direct-import wrapper |
| `tools/asi/prediction.py` | New — direct-import wrapper |
| `tools/asi/improvement.py` | New — direct-import wrapper |
| `tools/asi/heartbeat.py` | New — central Heartbeat with 10 subsystems |
| `scripts/asi_heartbeat.py` | New — cron entry point (no_agent) |
| `toolsets.py` | Modified — added "asi" toolset + tools to core list |

### Cron Job

- **Name**: `asi-heartbeat-tick`
- **Schedule**: `*/5 * * * *` (every 5 minutes)
- **Type**: no_agent script `asi_heartbeat.py`
- **Behavior**: Checks all 10 subsystems, runs only those whose cadence timer has elapsed

### Verification

- Registry tests: 44/44 passed
- Tool registration: 5 ASI tools registered with emojis and schemas
- Heartbeat status: 10 subsystems loaded and reporting
- All pre-existing test failures confirmed unrelated (3 pre-existing)