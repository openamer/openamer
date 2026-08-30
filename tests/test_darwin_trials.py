"""Phase-2 tests: trial swap, real execution evidence, promotion."""
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
    """Fake skills dir, cron jobs.json and executions.db."""
    skills = tmp_path / "skills"
    for name in ("alpha", "beta"):
        d = skills / name
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text(f"# {name}\n", encoding="utf-8")

    home = tmp_path / "home"
    cron = home / "cron"
    cron.mkdir(parents=True)
    jobs = {"jobs": [{
        "id": "job1", "name": "alpha-job", "enabled": True,
        "skills": ["alpha", "shared"],
    }]}
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
    return {"skills": skills, "cron": cron, "home": home, "jobs": jobs}


def _add_execution(fake_world, job_id: str, status: str):
    db = fake_world["cron"] / "executions.db"
    conn = sqlite3.connect(str(db))
    conn.execute("INSERT INTO executions VALUES (?, ?, ?)", ("x", job_id, status))
    conn.commit()
    conn.close()


def test_start_trial_swaps_skill(fake_world):
    trial = darwin.start_trial("alpha", "alpha__mutX")
    assert trial is not None
    assert trial["job_id"] == "job1"
    jobs = json.loads((fake_world["cron"] / "jobs.json").read_text(encoding="utf-8"))
    assert jobs["jobs"][0]["skills"] == ["alpha__mutX", "shared"]
    assert trial["original_skills"] == ["alpha", "shared"]


def test_start_trial_no_match(fake_world):
    assert darwin.start_trial("does-not-exist", "child") is None


def test_end_trial_restores_skills(fake_world):
    darwin.start_trial("alpha", "alpha__mutX")
    trial = darwin.end_trial("job1", won=False)
    assert trial["won"] is False
    jobs = json.loads((fake_world["cron"] / "jobs.json").read_text(encoding="utf-8"))
    assert jobs["jobs"][0]["skills"] == ["alpha", "shared"]


def test_evaluate_trials_waiting_then_lost(fake_world):
    darwin.start_trial("alpha", "alpha__mutX")
    # no executions yet -> waiting
    results = darwin.evaluate_trials(min_executions=2)
    assert results[0]["status"] == "waiting"
    # 1 completed, 1 error -> lost
    _add_execution(fake_world, "job1", "completed")
    _add_execution(fake_world, "job1", "error")
    results = darwin.evaluate_trials(min_executions=2)
    assert results[0]["status"] == "lost"
    # job restored
    jobs = json.loads((fake_world["cron"] / "jobs.json").read_text(encoding="utf-8"))
    assert jobs["jobs"][0]["skills"] == ["alpha", "shared"]


def test_evaluate_trials_won_promotes_child(fake_world):
    # create the child offspring first (promotion requires it to exist)
    child_dir = darwin.DARWIN_DIR / "offspring" / "alpha__mutX"
    child_dir.mkdir(parents=True)
    (child_dir / "SKILL.md").write_text("# alpha EVOLVED\n", encoding="utf-8")
    darwin.start_trial("alpha", "alpha__mutX")
    _add_execution(fake_world, "job1", "completed")
    _add_execution(fake_world, "job1", "completed")
    results = darwin.evaluate_trials(min_executions=2)
    assert results[0]["status"] == "won"
    # child content now installed as the live skill
    live = (fake_world["skills"] / "alpha" / "SKILL.md").read_text(encoding="utf-8")
    child_md = (darwin.DARWIN_DIR / "offspring" / "alpha__mutX" / "SKILL.md")
    assert live == child_md.read_text(encoding="utf-8")
    # parent archived
    archives = list((darwin.DARWIN_DIR / "archive").iterdir())
    assert len(archives) == 1
