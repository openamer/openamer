"""Phase-3 tests: semantic mutations, quarantine, rollback, autopilot."""
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
    d = skills / "alpha"
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text("# alpha\n\n## Trigger\nRun when X.\n", encoding="utf-8")
    # dead skill: no usage, no cron
    dead = skills / "dead-skill"
    dead.mkdir()
    (dead / "SKILL.md").write_text("# dead\n", encoding="utf-8")

    home = tmp_path / "home"
    cron = home / "cron"
    cron.mkdir(parents=True)
    jobs = {"jobs": [{"id": "job1", "name": "alpha-job", "enabled": True,
                      "skills": ["alpha"]}]}
    (cron / "jobs.json").write_text(json.dumps(jobs), encoding="utf-8")
    db = cron / "executions.db"
    conn = sqlite3.connect(str(db))
    conn.execute("CREATE TABLE executions (id TEXT, job_id TEXT, status TEXT)")
    conn.commit()
    conn.close()

    monkeypatch.setattr(darwin, "SKILLS_DIR", skills)
    monkeypatch.setattr(darwin, "HOME", home)
    monkeypatch.setattr(darwin, "DARWIN_DIR", home / "darwin")
    monkeypatch.setattr(darwin, "POPULATION_FILE", home / "darwin" / "population.json")
    monkeypatch.setattr(darwin, "CRON_JOBS_FILE", cron / "jobs.json")
    monkeypatch.setattr(darwin, "ROLLBACK_LOG", home / "darwin" / "rollback-log.json")
    return {"skills": skills, "cron": cron, "home": home}


# ── semantic mutations ────────────────────────────────────────────────────────

def test_tighten_replaces_existing_trigger_body():
    text = "# s\n\n## Trigger\nRun when X.\n\n## Verification\ncheck.\n"
    out = darwin._semantic_mutation(text, "tighten_trigger", darwin.random.Random(42))
    assert "Run when X." not in out          # old body replaced
    assert "## Verification\ncheck." in out  # other section untouched
    assert out.count("## Trigger") == 1       # no duplicate section


def test_tighten_appends_when_no_trigger_section():
    text = "# s\nnothing here\n"
    out = darwin._semantic_mutation(text, "tighten_trigger", darwin.random.Random(42))
    assert "## Trigger" in out


def test_pitfall_pool_varies_not_duplicated():
    text = "# s\n\n## Pitfall\nold body\n"
    out = darwin._semantic_mutation(text, "add_pitfall", darwin.random.Random(42))
    assert out.count("## Pitfall") == 1
    assert "old body" not in out


# ── quarantine / rollback ─────────────────────────────────────────────────────

def _fitness_for(world):
    # dead-skill must score <= 0 and usage 0; alpha has a cron job so protected
    return {
        "alpha": {"fitness": 10, "usage": 3, "health": 1, "age_days": 1,
                  "mutations_won": 0, "mutations_lost": 0},
        "dead-skill": {"fitness": -2, "usage": 0, "health": 1, "age_days": 100,
                       "mutations_won": 0, "mutations_lost": 0},
    }


def test_quarantine_dry_run_moves_nothing(fake_world):
    moved = darwin.quarantine(_fitness_for(fake_world), threshold=0, dry_run=True)
    assert [m["skill"] for m in moved] == ["dead-skill"]
    assert (fake_world["skills"] / "dead-skill").exists()  # untouched


def test_quarantine_apply_moves_and_rollback_restores(fake_world):
    moved = darwin.quarantine(_fitness_for(fake_world), threshold=0, dry_run=False)
    assert [m["skill"] for m in moved] == ["dead-skill"]
    assert not (fake_world["skills"] / "dead-skill").exists()
    assert (darwin.DARWIN_DIR / "quarantine" / "dead-skill" / "SKILL.md").exists()
    restored = darwin.rollback(1)
    assert restored == ["dead-skill"]
    assert (fake_world["skills"] / "dead-skill" / "SKILL.md").exists()
    assert not (darwin.DARWIN_DIR / "quarantine" / "dead-skill").exists()


def test_quarantine_never_touches_cron_referenced_skill(fake_world):
    fit = _fitness_for(fake_world)
    fit["alpha"] = {**fit["alpha"], "fitness": -5, "usage": 0}  # make alpha look dead
    moved = darwin.quarantine(fit, threshold=0, dry_run=False)
    assert all(m["skill"] != "alpha" for m in moved)
    assert (fake_world["skills"] / "alpha").exists()  # protected


# ── autopilot ─────────────────────────────────────────────────────────────────

def test_autopilot_runs_full_cycle(fake_world, capsys):
    code = darwin.autopilot(min_executions=2)
    out = capsys.readouterr().out
    assert "[autopilot] fitness computed" in out
    assert "[autopilot] report ->" in out
    assert code in (0, 2)
