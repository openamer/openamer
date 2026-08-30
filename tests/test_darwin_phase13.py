"""Phase-13 tests: meta-evolution - operator selection learns."""
import importlib.util
import json
import random
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
    skills = tmp_path / "skills"
    skills.mkdir(parents=True)
    home = tmp_path / "home"
    (home / "reports").mkdir(parents=True)
    monkeypatch.setattr(darwin, "SKILLS_DIR", skills)
    monkeypatch.setattr(darwin, "HOME", home)
    monkeypatch.setattr(darwin, "DARWIN_DIR", home / "darwin")
    monkeypatch.setattr(darwin, "POPULATION_FILE", home / "darwin" / "population.json")
    monkeypatch.setattr(darwin, "LINEAGE_FILE", home / "darwin" / "lineage.json")
    monkeypatch.setattr(darwin, "OP_STATS_FILE", home / "darwin" / "op-stats.json")
    monkeypatch.setattr(darwin, "HISTORY_FILE",
                        home / "reports" / "darwin-history.jsonl")
    return home


def test_record_op_outcome_accumulates(fake_world):
    darwin.record_op_outcome("add_pitfall", True)
    darwin.record_op_outcome("add_pitfall", True)
    darwin.record_op_outcome("add_pitfall", False)
    stats = json.loads(darwin.OP_STATS_FILE.read_text(encoding="utf-8"))
    assert stats["add_pitfall"] == {"uses": 3, "wins": 2}


def test_weighted_choice_prefers_winning_op(fake_world):
    # add_pitfall has a proven 100% win rate, others never used
    darwin.OP_STATS_FILE.parent.mkdir(parents=True, exist_ok=True)
    darwin.OP_STATS_FILE.write_text(json.dumps({
        "add_pitfall": {"uses": 10, "wins": 9},
        "tighten_trigger": {"uses": 10, "wins": 0},
        "broaden_trigger": {"uses": 10, "wins": 1},
        "add_verification_step": {"uses": 10, "wins": 0},
    }), encoding="utf-8")
    rng = random.Random(7)
    picks = {darwin.weighted_op_choice(rng, epsilon=0.0) for _ in range(30)}
    assert picks == {"add_pitfall"}  # with 0 exploration, always the winner


def test_weighted_choice_explores_with_epsilon(fake_world):
    darwin.OP_STATS_FILE.parent.mkdir(parents=True, exist_ok=True)
    darwin.OP_STATS_FILE.write_text(json.dumps({
        "add_pitfall": {"uses": 10, "wins": 10},
    }), encoding="utf-8")
    rng = random.Random(7)
    picks = {darwin.weighted_op_choice(rng, epsilon=1.0) for _ in range(50)}
    assert len(picks) > 1  # full exploration touches multiple ops


def test_weighted_choice_empty_stats_is_uniform(fake_world):
    rng = random.Random(7)
    picks = {darwin.weighted_op_choice(rng, epsilon=0.0) for _ in range(50)}
    assert len(picks) >= 2  # no stats -> fair exploration


def test_mutate_uses_weighted_selection(fake_world, monkeypatch):
    skills = fake_world if isinstance(fake_world, Path) else fake_world["skills"]
    for name in ("p1", "p2"):
        (skills / name).mkdir()
        (skills / name / "SKILL.md").write_text(f"# {name}\n", encoding="utf-8")
    fitness = {n: {"fitness": 10, "usage": 1, "health": 1, "age_days": 1,
                   "mutations_won": 0, "mutations_lost": 0}
               for n in ("p1", "p2")}
    offspring = darwin.mutate(fitness, top_n=2, apply=True)
    # every offspring records which op created it
    assert all("op" in o for o in offspring)
    assert all(o["op"] in darwin.MUTATION_OPS for o in offspring)
