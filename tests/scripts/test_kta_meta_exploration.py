"""Regression test: KTA's meta-RL experiment must write what it claims.

Live bug 23.09.26: ``experiment_meta_insight()`` read meta_state.json, emitted
the string "increased exploration on the underused strategy" and wrote nothing.
``meta_learn.choose_strategy()`` had no exploration parameter at all, so the
claim had no consumer — the experiment ran log-only for weeks while still
logging ``"measurable": true``.

These tests pin the producer/consumer contract that replaced it: the experiment
writes ``exploration_bias``, choose_strategy honours it exactly once, and an
older state file cannot raise KeyError.
"""
import json
import sys
from pathlib import Path

TRAIN = Path(__file__).resolve().parents[2] / "scripts" / "training"
sys.path.insert(0, str(TRAIN))


def _state(tmp_path, replay=3, fresh=1, bias=None):
    p = tmp_path / "meta_state.json"
    s = {
        "lr_history": [],
        "current_lr": 2e-4,
        "strategy_stats": {
            "replay": {"uses": replay, "avg_drop": 0.14},
            "fresh": {"uses": fresh, "avg_drop": 0.3},
        },
        "memory_usefulness": {},
        "error_patterns": {},
        "total_measurements": 4,
    }
    if bias is not None:
        s["exploration_bias"] = bias
    p.write_text(json.dumps(s), encoding="utf-8")
    return p


def test_experiment_writes_exploration_bias(tmp_path, monkeypatch):
    """The experiment must mutate state, not just return a claim string."""
    import knowledge_to_action as kta

    st = _state(tmp_path)
    monkeypatch.setattr(kta, "T", str(tmp_path))

    result = kta.experiment_meta_insight()

    assert result["measurable"] is True
    assert json.loads(st.read_text(encoding="utf-8"))["exploration_bias"] == 1.0


def test_choose_strategy_honours_bias_exactly_once(tmp_path, monkeypatch):
    """Bias forces the underused strategy, then clears — no permanent pin."""
    import meta_learn as ml

    st = _state(tmp_path, bias=1.0)
    monkeypatch.setattr(ml, "STATE", str(st))

    choice, why = ml.choose_strategy()
    assert choice == "fresh", why  # fresh=1 is the less-used strategy
    assert json.loads(st.read_text(encoding="utf-8"))["exploration_bias"] == 0.0

    # a later call is no longer forced (still no bias, choice is free again)
    ml.choose_strategy()
    assert json.loads(st.read_text(encoding="utf-8"))["exploration_bias"] == 0.0


def test_experiment_does_not_boost_when_data_is_sufficient(tmp_path, monkeypatch):
    """Enough samples on both arms => no exploration boost, no state write."""
    import knowledge_to_action as kta

    st = _state(tmp_path, replay=9, fresh=9)
    monkeypatch.setattr(kta, "T", str(tmp_path))

    result = kta.experiment_meta_insight()

    assert "enough data" in result["result"]
    assert "exploration_bias" not in json.loads(st.read_text(encoding="utf-8"))


def test_load_state_backfills_key_absent_from_older_file(tmp_path, monkeypatch):
    """A state file written before exploration_bias existed must not KeyError."""
    import meta_learn as ml

    p = tmp_path / "meta_state.json"
    p.write_text(json.dumps({"strategy_stats": {}, "current_lr": 2e-4}), encoding="utf-8")
    monkeypatch.setattr(ml, "STATE", str(p))

    s = ml.load_state()

    assert s["exploration_bias"] == 0.0
    assert s["strategy_stats"] == {}
