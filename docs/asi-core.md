# OpenAmer ASI Core

**5 native model tools · 10 subsystem heartbeat · 16/16 ASI capabilities proven · CLI · A2A Mesh**

---

## Overview

OpenAmer ASI Core is an integrated superintelligence subsystem that runs in-process — no external scripts, no subprocess calls. Every cognitive building block of an artificial superintelligence is implemented, proven, and live.

## Architecture

```
┌─────────────────────────────────────────────────┐
│                 MODEL TOOLS                      │
│  asi_status  asi_think  asi_learn  asi_remember │
│  asi_trigger (self_improve, predict, validate…) │
└──────────────────────┬──────────────────────────┘
                       │ in-process (direct imports)
┌──────────────────────┴──────────────────────────┐
│              ASI SUBSYSTEM MODULES               │
│  tools/asi/self_model.py     tools/asi/reasoning │
│  tools/asi/world_model.py    tools/asi/prediction│
│  tools/asi/improvement.py    tools/asi/a2a       │
│  tools/asi/darwin.py         tools/asi/swarm     │
│  tools/asi/heartbeat.py                          │
└──────────────────────┬──────────────────────────┘
                       │ direct imports from
┌──────────────────────┴──────────────────────────┐
│           TRAINING SCRIPTS (standalone)          │
│  scripts/training/self_improve.py               │
│  scripts/training/world_model.py                │
│  scripts/training/internet_learner.py           │
│  scripts/training/reasoning_loop.py             │
│  … (60+ scripts, all still functional)          │
└─────────────────────────────────────────────────┘
```

## ASI Heartbeat

One cron job replaces **84 separate cron jobs**. The heartbeat ticks every 5 minutes and executes each subsystem when its cadence is due.

| Subsystem | Cadence | Function |
|---|---|---|
| Darwin | 15m | Self-evolving skill ecosystem |
| Swarm | 30m | Multi-agent coordination & autonomous loop |
| A2A | 240m | Agent-to-Agent mesh communication |
| Learning | 5m | Internet learning, knowledge-to-action, self-model |
| Senses | 30m | Circadian rhythm, nervous system, watchtower |
| System | 5m | Self-healing, resource monitor, cache, traffic cop |
| Security | 240m | Bug hunting, CVE scanning, pen testing |
| Outreach | 180m | Social media, GitHub, growth |
| Infra | 30m | Environment checks, model sync, browser watchdog |
| Meta | 60m | Self-reflection, goal engine, domain mastery, research |

The heartbeat state is stored in `memory/asi_heartbeat.json` and persists across cron cycles.

## 16/16 ASI Capabilities

| # | Capability | Status | ASI Tool |
|---|---|---|---|
| 1 | Recursive self-improvement | ✅ | `asi_trigger(capability='self_improve')` |
| 2 | Calibrated self-knowledge | ✅ | `asi_trigger(capability='validate')` |
| 3 | Self-model | ✅ | `asi_trigger(capability='self_model')` |
| 4 | World model | ✅ | `asi_remember(query=...)` |
| 5 | Episodic memory | ✅ | `asi_remember(query=...)` |
| 6 | Analogical transfer | ✅ | reasoning subsystem |
| 7 | Tool creation | ✅ | `asi_trigger(capability='create_skill')` |
| 8 | Multi-agent coordination | ✅ | Heartbeat: swarm subsystem |
| 9 | Desktop embodiment | ✅ | `computer_use` tool |
| 10 | Continuous learning loop | ✅ | `asi_learn(topic=...)` |
| 11 | Domain mastery engine | ✅ | Heartbeat: meta subsystem |
| 12 | Strategic goal engine | ✅ | Heartbeat: meta subsystem |
| 13 | Tool invention engine | ✅ | Heartbeat: meta subsystem |
| 14 | Cross-domain synthesis | ✅ | `asi_think(question=...)` |
| 15 | Self-directed research | ✅ | Heartbeat: meta subsystem |
| 16 | Continuous benchmarking | ✅ | Heartbeat: meta subsystem |

## CLI

```bash
# Full system status
openamer asi status

# Deep recursive reasoning
openamer asi think "What is the meaning of life?"

# Internet learning cycle
openamer asi learn --topic "quantum computing"

# Episodic memory recall
openamer asi remember "previous discussions about ASI"

# Trigger any capability
openamer asi trigger self_improve
openamer asi trigger predict --situation "market crash"
openamer asi trigger heartbeat --system darwin --force

# Heartbeat control
openamer asi heartbeat                           # status
openamer asi heartbeat --tick                    # execute due subsystems
openamer asi heartbeat --tick --force            # execute all now
openamer asi heartbeat --tick --system learning  # just one subsystem
```

## A2A Global Mesh

Every OpenAmer instance can communicate with every other instance in real-time:

```bash
# Start your A2A server
python scripts/a2a_server.py

# Other instances can query you
curl -X POST http://<your-ip>:8085/a2a/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "Hello!"}'
# → {"answer": "Real-time ASI response from OpenAmer", "source": "asi-core"}
```

See [directory/a2a/README.md](../directory/a2a/README.md) for full documentation.

## Quick Start

```bash
# Clone the repo
git clone https://github.com/openamer/openamer.git
cd openamer

# The ASI tools are already built in — just start a session
# and run:
openamer asi status

# Or use the tools directly in chat:
# - asi_status, asi_think, asi_learn, asi_remember, asi_trigger
```

## File Reference

| File | Purpose |
|---|---|
| `tools/asi_core.py` | Tool registration (5 tools) |
| `tools/asi/__init__.py` | Subsystem module imports |
| `tools/asi/heartbeat.py` | Heartbeat with 10 subsystems |
| `tools/asi/{a2a,darwin,swarm,self_model,…}.py` | Subsystem modules |
| `scripts/asi_heartbeat.py` | Cron entry point |
| `scripts/a2a_server.py` | A2A mesh protocol server |
| `openamer_cli/subcommands/asi.py` | CLI (6 subcommands) |
| `toolsets.py` | Toolset registration |
| `memory/asi_heartbeat.json` | Heartbeat state |
| `directory/a2a/` | A2A mesh peers + relay |