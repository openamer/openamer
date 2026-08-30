"""Phase-8 tests: fitness history/trend, species arena."""
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
    skills = tmp_path / "skills"
    skills.mkdir(parents=True)
    home = tmp_path / "home"
    (home / "reports").mkdir(parents=True)
    monkeypatch.setattr(darwin, "SKILLS_DIR", skills)
    monkeypatch.setattr(darwin, "HOME", home)
    monkeypatch.setattr(darwin, "DARWIN_DIR", home / "darwin")
    monkeypatch.setattr(darwin, "POPULATION_FILE", home / "darwin" / "population.json")
    monkeypatch.setattr(darwin, "LINEAGE_FILE", home / "darwin" / "lineage.json")
    monkeypatch.setattr(darwin, "HISTORY_FILE", home / "reports" / "darwin-history.jsonl")
    monkeypatch.setattr(darwin, "ARENA_FILE", home / "darwin" / "arena.json")
    return home


# ── history / trend ──────────────────────────────────────────────────────────

def test_history_appends_snapshots(fake_world):
    fit = {"a": {"fitness": 5}, "b": {"fitness": 3}}
    n1 = darwin.record_history(fit)
    n2 = darwin.record_history({**fit, "a": {"fitness": 7}})
    assert n1 == 1 and n2 == 2
    lines = [json.loads(l) for l in
             open(darwin.HISTORY_FILE, encoding="utf-8")]
    assert lines[1]["skills"]["a"] == 7


def test_trend_needs_two_snapshots(fake_world):
    darwin.record_history({"a": {"fitness": 5}})
    t = darwin.fitness_trend()
    assert t["snapshots"] == 1


def test_trend_rising_falling_new(fake_world):
    darwin.record_history({"a": {"fitness": 5}, "b": {"fitness": 9}})
    # a rises 5->8, b falls 9->2, c is new. Population: 14 -> 11 (falling, correct math)
    darwin.record_history({"a": {"fitness": 8}, "b": {"fitness": 2},
                           "c": {"fitness": 1}})
    t = darwin.fitness_trend()
    assert t["snapshots"] == 2
    assert t["skills"]["a"]["trend"] == "rising"
    assert t["skills"]["a"]["delta"] == 3
    assert t["skills"]["b"]["trend"] == "falling"
    assert t["skills"]["c"]["trend"] == "new"
    assert t["population_trend"] == "falling"
    assert t["population_delta"] == -3


# ── arena ────────────────────────────────────────────────────────────────────

def _make_species(home, name, status="installed", body="echo ok"):
    sp = home / "darwin" / "species"
    sp.mkdir(parents=True, exist_ok=True)
    (sp / name).mkdir(exist_ok=True)
    (sp / name / "SKILL.md").write_text(
        f"# {name}\n```bash\n{body}\n```\n", encoding="utf-8")
    (sp / f"{name}.json").write_text(json.dumps(
        {"child": name, "kind": "speciation", "status": status}), encoding="utf-8")


def test_arena_needs_two_installed(fake_world):
    _make_species(fake_world, "only-one")
    assert darwin.species_arena() == []


def test_arena_fights_and_records_genome(fake_world):
    _make_species(fake_world, "species-healthy", body="echo ok")
    _make_species(fake_world, "species-broken", body="exit 4")
    fights = darwin.species_arena(min_interval_minutes=0)
    assert len(fights) == 1
    f = fights[0]
    assert f["status"] == "fought"
    # arena pairs oldest-fight-first = alphabetical here: broken is 'a',
    # healthy is 'b'. Healthy (exit 0) must beat broken (exit 4).
    assert {f["a"], f["b"]} == {"species-broken", "species-healthy"}
    exits = {f["a"]: f["a_exit"], f["b"]: f["b_exit"]}
    assert exits["species-broken"] == 4
    assert exits["species-healthy"] == 0
    assert f["winner"] == "child"  # healthy (b) wins
    # genome updated: one species has a win, the other a loss
    pop = json.loads(darwin.POPULATION_FILE.read_text(encoding="utf-8"))
    total_wins = sum(g.get("wins", 0) for g in pop.values())
    total_losses = sum(g.get("losses", 0) for g in pop.values())
    assert total_wins == 1 and total_losses == 1


def test_arena_rate_limit(fake_world):
    _make_species(fake_world, "s1")
    _make_species(fake_world, "s2")
    darwin.species_arena(min_interval_minutes=0)
    fights2 = darwin.species_arena(min_interval_minutes=60)
    assert fights2 == [{"status": "cooldown"}]
