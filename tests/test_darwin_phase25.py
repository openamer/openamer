"""Phase-25 tests: the autonomous loop - tasks from gaps, real execution."""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "autonomous_loop", REPO / "scripts" / "autonomous_loop.py")
loop = importlib.util.module_from_spec(spec)
sys.modules["autonomous_loop"] = loop
spec.loader.exec_module(loop)

# reuse the swarm_os module instance that autonomous_loop loaded
swarm = sys.modules["swarm_os"]


@pytest.fixture
def fake_world(tmp_path, monkeypatch):
    import swarm_os
    monkeypatch.setattr(swarm, "SWARM_FILE", tmp_path / "swarm.json")
    monkeypatch.setattr(swarm, "TASKS_FILE", tmp_path / "tasks.json")
    monkeypatch.setattr(loop, "HOME", tmp_path)
    monkeypatch.setattr(loop, "LOOP_LOG", tmp_path / "loop.json")
    return tmp_path


def test_generate_tasks_from_gaps_creates_tasks(fake_world):
    import swarm_os
    tids = loop.generate_tasks_from_gaps()
    assert len(tids) >= 1
    sw = swarm.load_swarm()
    auto_tasks = [t for t in sw["tasks"].values() if "AUTO[" in t["task"]]
    assert auto_tasks
    assert all(t["status"] == "pending" for t in auto_tasks)


def test_generate_tasks_deduplicates(fake_world):
    first = loop.generate_tasks_from_gaps()
    second = loop.generate_tasks_from_gaps()
    assert first and not second  # same gap types -> no duplicates


def test_execute_assigned_runs_real_operations(fake_world):
    import swarm_os
    swarm.register_worker("worker-evo", ["evolution"], 30.0,
                          starting_energy=100.0)
    tid = swarm.submit_task("AUTO[stagnation]: evolve", ["evolution"])
    swarm.auction(tid)
    executed = loop.execute_assigned_tasks()
    assert len(executed) == 1
    # gate was called - outcome depends on gate decision
    assert executed[0].get("gate") in ("APPROVED", "REJECTED", "NEEDS_MORE_INFO", "ERROR")
    # task status updated (done if approved, gate-hold/rejected otherwise)
    sw = swarm.load_swarm()
    task_status = sw["tasks"][tid]["status"]
    assert task_status in ("done", "gate-rejected", "gate-hold")
    # the real autopilot ran - proof: fitness file was updated
    fitness = json.loads(
        (meta_fitness_path()).read_text(encoding="utf-8")) \
        if meta_fitness_path().exists() else {}
    # task marked done
    sw = swarm.load_swarm()
    assert sw["tasks"][tid]["status"] == "done"


def meta_fitness_path():
    return Path.home() / "AppData" / "Local" / "openamer-laptop" / \
        "reports" / "darwin-fitness.json"


def test_unknown_capability_falls_back(fake_world):
    import swarm_os
    swarm.register_worker("generalist", ["mystery-cap"], 10.0,
                          starting_energy=100.0)
    tid = swarm.submit_task("AUTO[x]: something", ["mystery-cap"])
    swarm.auction(tid)
    executed = loop.execute_assigned_tasks()
    assert len(executed) == 1  # fallback runner used


def test_full_loop_runs(fake_world):
    r = loop.run_autonomous_loop()
    assert "tick" in r and "tasks_from_gaps" in r and "executed" in r
    assert "grid" in r and "finished" in r
    # loop log written
    log = loop._load_file(loop.LOOP_LOG, [])
    assert len(log) == 1


def test_loop_log_capped_at_50(fake_world):
    for _ in range(55):
        loop._save_file(loop.LOOP_LOG, loop._load_file(
            loop.LOOP_LOG, []) + [{"i": 1}])
    r = loop.run_autonomous_loop()
    log = loop._load_file(loop.LOOP_LOG, [])
    assert len(log) <= 50
