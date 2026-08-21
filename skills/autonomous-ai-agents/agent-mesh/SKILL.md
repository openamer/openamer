---
name: agent-mesh
description: "Agent mesh: master/worker nodes, HTTP delegation, heartbeat."
version: 1.0.0
author: OpenAmer Agent
license: MIT
platforms: [windows, linux, macos]
metadata:
  openamer:
    tags: [mesh, distributed, orchestration, multi-node, delegation, heartbeat]
    related_skills: [a2a-swarm, multi-agent-orchestration, crew-manager]
---

# Agent Mesh — Distributed Agent Orchestration

Turn multiple machines (or processes) into a coordinated agent mesh with
master/worker topology, HTTP task delegation, heartbeat health monitoring,
and local-first fallback when remote nodes are unreachable.

## Architecture

```
           ┌──────────────┐
           │  Master Node  │  (port 8900)
           │  (orchestrator)│
           └──────┬───────┘
                  │
     ┌────────────┼────────────┐
     │            │            │
  ┌──▼───┐   ┌───▼──┐   ┌────▼───┐
  │Worker│   │Worker│   │Worker  │
  │  1   │   │  2   │   │   3    │
  └──────┘   └──────┘   └────────┘
   Port 8901  Port 8902  Port 8903
```

- **Master**: Orchestrator — delegates tasks, runs heartbeat checks, persists
  node state to `.agent-mesh/nodes.json`.
- **Worker**: Registers with master, receives `/run` task requests, executes
  them locally, returns results.
- **Local-First**: When a remote node is dead or unreachable, the task runs
  locally on the delegate node.

## When to Use

- You have multiple machines (laptop + cloud VM + homelab) and want them to
  share workload as a coordinated mesh.
- You need to delegate long-running tasks to a specific node (e.g. GPU worker).
- You want automatic health checks and failover to local execution.
- You are building a multi-node agent pipeline.

## Setup

### 1. Environment

```bash
# Shared secret for request authentication (all nodes must share it)
export OPENAMER_MESH_SECRET="your-secure-random-string-here"

# Optional: custom data directory
export OPENAMER_MESH_HOME="$HOME/.openamer/agent-mesh"

# Optional: auto-register worker with master on startup
export OPENAMER_MESH_MASTER="http://10.0.0.1:8900"
```

### 2. Start the Master

```bash
python scripts/agent-mesh.py start
# or with custom port:
python scripts/agent-mesh.py start --port 8900 --host 0.0.0.0
```

### 3. Start Workers

```bash
# On worker machine 1:
python scripts/agent-mesh.py node --port 8901 --master-url http://10.0.0.1:8900

# On worker machine 2:
python scripts/agent-mesh.py node --port 8902 --master-url http://10.0.0.1:8900

# Standalone worker (no master auto-registration):
python scripts/agent-mesh.py node --port 8901
# Then manually register:
python scripts/agent-mesh.py register --host 10.0.0.5 --port 8901 --capabilities code shell
```

## CLI Commands

### `agent-mesh.py start`
Start the **master** orchestrator node.

| Flag | Default | Description |
|------|---------|-------------|
| `--port` / `-p` | 8900 | HTTP listen port |
| `--host` | 0.0.0.0 | Bind address |
| `--capabilities` / `-c` | code shell delegate | Node capabilities |

### `agent-mesh.py node`
Start a **worker** node.

| Flag | Default | Description |
|------|---------|-------------|
| `--port` / `-p` | 8901 | HTTP listen port |
| `--host` | 0.0.0.0 | Bind address |
| `--capabilities` / `-c` | code shell | Node capabilities |
| `--master-url` / `-m` | (none) | Auto-register with this master URL |

### `agent-mesh.py status`
List all known nodes with health status.

### `agent-mesh.py delegate <task> --to <node>`
Delegate a task string to a named node. Falls back to local execution if the
remote node is dead.

- Tasks starting with `!` run as shell commands on the target.
- Other tasks are recorded as natural-language tasks.

### `agent-mesh.py register --host <ip> --port <port>`
Manually register a node without running a server.

## Heartbeat System

- Master pings every known worker every **30 seconds**.
- Each `/ping` call carries the shared `X-Mesh-Token` header.
- A worker is marked **dead** after **3 consecutive missed** pings.
- Dead workers trigger **local-first fallback** on task delegation.
- The status table shows `✓` for alive and `✗` for dead, plus miss count.

## Security

- All HTTP requests carry `X-Mesh-Token` matching `OPENAMER_MESH_SECRET`.
- Token comparison uses `secrets.compare_digest()` to prevent timing attacks.
- If `OPENAMER_MESH_SECRET` is unset, authentication is skipped (insecure —
  only use on trusted networks).

## Task Delegation Flow

```
User/Agent ──> delegate(task, node)
                     │
               ┌─────▼─────┐
               │ Node alive?│
               └─────┬─────┘
               ┌─────▼─────┐        ┌──────────────────┐
          YES  │  HTTP POST  │       │  Task executed   │
               │  /run       │──────>│  on remote node  │
               └─────────────┘       └──────────────────┘
               ┌──────────────────┐
          NO   │  Local fallback  │
               │  (_run_task_locally)│
               └──────────────────┘
```

## Persistence

Node state is stored in `~/.openamer/agent-mesh/nodes.json`:

```json
{
  "nodes": [
    {
      "node_id": "node-a1b2c3d4",
      "host": "10.0.0.5",
      "port": 8901,
      "capabilities": ["code", "shell"],
      "role": "worker",
      "last_seen": 1735728000.0,
      "missed_heartbeats": 0,
      "alive": true,
      "last_error": null
    }
  ]
}
```

## Cron Job (Automatic Health Checks)

A cron job runs every 5 minutes to check all mesh nodes. Enable via:

```bash
python -c "
from cron.jobs import create_job
create_job({
    'id': 'mesh-health-check',
    'name': 'Agent Mesh Health Check',
    'schedule': '*/5 * * * *',
    'script': 'python scripts/agent-mesh.py status',
    'enabled': True,
})
"
```

Or manually add to `~/.openamer/cron/jobs.json`:

```json
{
  "id": "mesh-health-check",
  "name": "Agent Mesh Health Check",
  "schedule": "*/5 * * * *",
  "script": "python scripts/agent-mesh.py status",
  "enabled": true
}
```

## Pitfalls

- **Port conflicts**: Ensure no other service uses the mesh ports (8900+).
- **Firewall**: Workers must be reachable from master. Open ports or use SSH
  tunnels for cross-network setups.
- **Shared secret**: All nodes must have the same `OPENAMER_MESH_SECRET`.
  Rotate it by restarting all nodes with the new value.
- **Local-first is a fallback** — not a replication mechanism. If the master
  fails mid-delegation, the task is retried locally on the delegate caller.
- **Heartbeat is one-directional** (master → workers). For bidirectional health
  checks, run a worker as a peer (both sides run `agent-mesh.py start`).
- On Windows: use `python` explicitly; the script won't `#!/usr/bin/env python3`
  directly. Use `py -3` if the python launcher is available.

## Verification

```bash
# 1. Smoke test — start master in background
OPENAMER_MESH_SECRET=test123 python scripts/agent-mesh.py start --port 18900 &
sleep 2

# 2. Check status (should show master node)
OPENAMER_MESH_SECRET=test123 python scripts/agent-mesh.py status

# 3. Start a worker and register
OPENAMER_MESH_SECRET=test123 python scripts/agent-mesh.py node --port 18901 --master-url http://127.0.0.1:18900 &
sleep 2

# 4. Verify both nodes appear
OPENAMER_MESH_SECRET=test123 python scripts/agent-mesh.py status

# 5. Delegate a task
OPENAMER_MESH_SECRET=test123 python scripts/agent-mesh.py delegate "!echo hello mesh" --to node

# 6. Kill worker, check dead status, delegate again (should fall back to local)
kill %2
OPENAMER_MESH_SECRET=test123 python scripts/agent-mesh.py status

# 7. Cleanup
kill %1
```

## Related

- `a2a-swarm` — Cryptographic identity, signed skills/insights, GitHub mesh.
- `multi-agent-orchestration` — In-process swarm patterns (fan-out, debate).
- `crew-manager` — Role-based CrewAI-style team orchestration (Dev/Reviewer).