"""Phase-15 tests: self-tuning constants from ecosystem health."""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "darwin_engine", REPO / "scripts" / "darwin_engine.py")
darwin = importlib.util.module_from_spec(spec)
sys.modules["darwin_engine"] = darwin
spec.loader.exec_module(darwin)


@pytest.fixture
def fake_world(tmp_path, monkeypatch):
    home = tmp_path / "home"
    (home / "reports").mkdir(parents=True)
    (home / "skills").mkdir()
    monkeypatch.setattr(darwin, "SKILLS_DIR", home / "skills")
    monkeypatch.setattr(darwin, "HOME", home)
    monkeypatch.setattr(darwin, "DARWIN_DIR", home / "darwin")
    monkeypatch.setattr(darwin, "POPULATION_FILE",
                        home / "darwin" / "population.json")
    monkeypatch.setattr(darwin, "TUNING_FILE", home / "darwin" / "tuning.json")
    monkeypatch.setattr(darwin, "HISTORY_FILE",
                        home / "reports" / "darwin-history.jsonl")
    return home


def _write_history(home, entries):
    with open(darwin.HISTORY_FILE, "w", encoding="utf-8") as f:
        for e in entries:
            f.write(json.dumps(e) + "\n")


def test_get_tuning_defaults_when_no_file(fake_world):
    t = darwin.get_tuning()
    assert t["epsilon"] == 0.3
    assert t["max_trials"] == 2
    assert t["max_losses"] == 3


def test_tuning_persists(fake_world):
    darwin.TUNING_FILE.parent.mkdir(parents=True, exist_ok=True)
    darwin.TUNING_FILE.write_text(json.dumps({"epsilon": 0.4}), encoding="utf-8")
    assert darwin.get_tuning()["epsilon"] == 0.4


def test_auto_tune_stagnating_raises_exploration(fake_world):
    # 4 flat snapshots -> stagnating
    _write_history(fake_world, [
        {"when": f"2026-01-0{i}T00:00:00+00:00", "skills": {"a": 5}}
        for i in range(1, 5)])
    t = darwin.auto_tune()
    assert t["epsilon"] == 0.5
    assert t["max_trials"] == 3
    assert "stagnating" in t["reason"]
    # persisted
    assert darwin.get_tuning()["epsilon"] == 0.5


def test_auto_tune_declining_tightens(fake_world):
    _write_history(fake_world, [
        {"when": "2026-01-01T00:00:00+00:00", "skills": {"a": 9}},
        {"when": "2026-01-02T00:00:00+00:00", "skills": {"a": 5}},
        {"when": "2026-01-03T00:00:00+00:00", "skills": {"a": 2}},
    ])
    t = darwin.auto_tune()
    assert t["epsilon"] == 0.15
    assert t["max_losses"] == 2
    assert "declining" in t["reason"]


def test_auto_tune_healthy_keeps_defaults(fake_world):
    _write_history(fake_world, [
        {"when": "2026-01-01T00:00:00+00:00", "skills": {"a": 2}},
        {"when": "2026-01-02T00:00:00+00:00", "skills": {"a": 9}},
        {"when": "2026-01-03T00:00:00+00:00", "skills": {"a": 12}},
    ])
    t = darwin.auto_tune()
    assert t["epsilon"] == 0.3
    assert t["max_trials"] == 2
    assert "healthy" in t["reason"]


def test_auto_tune_idempotent_when_unchanged(fake_world):
    _write_history(fake_world, [
        {"when": "2026-01-01T00:00:00+00:00", "skills": {"a": 1}},
        {"when": "2026-01-02T00:00:00+00:00", "skills": {"a": 9}},
        {"when": "2026-01-03T00:00:00+00:00", "skills": {"a": 19}},
    ])
    darwin.auto_tune()
    first = darwin.TUNING_FILE.read_text(encoding="utf-8")
    darwin.auto_tune()
    second = darwin.TUNING_FILE.read_text(encoding="utf-8")
    # second run only changes tuned_at; constants stay identical
    t1 = json.loads(first)
    t2 = json.loads(second)
    for k in ("epsilon", "max_trials", "max_losses"):
        assert t1[k] == t2[k]
