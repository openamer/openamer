"""Phase-10 tests: retire losers, status overview, full autopilot pipeline."""
import importlib.util
import json
import sqlite3
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
    cron = home / "cron"
    cron.mkdir(parents=True)
    (cron / "jobs.json").write_text(json.dumps({"jobs": []}), encoding="utf-8")
    db = cron / "executions.db"
    conn = sqlite3.connect(str(db))
    conn.execute("CREATE TABLE executions (id TEXT, job_id TEXT, status TEXT)")
    conn.commit()
    conn.close()

    monkeypatch.setattr(darwin, "SKILLS_DIR", skills)
    monkeypatch.setattr(darwin, "HOME", home)
    monkeypatch.setattr(darwin, "DARWIN_DIR", home / "darwin")
    monkeypatch.setattr(darwin, "POPULATION_FILE", home / "darwin" / "population.json")
    monkeypatch.setattr(darwin, "LINEAGE_FILE", home / "darwin" / "lineage.json")
    monkeypatch.setattr(darwin, "ROLLBACK_LOG", home / "darwin" / "rollback-log.json")
    monkeypatch.setattr(darwin, "SYNTHESIS_LOG", home / "darwin" / "synthesis-log.json")
    monkeypatch.setattr(darwin, "HARVESTED_FILE",
                        home / "darwin" / "harvested-blueprints.json")
    monkeypatch.setattr(darwin, "HISTORY_FILE",
                        home / "reports" / "darwin-history.jsonl")
    monkeypatch.setattr(darwin, "ARENA_FILE", home / "darwin" / "arena.json")
    monkeypatch.setattr(darwin, "CRON_JOBS_FILE", cron / "jobs.json")
    return {"skills": skills, "home": home, "cron": cron}


def _make_species(fake_world, name, status="installed"):
    home = fake_world["home"] if isinstance(fake_world, dict) else fake_world
    sp = home / "darwin" / "species"
    sp.mkdir(parents=True, exist_ok=True)
    (sp / name).mkdir(exist_ok=True)
    (sp / name / "SKILL.md").write_text(f"# {name}\n```bash\necho ok\n```\n",
                                        encoding="utf-8")
    (sp / f"{name}.json").write_text(json.dumps(
        {"child": name, "kind": "speciation", "status": status}), encoding="utf-8")


def test_retire_losers_after_threshold(fake_world):
    _make_species(fake_world, "loser-skill")
    _make_species(fake_world, "winner-skill")
    darwin.POPULATION_FILE.write_text(json.dumps({
        "loser-skill": {"wins": 0, "losses": 3},
        "winner-skill": {"wins": 2, "losses": 1},
    }), encoding="utf-8")
    retired = darwin.retire_losers(max_losses=3)
    names = [r["name"] for r in retired]
    assert names == ["loser-skill"]
    assert not (fake_world["home"] / "darwin" / "species" / "loser-skill").exists()
    assert (fake_world["home"] / "darwin" / "quarantine" / "loser-skill").exists()
    # winner untouched
    assert (fake_world["home"] / "darwin" / "species" / "winner-skill").exists()
    # rollback log has the retirement for reversibility
    log = json.loads(darwin.ROLLBACK_LOG.read_text(encoding="utf-8"))
    assert any(e["skill"] == "loser-skill" and e.get("reason") == "arena-loses"
               for e in log)


def test_retire_spares_equal_or_winning_record(fake_world):
    _make_species(fake_world, "balanced-skill")
    darwin.POPULATION_FILE.write_text(json.dumps({
        "balanced-skill": {"wins": 3, "losses": 3},
    }), encoding="utf-8")
    assert darwin.retire_losers(max_losses=3) == []  # losses <= wins -> safe


def test_retire_below_threshold_ignored(fake_world):
    _make_species(fake_world, "young-skill")
    darwin.POPULATION_FILE.write_text(json.dumps({
        "young-skill": {"wins": 0, "losses": 2},
    }), encoding="utf-8")
    assert darwin.retire_losers(max_losses=3) == []


def test_retired_species_can_be_restored_via_rollback(fake_world):
    _make_species(fake_world, "doomed")
    darwin.POPULATION_FILE.write_text(json.dumps({
        "doomed": {"wins": 0, "losses": 5}}), encoding="utf-8")
    darwin.retire_losers(max_losses=3)
    restored = darwin.rollback(1)
    assert restored == ["doomed"]
    # restored back into the SPECIES dir? No - rollback restores to SKILLS_DIR.
    # The skill is live again as a regular skill; meta stays retired in species.
    assert (fake_world["skills"] / "doomed" / "SKILL.md").exists()


def test_status_overview_shape(fake_world):
    _make_species(fake_world, "some-species")
    darwin.POPULATION_FILE.write_text(json.dumps({"x": {"wins": 1}}),
                                      encoding="utf-8")
    s = darwin.status_overview()
    for key in ("when", "population", "fittest", "weakest", "species",
                "active_trials", "harvested_blueprints", "genome_records",
                "trend"):
        assert key in s
    assert s["species"]["installed"] == 1
    assert s["genome_records"] == 1


def test_autopilot_full_pipeline_runs(fake_world, capsys):
    # seed: harvested blueprints + a promoted species so the pipeline has work
    hdir = fake_world["home"] / "darwin"
    hdir.mkdir(parents=True, exist_ok=True)
    (hdir / "harvested-blueprints.json").write_text(
        json.dumps([{"name": "darwin-harvested-test-thing",
                     "topic": "work/missing-config.yaml", "hits": 9, "fix_hint": ""}]),
        encoding="utf-8")
    # give the fitness file one snapshot so speciate has a fitness source
    (fake_world["home"] / "reports" / "darwin-fitness.json").write_text(
        json.dumps({"updated": "2026-01-01", "skills": {
            "seed": {"fitness": 5, "usage": 1, "health": 1, "age_days": 1,
                     "mutations_won": 0, "mutations_lost": 0}}}),
        encoding="utf-8")
    code = darwin.autopilot(min_executions=2)
    out = capsys.readouterr().out
    assert "synthesized" in out or "promoted species" in out
    assert code in (0, 2)
