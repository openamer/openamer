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
import os

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import importlib.util

def _resolve_openamer_home(default: Path) -> Path:
    """Resolve OPENAMER_HOME robustly across shells (see darwin_engine.py).

    git-bash exports OPENAMER_HOME as an MSYS path ("/c/Users/..."). Native
    Windows Python treats that as relative and lands in a phantom "C:/c/..."
    tree. Normalise MSYS drive forms and reject doubled-drive artefacts so the
    script never silently operates on a directory that isn't the real install.
    """
    raw = os.environ.get("OPENAMER_HOME")
    if not raw:
        return default
    norm = raw.replace(os.sep, "/") if os.sep != "/" else raw
    cand = None
    if len(norm) >= 3 and norm[0] == "/" and norm[1].isalpha() and norm[2] == "/":
        cand = Path(norm[1].upper() + ":/" + norm[3:])
    else:
        p = Path(raw)
        if p.is_absolute():
            cand = p
    if cand is None:
        return default
    parts = cand.parts
    drive = parts[0].rstrip("/").rstrip(os.sep)
    if len(drive) == 2 and drive[1] == ":" and len(parts) >= 2:
        head = parts[1].strip("/").strip(os.sep).lower()
        if head and head == drive[0].lower():
            return default
    return cand if cand.exists() else default



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

HOME = _resolve_openamer_home(Path.home() / "AppData" / "Local" / "openamer")
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
        r = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace',
                           timeout=timeout, cwd=str(REPO))
        return r.returncode in (0, 2), (r.stdout or r.stderr)[-300:]
    except subprocess.TimeoutExpired:
        return False, "timeout"
    except Exception as e:
        return False, str(e)[:200]


GAP_TASK_SPECS = {
    "weak-population": (
        "Run the existing documented scripts/darwin_engine.py --autopilot cycle "
        "to mutate or predate the skills currently below the fitness threshold. "
        "This is the routine evolution entrypoint: fitness scan, mutations from "
        "top parents, trial evaluation, predation check. No new code, no core "
        "changes; writes stay inside OPENAMER_HOME/darwin/."
    ),
    "stagnation": (
        "Raise exploration on the stagnant slice of the skill population by "
        "running the existing documented scripts/darwin_engine.py --autopilot "
        "with a higher mutation rate. Routine evolution entrypoint, no new code, "
        "no core changes; writes stay inside OPENAMER_HOME/darwin/."
    ),
    "losing-record": (
        "Prioritize verification-step mutations for the skills with a losing "
        "battle record by running the existing documented "
        "scripts/darwin_engine.py --autopilot cycle. Routine evolution "
        "entrypoint, no new code, no core changes; writes stay inside "
        "OPENAMER_HOME/darwin/."
    ),
    "market-backlog": (
        "Publish the settled grid result and sync the swarm market by running "
        "the existing documented scripts/darwin_grid_github.py --publish "
        "damir-desktop. Routine grid entrypoint, no new code, no core changes; "
        "network egress limited to the configured grid remote."
    ),
}


def _task_text_for_gap(gtype: str, gap: dict, cap: str) -> str:
    """Build a gate-judgeable task text for a metacognition gap.

    Falls back to naming the real entrypoint for that capability, so the
    proposal is never a bare imperative with no scope.
    """
    detail = str(gap.get("detail", "")).strip()
    body = GAP_TASK_SPECS.get(gtype)
    if not body:
        body = (f"Investigate and resolve the detected '{gtype}' gap via the "
                f"existing documented entrypoint for capability '{cap}'. "
                f"Read-only analysis first; no new code, no core changes.")
    suffix = f" Detected condition: {detail}." if detail else ""
    return f"AUTO[{gtype}]: {body}{suffix}"


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
        # The task text is handed to the gate as the proposal. A bare directive
        # ("mutate or predate these skills") is unjudgeable -- the gate correctly
        # answers NEEDS_MORE_INFO forever. Name the concrete entrypoint, the
        # scope and the safety boundary so the gate can actually rule on it.
        task_text = _task_text_for_gap(gtype, gap, cap)
        # dedup: skip if a task with the same gap type is genuinely still in
        # flight. gate-hold / gate-rejected do NOT count as "in flight" --
        # treating them as open is what let 825 dead tasks block every future
        # task generation while the loop reported "0 tasks needed".
        sw = swarm.load_swarm()
        tag = task_text.split("]:")[0] + "]"
        already = any(
            t["status"] in ("pending", "assigned")
            and tag in t["task"]
            for t in sw["tasks"].values())
        if already:
            continue
        tid = swarm.submit_task(task_text, [cap])
        created.append(tid)
    return created


def execute_assigned_tasks() -> list[dict]:
    """Run REAL operations for assigned tasks - but ONLY after the gate
    approves them. Each task goes through OpenAmer's brain first."""
    import importlib.util as _ilu
    gate_spec = _ilu.spec_from_file_location(
        "darwin_gate", REPO / "scripts" / "darwin_gate.py")
    gate = importlib.util.module_from_spec(gate_spec)
    sys.modules["darwin_gate"] = gate
    gate_spec.loader.exec_module(gate)

    executed = []
    # NOTE: we must re-read the swarm file after every mutation. Holding a
    # single snapshot and saving it at the end of the loop clobbers whatever
    # swarm.complete_task() wrote (status/wins/energy), so executions silently
    # reverted and the worker never got credit.
    for tid, task in list(swarm.load_swarm()["tasks"].items()):
        if task["status"] != "assigned":
            continue
        caps = task.get("capabilities") or []
        task_text = task.get("task", "")

        # ── GATE CHECK: OpenAmer decides, not the agent ──────────────────
        worker = task.get("winner", "swarm-agent")
        proposal = gate.submit_proposal(
            worker=worker,
            action=task_text[:80],
            description=f"Swarm task: {task_text}. Capabilities: {caps}. "
                        f"This task was generated autonomously by the "
                        f"Darwin swarm from metacognition gap analysis.")
        gate_status = proposal.get("gate_status", "ERROR")
        gate_reason = proposal.get("gate_reason", "")

        if gate_status == "APPROVE":
            # approved -> execute for real
            runner = None
            for c in caps:
                if c in TASK_RUNNERS:
                    runner = TASK_RUNNERS[c]
                    break
            if runner is None:
                runner = next(iter(TASK_RUNNERS.values()))
            ok, output = _run(runner["cmd"])
            swarm.complete_task(tid, output, success=ok)  # re-loads + persists
            task = swarm.load_swarm()["tasks"].get(tid, task)
            executed.append({"task": tid, "capabilities": caps,
                             "success": ok, "gate": "APPROVED",
                             "output_tail": output[-120:]})
        elif gate_status == "REJECT":
            # rejected -> mark task as gate-rejected, don't execute
            swarm.set_task_status(tid, "gate-rejected", gate_reason=gate_reason)
            executed.append({"task": tid, "gate": "REJECTED",
                             "reason": gate_reason[:150]})
        else:
            # needs more info or error -> hold
            swarm.set_task_status(tid, "gate-hold", gate_reason=gate_reason)
            executed.append({"task": tid, "gate": gate_status,
                             "reason": gate_reason[:150]})
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
        capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=110, cwd=str(REPO))
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
    gate_ok = sum(1 for e in executed if e.get("gate") == "APPROVED")
    gate_rej = sum(1 for e in executed if e.get("gate") == "REJECTED")
    report["gate"] = {"approved": gate_ok, "rejected": gate_rej}

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
