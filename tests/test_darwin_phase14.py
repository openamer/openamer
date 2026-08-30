"""Phase-14 tests: explainability + species-aware rollback."""
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
    (skills / "known-skill").mkdir(parents=True)
    home = tmp_path / "home"
    (home / "reports").mkdir(parents=True)
    monkeypatch.setattr(darwin, "SKILLS_DIR", skills)
    monkeypatch.setattr(darwin, "HOME", home)
    monkeypatch.setattr(darwin, "DARWIN_DIR", home / "darwin")
    monkeypatch.setattr(darwin, "POPULATION_FILE",
                        home / "darwin" / "population.json")
    monkeypatch.setattr(darwin, "LINEAGE_FILE", home / "darwin" / "lineage.json")
    monkeypatch.setattr(darwin, "OP_STATS_FILE", home / "darwin" / "op-stats.json")
    monkeypatch.setattr(darwin, "ROLLBACK_LOG", home / "darwin" / "rollback-log.json")
    monkeypatch.setattr(darwin, "HISTORY_FILE",
                        home / "reports" / "darwin-history.jsonl")
    monkeypatch.setattr(darwin, "CRON_JOBS_FILE", home / "cron" / "jobs.json")
    return home


def test_explain_unknown_skill(fake_world):
    e = darwin.explain_skill("ghost")
    assert e["exists"] is False


def test_explain_returns_breakdown(fake_world):
    darwin.FITNESS_FILE.write_text(json.dumps({
        "updated": "x", "skills": {"known-skill": {
            "fitness": 20, "usage": 3, "health": 1, "age_days": 2,
            "mutations_won": 1, "mutations_lost": 0}}}), encoding="utf-8")
    darwin.POPULATION_FILE.parent.mkdir(parents=True, exist_ok=True)
    darwin.POPULATION_FILE.write_text(json.dumps(
        {"known-skill": {"wins": 1, "losses": 0}}), encoding="utf-8")
    e = darwin.explain_skill("known-skill")
    assert e["exists"] is True
    assert e["breakdown"]["usage_points"] == 9      # 3 * 3
    assert e["breakdown"]["health_points"] == 5     # 1 * 5
    assert e["breakdown"]["mutation_bonus"] == 2    # 1 win * 2
    assert e["genome"]["wins"] == 1


def test_explain_detects_operator_quality(fake_world):
    darwin.OP_STATS_FILE.parent.mkdir(parents=True, exist_ok=True)
    darwin.OP_STATS_FILE.write_text(json.dumps(
        {"add_pitfall": {"uses": 4, "wins": 3}}), encoding="utf-8")
    e = darwin.explain_skill("some-skill__mutadd_pitfall")
    assert e["operator_quality"]["op"] == "add_pitfall"
    assert e["operator_quality"]["win_rate"] == 0.75


def test_explain_detects_species_origin(fake_world):
    sp = darwin.DARWIN_DIR / "species"
    sp.mkdir(parents=True, exist_ok=True)
    (sp / "my-species.json").write_text(json.dumps(
        {"child": "my-species", "kind": "speciation"}), encoding="utf-8")
    e = darwin.explain_skill("my-species")
    assert e["is_species"] is True


def test_retire_then_unretire_returns_to_species_dir(fake_world):
    # setup: installed species with losing record
    sp = darwin.DARWIN_DIR / "species"
    sp.mkdir(parents=True, exist_ok=True)
    (sp / "doomed").mkdir()
    (sp / "doomed" / "SKILL.md").write_text("# doomed\n", encoding="utf-8")
    (sp / "doomed.json").write_text(json.dumps(
        {"child": "doomed", "status": "installed"}), encoding="utf-8")
    darwin.POPULATION_FILE.write_text(json.dumps(
        {"doomed": {"wins": 0, "losses": 4}}), encoding="utf-8")

    retired = darwin.retire_losers(max_losses=3)
    assert [r["name"] for r in retired] == ["doomed"]
    q = darwin.DARWIN_DIR / "quarantine" / "doomed"
    assert q.exists()

    # now undo it - must go back to species/, NOT skills/
    ok = darwin.rollback_species("doomed")
    assert ok is True
    assert (sp / "doomed" / "SKILL.md").exists()
    assert not q.exists()
    meta = json.loads((sp / "doomed.json").read_text(encoding="utf-8"))
    assert meta["status"] == "installed"
    # rollback log entry for the retirement was removed
    log = json.loads(darwin.ROLLBACK_LOG.read_text(encoding="utf-8"))
    assert not any(e.get("reason") == "arena-loses" for e in log)


def test_unretire_fails_when_not_retired(fake_world):
    assert darwin.rollback_species("never-retired") is False
