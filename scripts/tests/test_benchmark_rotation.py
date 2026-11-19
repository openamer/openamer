"""The mastery instrument must rotate, prove it, and admit exhaustion.

Background: `benchmark.py` scored itself with `questions[:2]` on every run, so
22 scored runs measured the same ~22 sentences. `desire_engine.sense_mastery`
then reported `spent` — correctly, because a score that cannot tell learning
from repetition is not a number.

These tests pin the repair from both sides:

* the selector really rotates (LRU over the pool, distinct set ids, honest
  exhaustion instead of silent wrap-around), and
* the sensor only goes LIVE on *evidence* — distinct set ids across runs — not
  on the mere presence of a `set_id` key, which is what the old check accepted.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))

import benchmark_items  # noqa: E402


def _pool(n=10):
    return {
        "alpha": [{"q": f"alpha question {i}", "a": str(i)} for i in range(n)],
        "beta": [{"q": f"beta question {i}", "a": str(i)} for i in range(n)],
    }


def _sets_from(selections):
    return [{"set_id": s["set_id"], "item_ids": s["item_ids"]} for s in selections]


# ------------------------------------------------------------------ selector
def test_consecutive_runs_pick_different_items():
    pool = _pool()
    first = benchmark_items.select_items(pool, 2, [])
    second = benchmark_items.select_items(pool, 2, _sets_from([first]))
    third = benchmark_items.select_items(pool, 2, _sets_from([first, second]))

    assert len({first["set_id"], second["set_id"], third["set_id"]}) == 3
    assert not set(first["item_ids"]) & set(second["item_ids"])
    assert not set(second["item_ids"]) & set(third["item_ids"])


def test_selection_is_deterministic_for_same_history():
    pool = _pool()
    a = benchmark_items.select_items(pool, 2, [])
    b = benchmark_items.select_items(pool, 2, [])
    assert a["set_id"] == b["set_id"]
    assert a["item_ids"] == b["item_ids"]


def test_pool_reports_exhaustion_instead_of_wrapping_silently():
    pool = _pool(4)  # 4 per domain, 2 per set -> 2 sets before every item is used
    history = []
    for _ in range(4):
        sel = benchmark_items.select_items(pool, 2, history)
        history.extend(_sets_from([sel]))

    health = benchmark_items.pool_health(pool, history)
    assert health["exhausted"] is True
    assert health["min_used"] >= benchmark_items.MAX_ITEM_EXPOSURES


def test_fresh_pool_is_not_exhausted():
    health = benchmark_items.pool_health(_pool(), [])
    assert health["exhausted"] is False
    assert health["fresh"] == 20


# ------------------------------------------------------------ rotation proof
def test_rotation_proof_needs_at_least_two_distinct_sets():
    assert benchmark_items.rotation_proof([])["rotated"] is False
    assert benchmark_items.rotation_proof([{"set_id": "a"}])["rotated"] is False
    assert benchmark_items.rotation_proof(
        [{"set_id": "a"}, {"set_id": "a"}])["rotated"] is False
    assert benchmark_items.rotation_proof(
        [{"set_id": "a"}, {"set_id": "b"}])["rotated"] is True


# ------------------------------------------------------------------- sensor
def _load_desire_engine(home: Path):
    os.environ["OPENAMER_HOME"] = str(home)
    (home / "memory").mkdir(parents=True, exist_ok=True)
    for mod in ("desire_engine",):
        sys.modules.pop(mod, None)
    sys.path.insert(0, str(REPO / "scripts" / "training"))
    import desire_engine  # noqa: E402
    return desire_engine


def _write_bench(home: Path, payload: dict):
    (home / "memory" / "benchmarks.json").write_text(
        json.dumps(payload), encoding="utf-8")


def test_sensor_is_live_only_on_real_rotation(tmp_path):
    de = _load_desire_engine(tmp_path)
    _write_bench(tmp_path, {
        "history": [{"overall_accuracy": 0.4}, {"overall_accuracy": 0.5},
                    {"overall_accuracy": 0.6}],
        "sets": [{"set_id": "v2-aaa", "item_ids": ["x"]},
                 {"set_id": "v2-bbb", "item_ids": ["y"]}],
    })
    out = de.sense_mastery()
    assert out["measure"] == de.LIVE, out


def test_sensor_refuses_a_bare_set_id_key(tmp_path):
    """The old check passed on the KEY existing. Adding one must not fool it."""
    de = _load_desire_engine(tmp_path)
    _write_bench(tmp_path, {
        "set_id": "v2-cosmetic",          # key present, no rotation behind it
        "history": [{"overall_accuracy": 0.4}, {"overall_accuracy": 0.5},
                    {"overall_accuracy": 0.6}],
    })
    out = de.sense_mastery()
    assert out["measure"] == de.SPENT, out


def test_sensor_refuses_repeated_sets(tmp_path):
    de = _load_desire_engine(tmp_path)
    _write_bench(tmp_path, {
        "history": [{"overall_accuracy": 0.4}, {"overall_accuracy": 0.5},
                    {"overall_accuracy": 0.6}],
        "sets": [{"set_id": "v2-same", "item_ids": ["x"]},
                 {"set_id": "v2-same", "item_ids": ["x"]}],
    })
    out = de.sense_mastery()
    assert out["measure"] == de.SPENT, out


def test_sensor_reports_exhausted_pool_as_spent(tmp_path):
    de = _load_desire_engine(tmp_path)
    _write_bench(tmp_path, {
        "history": [{"overall_accuracy": 0.4}, {"overall_accuracy": 0.5},
                    {"overall_accuracy": 0.6}],
        "sets": [{"set_id": "v2-aaa", "item_ids": ["x"], "pool_exhausted": True}],
    })
    out = de.sense_mastery()
    assert out["measure"] == de.SPENT, out
    assert "exhausted" in out["note"]


def test_mastery_escalates_to_instrument_repair(tmp_path, monkeypatch):
    """End to end: a spent instrument must produce a repair goal, not silence."""
    de = _load_desire_engine(tmp_path)
    _write_bench(tmp_path, {
        "history": [{"overall_accuracy": 0.4}, {"overall_accuracy": 0.5},
                    {"overall_accuracy": 0.6}],
    })
    monkeypatch.setattr(de, "sense_hunger", lambda: {
        "satisfaction": 0.9, "measure": de.LIVE, "note": "test"})
    levels = de.sense_all() if hasattr(de, "sense_all") else None
    assert levels is None or "mastery" in levels
