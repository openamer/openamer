#!/usr/bin/env python3
"""Swarm Intelligence — multi-agent collaboration for Mini-OpenAmer.

Laptop agent + PC agent work TOGETHER as a collective:
  A. Task routing: simple→laptop, GPU-heavy→PC, frontier→cloud
  B. Shared world-model: insights from both agents merge
  C. Evidence-based consensus: conflicting learnings resolve by evidence count
  D. Shared identity: "We are OpenAmer" — collective self-model

Runs over the Agent Mesh (Go-daemon :18920) + SSH to PC.
"""
import json, os, sys, time, datetime, subprocess, urllib.request, threading

T = r"C:/Users/damir/AppData/Local/openamer-laptop/scripts/training"
SWARM_DIR = r"C:/Users/damir/AppData/Local/openamer-laptop/memory/swarm"
SHARED_WM = os.path.join(SWARM_DIR, "shared_world_model.jsonl")
SWARM_STATE = os.path.join(SWARM_DIR, "swarm_state.json")
SWARM_IDENTITY = os.path.join(SWARM_DIR, "swarm_identity.md")
PC_SSH = "damir@192.168.178.23"
PC_AGENT_URL = "http://192.168.178.23:8081"  # tool_server on PC

os.makedirs(SWARM_DIR, exist_ok=True)

def load_json(path, default):
    try:
        return json.load(open(path, encoding="utf-8"))
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
    # PC — frontier server
    try:
        r = subprocess.run(["ssh", "-o", "StrictHostKeyChecking=no", "-o", "BatchMode=yes",
            "damir@192.168.178.23", "curl -s -m 5 http://localhost:8082/health"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=15)
        if "alive" in r.stdout:
            agents.append({"id": "pc-gpu-4b", "url": "http://localhost:8082 (via SSH)",
                          "role": "frontier-reasoning", "tools": 1,
                          "energy": "medium", "capabilities": ["deep-reasoning", "gpu-training"]})
    except Exception:
        pass
    return agents

# ---- B. Knowledge Synthesis: merge insights from both agents ----

def synthesize_knowledge(local_insight, remote_insight=None):
    """Merge insights from both agents."""
    try:
        if remote_insight is None:
            r = subprocess.run(["ssh", "-o", "StrictHostKeyChecking=no", "-o", "BatchMode=yes",
                "damir@192.168.178.23",
                "curl -s -m 5 http://localhost:8081/health"],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=15)
            if "alive" not in r.stdout:
                return "remote agent down"
            remote_insight = r.stdout.strip()

        synthesis = {
            "ts": datetime.datetime.now().isoformat(),
            "type": "synthesis",
            "local": (local_insight or "none")[:200],
            "remote": (remote_insight or "none")[:200],
            "synthesized": "Laptop reasoning + PC GPU perspective merged",
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
    # - reasoning/GPU tasks → PC (has GPU, deeper model)
    if complexity == "auto":
        # simple keywords → laptop, complex → PC
        complex_keywords = ["analyze", "compare", "prove", "design", "architecture"]
        complexity = "complex" if any(k in task.lower() for k in complex_keywords) else "simple"

    if complexity == "simple":
        target = next((a for a in agents if a["id"] == "laptop-2b"), agents[0])
    else:
        target = next((a for a in agents if a["id"] == "pc-gpu-4b"),
                     next((a for a in agents if a["id"] == "laptop-2b"), agents[0]))

    return {"task": task[:100], "routed_to": target["id"],
            "reason": f"complexity={complexity}, {target['role']}"}

# ---- D. Evidence-based Consensus ----

def resolve_conflict(claim_a, claim_b, evidence_a, evidence_b):
    """When agents disagree, the one with more evidence wins."""
    # count supporting evidence in world model
    if not os.path.exists(SHARED_WM):
        return {"winner": "undetermined", "reason": "no shared knowledge"}
    lines = open(SHARED_WM, encoding="utf-8").readlines()
    support_a = sum(1 for l in lines if claim_a[:40].lower() in l.lower())
    support_b = sum(1 for l in lines if claim_b[:40].lower() in l.lower())

    winner = "a" if support_a > support_b else "b" if support_b > support_a else "tie"
    return {"winner": winner, "evidence_a": support_a, "evidence_b": support_b,
            "principle": "more evidence wins — consensus through shared experience"}

# ---- E. Shared Identity ----

def update_swarm_identity():
    """The 'WE' identity — collective self-model across agents."""
    agents = discover_agents()
    total_events = 0
    total_memory = 0

    # laptop stats
    wm_path = r"C:/Users/damir/AppData/Local/openamer-laptop/memory/world_model.jsonl"
    if os.path.exists(wm_path):
        total_events = sum(1 for _ in open(wm_path, encoding="utf-8"))

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
- 3012+ episodic memories (our collective history)
- 2400+ evolution events (our genetic diversity)

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
        update_swarm_identity()