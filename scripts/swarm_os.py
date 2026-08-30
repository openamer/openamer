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
                    genome_fitness: float = 0.0,
                    starting_energy: float = 50.0) -> dict:
    """Register (or birth) a worker in the swarm."""
    swarm = load_swarm()
    w = swarm["workers"].get(name, {
        "born": _now(), "wins": 0, "losses": 0, "children": 0,
        "capabilities": capabilities, "genome_fitness": genome_fitness,
        "energy": starting_energy,
    })
    w["capabilities"] = capabilities
    w["genome_fitness"] = max(w.get("genome_fitness", 0), genome_fitness)
    swarm["workers"][name] = w
    save_swarm(swarm)
    return w


# ── Energy economics (phase 21): work pays, existing costs ───────────────────

ENERGY_TASK_REWARD = 10.0    # paid for a completed task
ENERGY_TASK_FAILURE = -5.0   # failed tasks cost energy
ENERGY_AUCTION_BID = 1.0     # participating in an auction costs energy
ENERGY_REPRODUCE_COST = 20.0  # children are an investment
ENERGY_IDLE_DRAIN = 0.5      # per tick, just for existing
ENERGY_STARVATION = 0.0      # below this -> worker dies


def _pay_energy(swarm: dict, name: str, amount: float) -> None:
    w = swarm["workers"].get(name)
    if w is not None:
        w["energy"] = round(w.get("energy", 0) + amount, 2)


def drift_capabilities(parent_caps: list[str],
                       rng, rate: float = 0.3) -> list[str]:
    """Genetic drift: children are never exact clones. With probability
    `rate` per child, one capability is dropped OR a related one gained."""
    caps = list(parent_caps)
    if not caps or rng.random() > rate:
        return caps
    if len(caps) > 1 and rng.random() < 0.5:
        caps.remove(rng.choice(caps))      # lose one
    else:
        related = {"code": "review", "evolution": "mutation",
                   "memory": "recall", "sync": "network"}
        base = rng.choice(caps)
        if base in related:
            caps.append(related[base])     # gain a related one
        else:
            caps.append(base + "-v2")      # variant
    return caps


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
        # score: capability match dominates, genome fitness breaks ties,
        # energy multiplies (wealthy workers can bid higher)
        energy_boost = 1.0 + max(w.get("energy", 0), 0) / 100.0
        score = (cap_match * 100 + w.get("genome_fitness", 0)
                 + w.get("wins", 0) * 2 - w.get("losses", 0) * 3) * energy_boost
        if score > best_score:
            best, best_score = name, score
    if best:
        task["status"] = "assigned"
        task["winner"] = best
        task["assigned_at"] = _now()
        _pay_energy(swarm, best, -ENERGY_AUCTION_BID)  # bidding costs
        save_swarm(swarm)
    return {"task": task_id, "winner": best, "score": round(best_score, 2)}


def complete_task(task_id: str, result: str, success: bool) -> dict | None:
    """Report task outcome: winner's genome is updated (W/L) and energy
    is exchanged - success pays, failure costs."""
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
            _pay_energy(swarm, winner, ENERGY_TASK_REWARD)
        else:
            w["losses"] = w.get("losses", 0) + 1
            _pay_energy(swarm, winner, ENERGY_TASK_FAILURE)
    save_swarm(swarm)
    return task


def reproduce(agent_name: str) -> dict | None:
    """A successful agent clones itself: same capabilities, shared genome
    fitness, fresh W/L. Reproduction costs energy; the child receives
    half the parent's energy (inheritance) and drift-mutated capabilities."""
    import random as _random
    swarm = load_swarm()
    parent = swarm["workers"].get(agent_name)
    if not parent:
        return None
    if parent.get("wins", 0) < REPRODUCE_THRESHOLD:
        return {"error": f"needs {REPRODUCE_THRESHOLD} wins to reproduce "
                         f"(has {parent.get('wins', 0)})"}
    parent_energy = parent.get("energy", 0)
    if parent_energy < ENERGY_REPRODUCE_COST:
        return {"error": f"needs {ENERGY_REPRODUCE_COST} energy to reproduce "
                         f"(has {parent_energy})"}
    child_name = f"{agent_name}-gen{parent.get('children', 0) + 1}"
    rng = _random.Random(_now())
    child_caps = drift_capabilities(parent.get("capabilities") or [], rng)
    half_energy = round(parent_energy / 2, 2)
    swarm["workers"][child_name] = {
        "born": _now(), "parent": agent_name,
        "wins": 0, "losses": 0,
        "children": 0,
        "capabilities": child_caps,
        "genome_fitness": parent.get("genome_fitness", 0),
        "generation": parent.get("generation", 1) + 1,
        "energy": half_energy,
        "drifted": child_caps != list(parent.get("capabilities") or []),
    }
    parent["children"] = parent.get("children", 0) + 1
    _pay_energy(swarm, agent_name, -ENERGY_REPRODUCE_COST)
    save_swarm(swarm)
    return {"child": child_name,
            "generation": swarm["workers"][child_name]["generation"],
            "drifted": swarm["workers"][child_name]["drifted"]}


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


# ── Phase 23: teaching + territoriality ──────────────────────────────────────

SWARM_KNOWLEDGE_FILE = HOME / "darwin" / "swarm-knowledge.json"
TERRITORIES_FILE = HOME / "darwin" / "territories.json"


def teach_before_death(swarm: dict, dying_worker: str) -> dict | None:
    """A dying worker passes its life's knowledge to the fittest survivor.

    Knowledge transferred:
    - capabilities the survivor lacks (up to 2)
    - a fitness grant proportional to the dying worker's wins
    - recorded in the swarm knowledge base (generational memory)
    """
    dying = swarm["workers"].get(dying_worker)
    if not dying:
        return None
    survivors = {n: w for n, w in swarm["workers"].items()
                 if n != dying_worker}
    if not survivors:
        return None
    heir_name = max(survivors, key=lambda n: survivors[n].get("genome_fitness", 0))
    heir = survivors[heir_name]
    dying_caps = set(dying.get("capabilities") or [])
    heir_caps = set(heir.get("capabilities") or [])
    transferred = list(dying_caps - heir_caps)[:2]
    for c in transferred:
        heir_caps.add(c)
    heir["capabilities"] = list(heir_caps)
    grant = round(dying.get("wins", 0) * 0.5, 2)
    heir["genome_fitness"] = round(
        heir.get("genome_fitness", 0) + grant, 2)
    # knowledge base: the swarm remembers its teachers forever
    kb = _load(SWARM_KNOWLEDGE_FILE, {"teachers": []})
    kb["teachers"].append({
        "teacher": dying_worker, "heir": heir_name,
        "taught": transferred, "fitness_grant": grant, "when": _now(),
    })
    _save(SWARM_KNOWLEDGE_FILE, kb)
    return {"heir": heir_name, "taught": transferred, "fitness_grant": grant}


def claim_territory(domain: str, worker: str) -> dict:
    """A worker claims a task domain for the local swarm."""
    territories = _load(TERRITORIES_FILE, {})
    existing = territories.get(domain)
    if existing and existing.get("holder") != "local":
        # foreign territory - must be contested via duel
        return {"claimed": False, "reason": "held by foreign swarm",
                "holder": existing.get("holder")}
    territories[domain] = {"holder": "local", "worker": worker,
                           "claimed": _now()}
    _save(TERRITORIES_FILE, territories)
    return {"claimed": True, "domain": domain, "worker": worker}


def contest_territory(domain: str, foreign_champion: str,
                      local_champion: str) -> dict:
    """A foreign swarm contests a domain we hold: real duel decides."""
    territories = _load(TERRITORIES_FILE, {})
    existing = territories.get(domain)
    if not existing or existing.get("holder") != "local":
        return {"contested": False, "reason": "not ours to defend"}
    duel = darwin.head_to_head(local_champion, foreign_champion)
    won = duel["winner"] == "parent"
    if not won:
        territories[domain] = {"holder": "foreign",
                               "worker": foreign_champion,
                               "lost": _now()}
        _save(TERRITORIES_FILE, territories)
    return {"contested": True, "domain": domain, "won": won,
            "local_exit": duel["parent_result"].get("exit_code"),
            "foreign_exit": duel["child_result"].get("exit_code")}


def tick() -> dict:
    """One autonomous swarm cycle: auction pending tasks, reproduce
    successful workers, drain idle energy, starve the broke (with
    knowledge transfer to children), retire losers."""
    swarm = load_swarm()
    # idle drain: existing costs energy for every worker
    for name, w in swarm["workers"].items():
        _pay_energy(swarm, name, -ENERGY_IDLE_DRAIN)
    # starvation: workers with no energy die - but they TEACH first
    starved = []
    for name in list(swarm["workers"].keys()):
        w = swarm["workers"].get(name)
        if w and w.get("energy", 0) < ENERGY_STARVATION \
                and len(swarm["workers"]) > 1:
            teachings = teach_before_death(swarm, name)
            del swarm["workers"][name]
            starved.append({"worker": name, "taught": teachings})
    save_swarm(swarm)

    pending = [tid for tid, t in swarm["tasks"].items()
               if t["status"] == "pending"]
    auctioned = [auction(tid) for tid in pending]
    auctioned = [a for a in auctioned if a and a["winner"]]
    reproduced = []
    for name, w in list(swarm["workers"].items()):
        if w.get("wins", 0) >= REPRODUCE_THRESHOLD \
                and w.get("children", 0) < 3 \
                and w.get("energy", 0) >= ENERGY_REPRODUCE_COST:
            r = reproduce(name)
            if r and "child" in r:
                reproduced.append(r["child"])
    retired = retire_losing_workers()
    return {"auctioned": auctioned, "reproduced": reproduced,
            "retired": retired, "starved": starved}


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
