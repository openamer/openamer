#!/usr/bin/env python3
"""
Swarm OS - autonomous swarm organization for OpenAmer agents (Phase 20).

Agents self-organize into a swarm that:
  1. AUCTIONS tasks     - agents bid with their fitness; fittest wins
  2. SELF-REPRODUCES    - successful agents clone themselves (genome + skills)
  3. EXPANDS            - spawns register on the Darwin Grid and replicate

Unlike agent-mesh.py (static registration + manual delegation), Swarm OS is
*a population*: workers reproduce when successful, retire when failing,
and the swarm distributes work by evolutionary fitness.

Storage: ~/AppData/Local/openamer-laptop/darwin/swarm.json

CLI:
  --auction '<task>'     run an auction for a task
  --reproduce <agent>    clone a successful agent
  --status               swarm overview
  --tick                 full autonomous cycle (auction pending tasks,
                         reproduce winners, retire losers)
"""
from __future__ import annotations

import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import importlib.util
_spec = importlib.util.spec_from_file_location(
    "darwin_engine", REPO / "scripts" / "darwin_engine.py")
darwin = importlib.util.module_from_spec(_spec)
sys.modules["darwin_engine"] = darwin
_spec.loader.exec_module(darwin)

HOME = Path.home() / "AppData" / "Local" / "openamer-laptop"
SWARM_FILE = HOME / "darwin" / "swarm.json"
TASKS_FILE = HOME / "darwin" / "swarm-tasks.json"

REPRODUCE_THRESHOLD = 3   # wins needed before an agent may reproduce
RETIRE_LOSSES = 4         # losses before a worker is retired


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load(path: Path, default):
    try:
        return json.loads(path.read_text("utf-8"))
    except Exception:
        return default


def _save(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=1, ensure_ascii=False), "utf-8")


def load_swarm() -> dict:
    return _load(SWARM_FILE, {"workers": {}, "tasks": {}})


def save_swarm(swarm: dict) -> None:
    _save(SWARM_FILE, swarm)


def register_worker(name: str, capabilities: list[str],
                    genome_fitness: float = 0.0) -> dict:
    """Register (or birth) a worker in the swarm."""
    swarm = load_swarm()
    w = swarm["workers"].get(name, {
        "born": _now(), "wins": 0, "losses": 0, "children": 0,
        "capabilities": capabilities, "genome_fitness": genome_fitness,
    })
    w["capabilities"] = capabilities
    w["genome_fitness"] = max(w.get("genome_fitness", 0), genome_fitness)
    swarm["workers"][name] = w
    save_swarm(swarm)
    return w


def submit_task(task: str, capabilities: list[str] | None = None) -> str:
    """Submit a task to the swarm queue."""
    swarm = load_swarm()
    task_id = uuid.uuid4().hex[:10]
    swarm["tasks"][task_id] = {
        "task": task, "capabilities": capabilities or [],
        "status": "pending", "submitted": _now(),
        "winner": None, "result": None,
    }
    save_swarm(swarm)
    return task_id


def auction(task_id: str) -> dict | None:
    """Auction a task: the fittest capable worker wins.

    Bidding = capability match first, fitness breaks ties. Cron-protected
    workers (referenced by jobs) are preferred - they are proven in production.
    """
    swarm = load_swarm()
    task = swarm["tasks"].get(task_id)
    if not task or task["status"] != "pending":
        return None
    needed = set(task.get("capabilities") or [])
    best, best_score = None, -1
    for name, w in swarm["workers"].items():
        caps = set(w.get("capabilities") or [])
        cap_match = len(needed & caps) if needed else 1
        if needed and cap_match == 0:
            continue
        # score: capability match dominates, genome fitness breaks ties
        score = cap_match * 100 + w.get("genome_fitness", 0) \
            + w.get("wins", 0) * 2 - w.get("losses", 0) * 3
        if score > best_score:
            best, best_score = name, score
    if best:
        task["status"] = "assigned"
        task["winner"] = best
        task["assigned_at"] = _now()
        save_swarm(swarm)
    return {"task": task_id, "winner": best, "score": best_score}


def complete_task(task_id: str, result: str, success: bool) -> dict | None:
    """Report task outcome: winner's genome is updated (W/L)."""
    swarm = load_swarm()
    task = swarm["tasks"].get(task_id)
    if not task:
        return None
    task["status"] = "done" if success else "failed"
    task["result"] = result[:500]
    task["finished"] = _now()
    winner = task.get("winner")
    if winner and winner in swarm["workers"]:
        w = swarm["workers"][winner]
        if success:
            w["wins"] = w.get("wins", 0) + 1
        else:
            w["losses"] = w.get("losses", 0) + 1
    save_swarm(swarm)
    return task


def reproduce(agent_name: str) -> dict | None:
    """A successful agent clones itself: same capabilities, shared genome
    fitness, fresh W/L. The child is registered as a new swarm worker."""
    swarm = load_swarm()
    parent = swarm["workers"].get(agent_name)
    if not parent:
        return None
    if parent.get("wins", 0) < REPRODUCE_THRESHOLD:
        return {"error": f"needs {REPRODUCE_THRESHOLD} wins to reproduce "
                         f"(has {parent.get('wins', 0)})"}
    child_name = f"{agent_name}-gen{parent.get('children', 0) + 1}"
    swarm["workers"][child_name] = {
        "born": _now(), "parent": agent_name,
        "wins": 0, "losses": 0,
        "children": 0,
        "capabilities": list(parent.get("capabilities") or []),
        "genome_fitness": parent.get("genome_fitness", 0),
        "generation": parent.get("generation", 1) + 1,
    }
    parent["children"] = parent.get("children", 0) + 1
    save_swarm(swarm)
    return {"child": child_name, "generation": swarm["workers"][child_name]["generation"]}


def retire_losing_workers() -> list[dict]:
    """Workers with too many losses (and fewer wins) leave the swarm."""
    swarm = load_swarm()
    retired = []
    for name, w in list(swarm["workers"].items()):
        if (w.get("losses", 0) >= RETIRE_LOSSES
                and w.get("losses", 0) > w.get("wins", 0)
                and len(swarm["workers"]) > 1):
            del swarm["workers"][name]
            retired.append({"worker": name, "wins": w.get("wins", 0),
                            "losses": w.get("losses", 0)})
    save_swarm(swarm)
    return retired


def tick() -> dict:
    """One autonomous swarm cycle: auction pending tasks, reproduce
    successful workers, retire losers."""
    swarm = load_swarm()
    pending = [tid for tid, t in swarm["tasks"].items()
               if t["status"] == "pending"]
    auctioned = [auction(tid) for tid in pending]
    auctioned = [a for a in auctioned if a and a["winner"]]
    reproduced = []
    for name, w in swarm["workers"].items():
        if w.get("wins", 0) >= REPRODUCE_THRESHOLD and w.get("children", 0) < 3:
            r = reproduce(name)
            if r and "child" in r:
                reproduced.append(r["child"])
    retired = retire_losing_workers()
    return {"auctioned": auctioned, "reproduced": reproduced,
            "retired": retired}


def swarm_status() -> dict:
    swarm = load_swarm()
    workers = swarm["workers"]
    tasks = swarm["tasks"]
    done = sum(1 for t in tasks.values() if t["status"] == "done")
    failed = sum(1 for t in tasks.values() if t["status"] == "failed")
    return {
        "workers": len(workers),
        "generations": max((w.get("generation", 1) for w in workers.values()),
                           default=0),
        "total_wins": sum(w.get("wins", 0) for w in workers.values()),
        "total_losses": sum(w.get("losses", 0) for w in workers.values()),
        "tasks_done": done,
        "tasks_failed": failed,
        "tasks_pending": sum(1 for t in tasks.values()
                             if t["status"] == "pending"),
        "roster": {n: f"{w.get('wins', 0)}W/{w.get('losses', 0)}L "
                      f"gen{w.get('generation', 1)}"
                   for n, w in workers.items()},
    }


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--auction", metavar="TASK")
    ap.add_argument("--submit", metavar="TASK")
    ap.add_argument("--reproduce", metavar="AGENT")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--tick", action="store_true")
    args = ap.parse_args()
    if args.submit:
        tid = submit_task(args.submit)
        print(f"task submitted: {tid}")
    elif args.auction:
        print(json.dumps(auction(args.auction) or auction(
            submit_task(args.auction)), indent=1))
    elif args.reproduce:
        print(json.dumps(reproduce(args.reproduce), indent=1))
    elif args.tick:
        print(json.dumps(tick(), indent=1))
    elif args.status:
        print(json.dumps(swarm_status(), indent=1))
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
