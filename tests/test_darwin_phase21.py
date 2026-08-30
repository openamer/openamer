"""Phase-21 tests: energy economics + genetic drift."""
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


def test_register_gives_starting_energy(fake_world):
    w = swarm.register_worker("w1", ["code"], starting_energy=50.0)
    assert w["energy"] == 50.0


def test_completed_task_pays_energy(fake_world):
    swarm.register_worker("w1", ["code"], starting_energy=10.0)
    tid = swarm.submit_task("t", ["code"])
    swarm.auction(tid)  # costs 1
    swarm.complete_task(tid, "ok", success=True)  # pays 10
    swarm_w = swarm.load_swarm()
    assert swarm_w["workers"]["w1"]["energy"] == 19.0  # 10 - 1 + 10


def test_failed_task_costs_energy(fake_world):
    swarm.register_worker("w1", ["code"], starting_energy=10.0)
    tid = swarm.submit_task("t", ["code"])
    swarm.auction(tid)  # -1
    swarm.complete_task(tid, "boom", success=False)  # -5
    swarm_w = swarm.load_swarm()
    assert swarm_w["workers"]["w1"]["energy"] == 4.0  # 10 - 1 - 5


def test_energy_boosts_auction_score(fake_world):
    # two identical workers, but w2 is wealthy -> w2 wins despite same fitness
    swarm.register_worker("poor", ["code"], genome_fitness=10,
                          starting_energy=1.0)
    swarm.register_worker("rich", ["code"], genome_fitness=10,
                          starting_energy=100.0)
    tid = swarm.submit_task("t", ["code"])
    assert swarm.auction(tid)["winner"] == "rich"


def test_reproduction_costs_and_inherits_energy(fake_world):
    swarm.register_worker("rich-parent", ["code"], starting_energy=60.0)
    for _ in range(3):
        tid = swarm.submit_task("t", ["code"])
        swarm.auction(tid)
        swarm.complete_task(tid, "ok", True)  # +10 -1 each = +9
    # now at 60 + 27 = 87 energy
    r = swarm.reproduce("rich-parent")
    assert "child" in r
    swarm_w = swarm.load_swarm()
    parent = swarm_w["workers"]["rich-parent"]
    child = swarm_w["workers"][r["child"]]
    assert parent["energy"] == 87.0 - 20.0  # reproduction cost
    assert child["energy"] == (87.0) / 2.0  # half of parent's pre-cost energy


def test_reproduction_blocked_without_energy(fake_world):
    swarm.register_worker("broke-champ", ["code"], starting_energy=5.0)
    # grant wins without energy via direct manipulation
    swarm_w = swarm.load_swarm()
    swarm_w["workers"]["broke-champ"]["wins"] = 5
    swarm.save_swarm(swarm_w)
    r = swarm.reproduce("broke-champ")
    assert "error" in r and "energy" in r["error"]


def test_genetic_drift_changes_capabilities(fake_world):
    caps = ["code", "evolution", "memory"]
    # force drift by using a fixed rng with high rate
    import random
    rng = random.Random(1)
    varied = set()
    for _ in range(30):
        varied.add(tuple(swarm.drift_capabilities(caps, rng, rate=1.0)))
    assert len(varied) > 1  # drift produces different variants


def test_no_drift_at_rate_zero(fake_world):
    import random
    caps = ["code", "evolution"]
    out = swarm.drift_capabilities(caps, random.Random(1), rate=0.0)
    assert out == caps


def test_tick_starves_broke_workers(fake_world):
    swarm.register_worker("rich", ["code"], starting_energy=100.0)
    swarm.register_worker("dying", ["code"], starting_energy=0.3)
    t = swarm.tick()
    assert "dying" in t["starved"]
    swarm_w = swarm.load_swarm()
    assert "dying" not in swarm_w["workers"]
    assert "rich" in swarm_w["workers"]  # last-one-standing protection not
    # triggered because rich still lives


def test_last_worker_never_starves(fake_world):
    swarm.register_worker("sole-survivor", ["code"], starting_energy=0.1)
    t = swarm.tick()
    assert t["starved"] == []  # swarm never dies completely
    assert "sole-survivor" in swarm.load_swarm()["workers"]
