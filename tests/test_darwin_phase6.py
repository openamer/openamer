"""Phase-6 tests: real head-to-head execution, stuck-trial resolution."""
import importlib.util
import json
import sqlite3
import subprocess
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
    good = skills / "good-skill"
    good.mkdir(parents=True)
    (good / "SKILL.md").write_text(
        "# good\n\n## Verification\n```bash\necho parent-ok\n```\n", encoding="utf-8")
    bad = skills / "bad-skill"
    bad.mkdir()
    (bad / "SKILL.md").write_text(
        "# bad\n\n## Verification\n```bash\nexit 3\n```\n", encoding="utf-8")

    home = tmp_path / "home"
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
    monkeypatch.setattr(darwin, "CRON_JOBS_FILE", cron / "jobs.json")
    return {"skills": skills, "cron": cron, "home": home}


def test_run_skill_check_executes_real_bash(fake_world):
    res = darwin.run_skill_check("good-skill")
    assert res["ok"] is True
    assert res["exit_code"] == 0
    assert "parent-ok" in res["stdout_tail"]


def test_run_skill_check_catches_failure(fake_world):
    res = darwin.run_skill_check("bad-skill")
    assert res["ok"] is True
    assert res["exit_code"] == 3


def test_run_skill_check_no_block(fake_world):
    (fake_world["skills"] / "bad-skill" / "SKILL.md").write_text("# plain\n")
    res = darwin.run_skill_check("bad-skill")
    assert res["ok"] is False
    assert res["reason"] == "no executable block"


def test_head_to_head_child_wins_on_parent_failure(fake_world):
    # child: healthy; parent: exits 3
    off = darwin.DARWIN_DIR / "offspring" / "bad-skill__mutfix"
    off.mkdir(parents=True)
    (off / "SKILL.md").write_text(
        "# fixed\n\n## Verification\n```bash\necho child-ok\n```\n", encoding="utf-8")
    res = darwin.head_to_head("bad-skill", "bad-skill__mutfix")
    assert res["winner"] == "child"
    assert res["parent_result"]["exit_code"] == 3
    assert res["child_result"]["exit_code"] == 0
    # evidence file written
    files = list((darwin.DARWIN_DIR / "head2head").glob("*.json"))
    assert len(files) == 1


def test_head_to_head_parent_defends(fake_world):
    # child: broken (exit 5); parent: healthy
    off = darwin.DARWIN_DIR / "offspring" / "good-skill__mutbreak"
    off.mkdir(parents=True)
    (off / "SKILL.md").write_text(
        "# broken\n```bash\nexit 5\n```\n", encoding="utf-8")
    res = darwin.head_to_head("good-skill", "good-skill__mutbreak")
    assert res["winner"] == "parent"


def test_head_to_head_neither_executable(fake_world):
    res = darwin.head_to_head("ghost-a", "ghost-b")
    assert res["winner"] == "neither"


def test_resolve_stuck_runs_duel_and_settles(fake_world, monkeypatch):
    # build a trial that is overdue but has no cron evidence
    monkeypatch.setattr(darwin, "ROLLBACK_LOG", darwin.DARWIN_DIR / "rb.json")
    trial = {
        "child": "bad-skill__mutfix", "parent": "bad-skill",
        "job_id": "jobX", "job_name": "x",
        "original_skills": ["bad-skill"],
        "started": "2026-01-01T00:00:00+00:00",
        "executions_before": 0,
    }
    trials_dir = darwin.DARWIN_DIR / "trials"
    trials_dir.mkdir(parents=True, exist_ok=True)
    (trials_dir / "jobX.json").write_text(json.dumps(trial), encoding="utf-8")
    # child offspring exists and is healthy (from earlier test fixture pattern)
    off = darwin.DARWIN_DIR / "offspring" / "bad-skill__mutfix"
    off.mkdir(parents=True, exist_ok=True)
    (off / "SKILL.md").write_text(
        "# fixed\n\n## Verification\n```bash\necho ok\n```\n", encoding="utf-8")
    # add a job to jobs.json so end_trial can restore
    (fake_world["cron"] / "jobs.json").write_text(json.dumps(
        {"jobs": [{"id": "jobX", "name": "x", "enabled": True,
                   "skills": ["bad-skill__mutfix"]}]}), encoding="utf-8")

    settled = darwin.resolve_stuck_trials(timeout_hours=0, do_run=True)
    assert len(settled) == 1
    assert settled[0]["status"] == "won"
    assert settled[0]["via"] == "head_to_head"
    # trial closed
    t = json.loads((trials_dir / "jobX.json").read_text(encoding="utf-8"))
    assert t["ended"] is not None
