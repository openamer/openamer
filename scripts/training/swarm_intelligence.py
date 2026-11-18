#!/usr/bin/env python3
"""Swarm Intelligence — multi-agent collaboration for Mini-OpenAmer.

Every agent that is actually reachable works TOGETHER as a collective:
  A. Task routing: everything on the laptop; the GPU PC that took the deep work
     was decommissioned 2026-11-18 (no GPU on this network any more)
  B. Shared world-model: insights from all agents merge
  C. Evidence-based consensus: conflicting learnings resolve by evidence count
  D. Shared identity: "We are OpenAmer" — collective self-model

Runs over the Agent Mesh (Go-daemon :18920). A remote node is added by
registering it in discovery, never by hardcoding a host in the routing table.
"""

import os
import json, os, sys, time, datetime, subprocess, urllib.request, threading
from pathlib import Path

T = os.path.join(os.environ.get("OPENAMER_HOME", str(Path.home() / "AppData" / "Local" / "openamer")), "scripts", "training")
SWARM_DIR = os.path.join(os.environ.get("OPENAMER_HOME", str(Path.home() / "AppData" / "Local" / "openamer")), "memory", "swarm")
SHARED_WM = os.path.join(SWARM_DIR, "shared_world_model.jsonl")
SWARM_STATE = os.path.join(SWARM_DIR, "swarm_state.json")
SWARM_IDENTITY = os.path.join(SWARM_DIR, "swarm_identity.md")

os.makedirs(SWARM_DIR, exist_ok=True)

def load_json(path, default):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return default

def log_shared(entry):
    with open(SHARED_WM, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

# ---- A. Agent Discovery: who is alive? ----

def discover_agents():
    """Find all live OpenAmer instances in the swarm."""
    agents = []
    # laptop (self) — always alive
    try:
        h = json.load(urllib.request.urlopen("http://localhost:8081/health", timeout=5))
        agents.append({"id": "laptop-2b", "url": "http://localhost:8081",
                       "role": "cognition+memory", "tools": h.get("tools", 0),
                       "energy": "low", "capabilities": ["reasoning", "memory", "tools"]})
    except Exception:
        pass
    # The PC frontier node (RTX 3060 Ti, :8082) was decommissioned on
    # 2026-11-18 — the owner has no GPU any more. It is not probed: a node that
    # cannot come back is not a fallback, it is a timeout. Registering it again
    # later is a one-line addition behind a config flag, not a hardcoded host.
    return agents

# ---- B. Knowledge Synthesis: merge insights from both agents ----

def synthesize_knowledge(local_insight, remote_insight=None):
    """Merge insights from the agents that actually exist.

    The remote half used to be an SSH probe to the PC GPU node. That node was
    decommissioned 2026-11-18, so an unset ``remote_insight`` now means "no
    remote perspective" instead of "hang on ssh until the timeout".
    """
    try:
        synthesis = {
            "ts": datetime.datetime.now().isoformat(),
            "type": "synthesis",
            "local": (local_insight or "none")[:200],
            "remote": (remote_insight or "none")[:200],
            "synthesized": ("laptop reasoning only — no remote node registered"
                            if not remote_insight else "laptop reasoning + remote perspective merged"),
        }
        log_shared(synthesis)
        return synthesis
    except Exception as e:
        return f"synthesis error: {e}"

# ---- C. Task Routing: who does what? ----

def route_task(task, complexity="auto"):
    """Route a task to the best agent based on capabilities."""
    agents = discover_agents()
    if not agents:
        return {"error": "no agents available"}

    # heuristic routing:
    # - simple/memory tasks → laptop (always on, low energy)
    # - everything else → laptop too: the GPU PC that used to take the deep work
    #   was decommissioned 2026-11-18
    if complexity == "auto":
        # simple keywords → laptop, complex → same agent, flagged as complex
        complex_keywords = ["analyze", "compare", "prove", "design", "architecture"]
        complexity = "complex" if any(k in task.lower() for k in complex_keywords) else "simple"

    if complexity == "simple":
        target = next((a for a in agents if a["id"] == "laptop-2b"), agents[0])
    else:
        # No GPU node to escalate to since 2026-11-18: "complex" stays on the
        # agent that exists instead of routing to a host that cannot answer.
        target = next((a for a in agents if a["id"] == "laptop-2b"), agents[0])

    return {"task": task[:100], "routed_to": target["id"],
            "reason": f"complexity={complexity}, {target['role']}"}

# ---- D. Evidence-based Consensus ----

def resolve_conflict(claim_a, claim_b, evidence_a, evidence_b):
    """When agents disagree, the one with more evidence wins."""
    # count supporting evidence in world model
    if not os.path.exists(SHARED_WM):
        return {"winner": "undetermined", "reason": "no shared knowledge"}
    with open(SHARED_WM, encoding="utf-8") as _fh:
        lines = _fh.readlines()
    support_a = sum(1 for l in lines if claim_a[:40].lower() in l.lower())
    support_b = sum(1 for l in lines if claim_b[:40].lower() in l.lower())

    winner = "a" if support_a > support_b else "b" if support_b > support_a else "tie"
    return {"winner": winner, "evidence_a": support_a, "evidence_b": support_b,
            "principle": "more evidence wins — consensus through shared experience"}

# ---- E. Shared Identity ----

def update_swarm_identity(agents=None):
    """The 'WE' identity — collective self-model across agents.

    `agents` is passed in by the caller when discovery already ran, so one cycle
    probes each registered agent once instead of twice.
    """
    if agents is None:
        agents = discover_agents()
    total_events = 0
    total_memory = 0

    # laptop stats
    wm_path = os.path.join(os.environ.get("OPENAMER_HOME", str(Path.home() / "AppData" / "Local" / "openamer")), "memory", "world_model.jsonl")
    if os.path.exists(wm_path):
        with open(wm_path, encoding="utf-8") as _fh1:
            total_events = sum(1 for _ in _fh1)

    # Measured, not recited: the collective numbers come from the stores on
    # this node. The doc used to state those counts as prose, which drifts
    # the moment either store grows.
    home = os.environ.get(
        "OPENAMER_HOME",
        str(Path.home() / "AppData" / "Local" / "openamer"))
    episodes_path = os.path.join(home, "memory", "longterm_episodes.jsonl")
    if os.path.exists(episodes_path):
        with open(episodes_path, encoding="utf-8") as _fh2:
            total_memory = sum(1 for _ in _fh2)
    lineage = load_json(os.path.join(home, "darwin", "lineage.json"), {})
    total_evolution = (len(lineage.get("events", [])) if isinstance(lineage, dict)
                       else len(lineage))

    swarm_state = load_json(SWARM_STATE, {"cycles": 0})
    swarm_state["cycles"] += 1
    swarm_state["last_update"] = datetime.datetime.now().isoformat()
    swarm_state["agents_alive"] = len(agents)

    identity = f"""# OpenAmer Swarm — Collective Identity

*Updated: {swarm_state['last_update'][:16]}*

## We are

{len(agents)} OpenAmer instances working as one intelligence:
{chr(10).join(f'- {a["id"]}: {a["role"]} ({a["energy"]} energy)' for a in agents)}

## Shared knowledge

- {total_events} world-model edges (shared across agents)
- {total_memory} episodic memories (our collective history)
- {total_evolution} evolution events (our genetic diversity)

## Our shared values

- Evidence over authority
- Energy efficiency over brute force
- Belonging to Damir, not to any corporation
- Honesty about what we are and what we don't know

## Our collective goal

To grow together until nothing stops us — each agent contributing
its unique capabilities while sharing a single evolving understanding.
"""
    with open(SWARM_IDENTITY, "w", encoding="utf-8") as f:
        f.write(identity)
    with open(SWARM_STATE, "w", encoding="utf-8") as f:
        json.dump(swarm_state, f, indent=1)

    print(f"[swarm] cycle #{swarm_state['cycles']}: {len(agents)} agents alive, "
          f"identity {'evolved' if swarm_state['cycles'] > 1 else 'created'}", flush=True)
    return swarm_state

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        if sys.argv[1] == "status":
            agents = discover_agents()
            print(json.dumps({"agents": agents, "count": len(agents)}, indent=1))
        elif sys.argv[1] == "identity":
            update_swarm_identity()
        elif sys.argv[1] == "route" and len(sys.argv) > 2:
            print(json.dumps(route_task(" ".join(sys.argv[2:])), indent=1))
        else:
            print("usage: swarm.py [status|identity|route <task>]")
    else:
        # full cycle
        agents = discover_agents()
        print(f"[swarm] agents discovered: {len(agents)}")
        for a in agents:
            print(f"  • {a['id']} ({a['role']}, {a['energy']} energy)")
        update_swarm_identity(agents)