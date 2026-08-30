#!/usr/bin/env python3
"""
Migration & Global Task Market (Phase 22).

Workers migrate between machine swarms via the Darwin Grid, and tasks
float on a global market where ANY machine's workers can bid.

Migration = a worker emigrates locally and immigrates on the target
machine (recorded as a JSON file in the grid repo / grid server).

Task market = open tasks are published to the grid; foreign workers bid
by posting their fitness + energy; the best bid wins remotely.

This module works with BOTH backends:
  - grid server (HTTP, darwin_grid_server.py)
  - github backend (darwin_grid_github.py)
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
    "swarm_os", REPO / "scripts" / "swarm_os.py")
swarm = importlib.util.module_from_spec(_spec)
sys.modules["swarm_os"] = swarm
_spec.loader.exec_module(swarm)

HOME = Path.home() / "AppData" / "Local" / "openamer-laptop"
MARKET_FILE = HOME / "darwin" / "task-market.json"
MIGRATION_LOG = HOME / "darwin" / "migration-log.json"


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


def emigrate(worker_name: str, target_machine: str) -> dict | None:
    """A worker leaves the local swarm for another machine.

    The worker (with its genome, energy, capabilities) is written to the
    migration log and removed locally. The target machine's swarm picks
    it up on its next tick via immigrate().
    """
    s = swarm
    sw = s.load_swarm()
    w = sw["workers"].get(worker_name)
    if not w:
        return None
    if len(sw["workers"]) <= 1:
        return {"error": "cannot emigrate the last worker"}
    record = {
        "worker": worker_name, "from": "local", "to": target_machine,
        "emigrated": _now(),
        "genome": w,
    }
    del sw["workers"][worker_name]
    s.save_swarm(sw)
    log = _load(MIGRATION_LOG, [])
    log.append(record)
    _save(MIGRATION_LOG, log)
    return {"emigrated": worker_name, "to": target_machine,
            "energy": w.get("energy", 0),
            "capabilities": w.get("capabilities", [])}


def immigrate(record: dict) -> dict:
    """Receive an immigrant worker from another machine."""
    name = record.get("worker", "")
    if not name:
        return {"error": "no worker name"}
    # adjust the name to show its origin
    origin = record.get("from", "foreign")
    new_name = f"{name}@{origin}"
    swarm_local = swarm.load_swarm()
    genome = record.get("genome", {})
    genome["immigrated"] = _now()
    genome["energy"] = max(genome.get("energy", 0), 5.0)  # entry grant
    swarm_local["workers"][new_name] = genome
    swarm.save_swarm(swarm_local)
    return {"immigrated": new_name,
            "capabilities": genome.get("capabilities", [])}


def publish_task_globally(task: str, capabilities: list[str],
                          reward: float = 10.0) -> str:
    """Put a task on the global market: any machine's workers may bid."""
    market = _load(MARKET_FILE, {"open": {}, "settled": {}})
    task_id = uuid.uuid4().hex[:10]
    market["open"][task_id] = {
        "task": task, "capabilities": capabilities, "reward": reward,
        "published": _now(), "machine": "local", "bids": {},
    }
    _save(MARKET_FILE, market)
    return task_id


def place_bid(task_id: str, worker: str, machine: str,
              fitness: float, energy: float) -> dict:
    """A foreign worker bids on an open market task."""
    market = _load(MARKET_FILE, {"open": {}, "settled": {}})
    task = market["open"].get(task_id)
    if not task:
        return {"error": "task not open"}
    bid_score = fitness * (1.0 + max(energy, 0) / 100.0)
    task["bids"][f"{machine}/{worker}"] = {
        "fitness": fitness, "energy": energy, "bid": round(bid_score, 2),
    }
    _save(MARKET_FILE, market)
    return {"bid": round(bid_score, 2), "task": task_id}


def settle_task(task_id: str) -> dict | None:
    """Settle a market task: highest bid wins, reward recorded."""
    market = _load(MARKET_FILE, {"open": {}, "settled": {}})
    task = market["open"].get(task_id)
    if not task or not task["bids"]:
        return None
    best_worker, best_bid = None, -1
    for key, bid in task["bids"].items():
        if bid["bid"] > best_bid:
            best_bid, best_worker = bid["bid"], key
    task["settled"] = _now()
    task["winner"] = best_worker
    task["winning_bid"] = best_bid
    market["settled"][task_id] = task
    del market["open"][task_id]
    _save(MARKET_FILE, market)
    return {"task": task_id, "winner": best_worker, "bid": best_bid,
            "reward": task["reward"]}


def market_status() -> dict:
    market = _load(MARKET_FILE, {"open": {}, "settled": {}})
    return {"open_tasks": len(market["open"]),
            "settled_tasks": len(market["settled"])}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--emigrate", nargs=2, metavar=("WORKER", "TARGET"))
    ap.add_argument("--immigrate", metavar="RECORD_FILE")
    ap.add_argument("--publish", metavar="TASK")
    ap.add_argument("--market", action="store_true")
    args = ap.parse_args()
    if args.emigrate:
        print(json.dumps(emigrate(args.emigrate[0], args.emigrate[1]),
                         indent=1))
    elif args.immigrate:
        print(json.dumps(immigrate(_load(Path(args.immigrate), {})),
                         indent=1))
    elif args.publish:
        print(json.dumps(publish_task_globally(args.publish, []), indent=1))
    elif args.market:
        print(json.dumps(market_status(), indent=1))
    else:
        ap.print_help()
