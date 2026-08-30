"""Phase-22 tests: migration + global task market."""
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

spec2 = importlib.util.spec_from_file_location(
    "swarm_migration", REPO / "scripts" / "swarm_migration.py")
mig = importlib.util.module_from_spec(spec2)
sys.modules["swarm_migration"] = mig
spec2.loader.exec_module(mig)


@pytest.fixture
def fake_world(tmp_path, monkeypatch):
    monkeypatch.setattr(swarm, "SWARM_FILE", tmp_path / "swarm.json")
    monkeypatch.setattr(swarm, "TASKS_FILE", tmp_path / "tasks.json")
    monkeypatch.setattr(mig, "MARKET_FILE",
                        tmp_path / "darwin" / "task-market.json")
    # mig loaded its own swarm_os instance; point it at the patched one
    monkeypatch.setattr(mig, "swarm", swarm)
    monkeypatch.setattr(mig, "MIGRATION_LOG",
                        tmp_path / "darwin" / "migration-log.json")
    return tmp_path


def test_emigrate_removes_and_logs(fake_world):
    swarm.register_worker("traveler", ["code"], 20.0)
    swarm.register_worker("stay-home", ["code"], 10.0)
    r = mig.emigrate("traveler", "remote-machine-01")
    assert r["emigrated"] == "traveler"
    assert r["to"] == "remote-machine-01"
    swarm_w = swarm.load_swarm()
    assert "traveler" not in swarm_w["workers"]
    assert "stay-home" in swarm_w["workers"]
    log = mig._load(mig.MIGRATION_LOG, [])
    assert len(log) == 1 and log[0]["genome"]["energy"] >= 20.0


def test_emigrate_blocks_last_worker(fake_world):
    swarm.register_worker("only-one", ["code"], 20.0)
    r = mig.emigrate("only-one", "remote")
    assert "error" in r


def test_immigrate_registers_with_origin_tag(fake_world):
    record = {"worker": "traveler", "from": "remote-machine-01",
              "genome": {"energy": 20.0, "capabilities": ["code"],
                         "wins": 2, "losses": 0}}
    r = mig.immigrate(record)
    assert r["immigrated"] == "traveler@remote-machine-01"
    swarm_w = swarm.load_swarm()
    w = swarm_w["workers"]["traveler@remote-machine-01"]
    assert w["energy"] >= 5.0  # entry grant
    assert "code" in w["capabilities"]


def test_full_migration_cycle(fake_world):
    # emigrate here...
    swarm.register_worker("wanderer", ["code"], 20.0)
    swarm.register_worker("other", ["code"], 10.0)
    mig.emigrate("wanderer", "machine-b")
    # ...simulate machine-b sending the record back
    log = mig._load(mig.MIGRATION_LOG, [])
    r = mig.immigrate({**log[0], "from": "machine-b"})
    assert r["immigrated"] == "wanderer@machine-b"
    assert "wanderer@machine-b" in swarm.load_swarm()["workers"]


def test_market_publish_and_bid(fake_world):
    tid = mig.publish_task_globally("fix the bug", ["code"], reward=15.0)
    r = mig.place_bid(tid, "worker-x", "machine-b", fitness=30, energy=50)
    assert r["bid"] == 45.0  # 30 * (1 + 50/100)
    st = mig.market_status()
    assert st["open_tasks"] == 1


def test_settle_awards_highest_bid(fake_world):
    tid = mig.publish_task_globally("big task", ["code"], reward=100.0)
    mig.place_bid(tid, "weak", "machine-a", fitness=5, energy=10)
    mig.place_bid(tid, "strong", "machine-b", fitness=40, energy=80)
    settled = mig.settle_task(tid)
    assert settled["winner"] == "machine-b/strong"
    assert settled["reward"] == 100.0
    st = mig.market_status()
    assert st["open_tasks"] == 0 and st["settled_tasks"] == 1


def test_settle_fails_with_no_bids(fake_world):
    tid = mig.publish_task_globally("lonely task", [])
    assert mig.settle_task(tid) is None
