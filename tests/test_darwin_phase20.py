"""Phase-20 tests: Swarm OS - autonomous swarm organization."""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "swarm_os", REPO / "scripts" / "swarm_os.py")
swarm = importlib.util.module_from_spec(spec)
sys.modules["swarm_os"] = swarm
spec.loader.exec_module(swarm)


@pytest.fixture
def fake_world(tmp_path, monkeypatch):
    monkeypatch.setattr(swarm, "SWARM_FILE", tmp_path / "swarm.json")
    monkeypatch.setattr(swarm, "TASKS_FILE", tmp_path / "tasks.json")
    return tmp_path


def test_register_and_submit(fake_world):
    w = swarm.register_worker("worker-a", ["code", "build"], 10.0)
    assert w["genome_fitness"] == 10.0
    tid = swarm.submit_task("build the thing", ["code"])
    assert len(tid) == 10


def test_auction_capability_match_wins(fake_world):
    swarm.register_worker("coder", ["code"], 5.0)
    swarm.register_worker("writer", ["write"], 50.0)  # higher fitness, wrong cap
    tid = swarm.submit_task("write code", ["code"])
    result = swarm.auction(tid)
    assert result["winner"] == "coder"  # capability beats raw fitness


def test_auction_fitness_breaks_ties(fake_world):
    swarm.register_worker("a", ["code"], 5.0)
    swarm.register_worker("b", ["code"], 50.0)
    tid = swarm.submit_task("task", ["code"])
    assert swarm.auction(tid)["winner"] == "b"


def test_auction_no_capable_worker(fake_world):
    swarm.register_worker("writer", ["write"], 50.0)
    tid = swarm.submit_task("code task", ["code"])
    assert swarm.auction(tid)["winner"] is None


def test_complete_task_updates_genome(fake_world):
    swarm.register_worker("w1", ["code"], 0)
    tid = swarm.submit_task("t", ["code"])
    swarm.auction(tid)
    swarm.complete_task(tid, "done!", success=True)
    s = swarm.swarm_status()
    assert s["total_wins"] == 1 and s["tasks_done"] == 1


def test_reproduction_requires_wins(fake_world):
    swarm.register_worker("young", ["code"], 0)
    r = swarm.reproduce("young")
    assert "error" in r  # needs 3 wins


def test_reproduction_creates_generation(fake_world):
    swarm.register_worker("champ", ["code"], 20)
    # grant 3 wins
    for _ in range(3):
        tid = swarm.submit_task("t", ["code"])
        swarm.auction(tid)
        swarm.complete_task(tid, "ok", success=True)
    r = swarm.reproduce("champ")
    assert r["child"] == "champ-gen1"
    assert r["generation"] == 2
    s = swarm.swarm_status()
    assert s["workers"] == 2


def test_tick_reproduces_and_fights(fake_world):
    swarm.register_worker("veteran", ["code"], 30)
    for _ in range(3):
        tid = swarm.submit_task("t", ["code"])
        swarm.auction(tid)
        swarm.complete_task(tid, "ok", success=True)
    t = swarm.tick()
    assert t["reproduced"] == ["veteran-gen1"]


def test_retire_losing_workers(fake_world):
    swarm.register_worker("loser", ["code"], 0)
    swarm_w = swarm.load_swarm()
    swarm_w["workers"]["loser"]["losses"] = 5
    swarm.save_swarm(swarm_w)
    swarm.register_worker("keeper", ["code"], 10)  # ensure >1 worker
    retired = swarm.retire_losing_workers()
    assert any(r["worker"] == "loser" for r in retired)
    assert "loser" not in swarm.load_swarm()["workers"]
