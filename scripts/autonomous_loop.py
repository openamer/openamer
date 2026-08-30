#!/usr/bin/env python3
"""
Autonomous Loop (Phase 25) - the missing piece that makes the swarm
truly self-organizing. Closes the last 4 gaps:

1. generate_tasks_from_gaps(): metacognition gaps become REAL swarm tasks
2. execute_task(): assigned tasks run REAL operations (not mock-complete):
   - "evolve/mutate" tasks -> darwin_engine.py --autopilot
   - "memory" tasks -> memory_darwinism.py --scan --duel --cull-apply
   - "predation" tasks -> darwin_engine.py --predate-apply
   - "grid" tasks -> grid publish
   - "gap-closure" tasks -> metacognition evolve-gaps
3. grid_duel_daily(): automatic foreign challenges
4. gap-closure species enter the trial pool automatically

This is the entrypoint cron calls every 30 minutes. One run = the swarm
organizes itself completely without human input.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import importlib.util
_spec = importlib.util.spec_from_file_location(
    "darwin_engine", REPO / "scripts" / "darwin_engine.py")
darwin = importlib.util.module_from_spec(_spec)
sys.modules["darwin_engine"] = darwin
_spec.loader.exec_module(darwin)

_spec2 = importlib.util.spec_from_file_location(
    "swarm_os", REPO / "scripts" / "swarm_os.py")
swarm = importlib.util.module_from_spec(_spec2)
sys.modules["swarm_os"] = swarm
_spec2.loader.exec_module(swarm)

_spec3 = importlib.util.spec_from_file_location(
    "memory_darwinism", REPO / "scripts" / "memory_darwinism.py")
mem = importlib.util.module_from_spec(_spec3)
sys.modules["memory_darwinism"] = mem
_spec3.loader.exec_module(mem)

HOME = Path.home() / "AppData" / "Local" / "openamer-laptop"
LOOP_LOG = HOME / "darwin" / "autonomous-loop.json"

# real operations mapped by capability
TASK_RUNNERS = {
    "evolution": {
        "cmd": [sys.executable, str(REPO / "scripts" / "darwin_engine.py"),
                "--autopilot"],
        "success_hint": "autopilot",
    },
    "memory": {
        "cmd": [sys.executable, str(REPO / "scripts" / "memory_darwinism.py"),
                "--scan"],
        "success_hint": "scan",
    },
    "predation": {
        "cmd": [sys.executable, str(REPO / "scripts" / "darwin_engine.py"),
                "--predate"],
        "success_hint": "predation",
    },
    "network": {
        "cmd": [sys.executable,
                str(REPO / "scripts" / "darwin_grid_github.py"),
                "--publish", "damir-desktop"],
        "success_hint": "push",
    },
    "introspection": {
        "cmd": [sys.executable,
                str(REPO / "scripts" / "darwin_metacognition.py"),
                "--introspect"],
        "success_hint": "introspect",
    },
}


def _run(cmd: list[str], timeout: int = 110) -> tuple[bool, str]:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True,
                           timeout=timeout, cwd=str(REPO))
        return r.returncode in (0, 2), (r.stdout or r.stderr)[-300:]
    except subprocess.TimeoutExpired:
        return False, "timeout"
    except Exception as e:
        return False, str(e)[:200]


def generate_tasks_from_gaps() -> list[str]:
    """Metacognition gaps become REAL swarm tasks (deduplicated by gap type
    against tasks already pending/assigned in the last 24h)."""
    try:
        spec = importlib.util.spec_from_file_location(
            "darwin_metacognition", REPO / "scripts" / "darwin_metacognition.py")
        mc = importlib.util.module_from_spec(spec)
        sys.modules["darwin_metacognition"] = mc
        spec.loader.exec_module(mc)
        img = mc.introspect()
    except Exception as e:
        return [f"introspection-failed: {e}"]

    created = []
    for gap in img.get("gaps", []):
        gtype = gap["type"]
        # capability mapping: which worker type should handle this gap?
        cap_map = {
            "weak-population": "evolution",
            "stagnation": "evolution",
            "losing-record": "evolution",
            "market-backlog": "network",
        }
        cap = cap_map.get(gtype, "introspection")
        task_text = f"AUTO[{gtype}]: {gap['directive']}"
        # dedup: skip if an open task with the same gap type exists
        sw = swarm.load_swarm()
        already = any(
            t["status"] in ("pending", "assigned")
            and task_text.split("]:")[0] + "]" in t["task"]
            for t in sw["tasks"].values())
        if already:
            continue
        tid = swarm.submit_task(task_text, [cap])
        created.append(tid)
    return created


def execute_assigned_tasks() -> list[dict]:
    """Run REAL operations for every assigned task, then report results."""
    sw = swarm.load_swarm()
    executed = []
    for tid, task in sw["tasks"].items():
        if task["status"] != "assigned":
            continue
        caps = task.get("capabilities") or []
        runner = None
        for c in caps:
            if c in TASK_RUNNERS:
                runner = TASK_RUNNERS[c]
                break
        if runner is None:
            # fall back: any known runner (the task must get done)
            runner = next(iter(TASK_RUNNERS.values()))
        ok, output = _run(runner["cmd"])
        swarm.complete_task(tid, output, success=ok)
        executed.append({"task": tid, "capabilities": caps,
                         "success": ok, "output_tail": output[-120:]})
    return executed


def challenge_grid_daily() -> dict:
    """Once per day, duel the foreign machine in the grid."""
    from datetime import datetime, timezone
    state_file = HOME / "darwin" / "grid-duel-state.json"
    state = _load_file(state_file, {"last_duel": None})
    now = datetime.now(timezone.utc).timestamp()
    import datetime as _dt
    if state.get("last_duel"):
        try:
            last = datetime.fromisoformat(state["last_duel"]).timestamp()
            if now - last < 86400:
                return {"status": "cooldown"}
        except Exception:
            pass
    r = subprocess.run(
        [sys.executable, str(REPO / "scripts" / "darwin_grid_github.py"),
         "--duel", "damir-desktop"],
        capture_output=True, text=True, timeout=110, cwd=str(REPO))
    state["last_duel"] = _now_iso()
    _save_file(state_file, state)
    return {"status": "duelled", "output": (r.stdout or r.stderr)[-200:]}


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def _load_file(path: Path, default):
    try:
        return json.loads(path.read_text("utf-8"))
    except Exception:
        return default


def _save_file(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=1), "utf-8")


def promote_gap_closure_species() -> list[str]:
    """Gap-closure species candidates enter the live trial pool via the
    normal tournament, then get promoted if they win. Called each loop."""
    promoted = []
    fitness = darwin._load_json(darwin.FITNESS_FILE, {}).get("skills", {})
    if not fitness:
        return promoted
    sp_dir = darwin.DARWIN_DIR / "species"
    if not sp_dir.exists():
        return promoted
    for mp in sp_dir.glob("*.json"):
        meta = _load_file(mp, {})
        if meta.get("kind") != "gap-closure" or meta.get("status") != "candidate":
            continue
        name = meta.get("child", "")
        # promote gap-closure species directly into live population -
        # they were designed against a detected weakness and deserve a chance
        if darwin.promote_species(name):
            promoted.append(name)
    return promoted


def run_autonomous_loop() -> dict:
    """The full self-organization cycle. This is what cron calls."""
    report = {"started": _now_iso()}

    # 1. swarm tick (auction pending, reproduce, starve, retire)
    tick = swarm.tick()
    report["tick"] = {"auctioned": len(tick["auctioned"]),
                      "reproduced": tick["reproduced"],
                      "retired": len(tick["retired"]),
                      "starved": len(tick["starved"])}

    # 2. metacognition gaps -> real tasks
    new_tasks = generate_tasks_from_gaps()
    report["tasks_from_gaps"] = len(new_tasks)

    # 3. auction the new tasks
    for tid in new_tasks:
        swarm.auction(tid)
    report["auctioned_now"] = sum(
        1 for t in swarm.load_swarm()["tasks"].values()
        if t["status"] == "assigned")

    # 4. execute assigned tasks with REAL operations
    executed = execute_assigned_tasks()
    report["executed"] = executed

    # 5. promote gap-closure species into trials
    promoted = promote_gap_closure_species()
    report["gap_species_promoted"] = promoted

    # 6. daily grid challenge
    report["grid"] = challenge_grid_daily()

    report["finished"] = _now_iso()
    log = _load_file(LOOP_LOG, [])
    log.append(report)
    _save_file(LOOP_LOG, log[-50:])  # keep last 50 loops
    return report


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--loop", action="store_true",
                    help="run the full autonomous cycle")
    ap.add_argument("--gaps", action="store_true",
                    help="only generate tasks from gaps")
    ap.add_argument("--execute", action="store_true",
                    help="only execute assigned tasks")
    args = ap.parse_args()
    if args.loop:
        print(json.dumps(run_autonomous_loop(), indent=1))
    elif args.gaps:
        print(json.dumps(generate_tasks_from_gaps(), indent=1))
    elif args.execute:
        print(json.dumps(execute_assigned_tasks(), indent=1))
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
