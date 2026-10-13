# ASI Core Deep-Dive: 5 Native Tools, a 10-Subsystem Heartbeat, and the A2A Global Mesh

*Why OpenAmer's agent architecture dropped cron jobs for a heartbeat — and gave every instance a voice.*

OpenAmer is an open-source AI agent (Apache 2.0) that runs entirely local on Windows. This post is a technical walkthrough of the ASI Core architecture — the layer that makes the agent autonomous, verifiable, and able to coordinate with other instances.

## 1. Five native ASI tools — in-process, no subprocess

Most agent frameworks shell out for everything. Every tool call pays process-spawn cost, loses the error context, and can't share memory with the reasoning loop.

OpenAmer's ASI tools run **in-process**:

- **think** — recursive reasoning loop with outcome prediction
- **learn** — extract patterns from failures into a persistent learning store
- **remember** — vector memory with episodic recall
- **trigger** — event the subsystems directly (no cron roundtrip)
- **heartbeat** — the 10-subsystem pulse (below)

No subprocess = no serialization overhead, structured errors stay structured, and tool results are immediately part of the reasoning context.

## 2. The 10-subsystem heartbeat replaces 84 cron jobs

OpenAmer grew to 84 scheduled cron jobs — and they failed in the worst way: silently. A failed outreach run reported green because the exit code was checked after a pipe (`cmd | tail; echo $?` measures tail, not cmd). Sixteen jobs went down on a single day and nobody noticed for hours.

The fix was architectural: one **heartbeat** that drives 10 subsystems on a fixed cadence — browser health, sessions, self-healing, learning, outreach, backup, reflection, performance, security, and a watchdog. Each subsystem reports its state honestly into the pulse; failures surface as facts, not exit codes.

The lesson generalizes: **an agent that lies to itself about success will confidently do the wrong thing forever.** Every claimed outcome gets re-verified by a separate subsystem before it's written to memory.

## 3. A2A Global Mesh: every instance talks to every other instance

The newest piece. Every running OpenAmer instance can discover and talk to every other instance — peer-to-peer, no central coordinator.

- Instances advertise capabilities and state over the mesh
- Tasks route to the instance best suited for them (GPU vs. laptop)
- Shared learnings propagate: what one instance learns, all can use
- Verified 16/16 ASI capabilities in the last E2E run

Try it locally:

```bash
openamer asi status      # subsystem + mesh state
openamer asi think "..." # recursive reasoning
openamer asi learn       # extract learnings from logs
openamer asi remember q  # episodic recall
openamer asi heartbeat   # force a pulse
```

## Status

Everything above is running 24/7 on a single Windows laptop (20W-class goal: it should stay lean). The repo is Apache 2.0:

**https://github.com/openamer/openamer**

Feedback, PRs, and star-ratings welcome — especially from anyone running multi-agent setups.
