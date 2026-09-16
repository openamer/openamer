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


def test_stale_positional_baseline_does_not_freeze_trial(fake_world):
    """Regression: a trial whose executions table was reset/pruned used to sit
    "waiting" forever.

    The legacy baseline sliced `rows[executions_before:]`, so once the table
    held <= that many rows the slice was permanently empty and the trial never
    gathered evidence -- occupying one of only two trial slots (max_trials=2)
    and blocking every later candidate forever. Evidence must be counted by
    the trial's START TIME, not by a row offset that can go stale.
    """
    monkeypatch = pytest.MonkeyPatch()
    try:
        db = fake_world["cron"] / "executions.db"
        conn = sqlite3.connect(str(db))
        conn.execute("DROP TABLE IF EXISTS executions")
        conn.execute("CREATE TABLE executions (id TEXT, job_id TEXT, "
                     "status TEXT, claimed_at TEXT)")
        # trial started AFTER the existing rows -> 2 fresh completions
        conn.execute("INSERT INTO executions VALUES "
                     "('1','jobX','completed','2026-01-01T00:00:00+00:00')")
        conn.execute("INSERT INTO executions VALUES "
                     "('2','jobX','completed','2026-06-01T10:00:00+00:00')")
        conn.execute("INSERT INTO executions VALUES "
                     "('3','jobX','completed','2026-06-01T11:00:00+00:00')")
        conn.commit()
        conn.close()

        outcomes = darwin._execution_outcomes(
            "jobX", since_count=3, since_ts="2026-03-01T00:00:00+00:00")
        # the stale positional baseline (3 rows, offset 3) would give 0/0
        assert outcomes["completed"] == 2, outcomes
        assert outcomes["error"] == 0

        # and the pure positional path still works when no timestamp given
        legacy = darwin._execution_outcomes("jobX", since_count=3)
        assert legacy == {"completed": 0, "error": 0}
    finally:
        monkeypatch.undo()


def test_evaluate_trials_settles_with_timestamp_evidence(fake_world, monkeypatch):
    """End-to-end reproduction of the real freeze.

    The trial was started when the job had 6 completed runs, so
    `executions_before` was recorded as 6. The executions table was then
    reset/pruned, so it now holds exactly 6 rows again -- but three of those
    rows are runs that happened AFTER the trial started.

    Positional baseline `rows[6:]` is therefore empty -> "waiting" forever,
    holding one of only two trial slots. The timestamp window must see the
    three post-trial completions and settle the trial.
    """
    monkeypatch.setattr(darwin, "ROLLBACK_LOG", darwin.DARWIN_DIR / "rb.json")
    monkeypatch.setattr(darwin, "POPULATION_FILE",
                        darwin.DARWIN_DIR / "population.json")
    db = fake_world["cron"] / "executions.db"
    conn = sqlite3.connect(str(db))
    conn.execute("DROP TABLE IF EXISTS executions")
    conn.execute("CREATE TABLE executions (id TEXT, job_id TEXT, "
                 "status TEXT, claimed_at TEXT)")
    rows = [
        ("1", "2026-01-01T00:00:00+00:00"),  # pre-trial
        ("2", "2026-01-02T00:00:00+00:00"),  # pre-trial
        ("3", "2026-01-03T00:00:00+00:00"),  # pre-trial
        ("4", "2026-07-01T10:00:00+00:00"),  # AFTER trial start
        ("5", "2026-07-01T11:00:00+00:00"),  # AFTER trial start
        ("6", "2026-07-01T12:00:00+00:00"),  # AFTER trial start
    ]
    for rid, ts in rows:
        conn.execute("INSERT INTO executions VALUES (?,?,?,?)",
                     (rid, "jobX", "completed", ts))
    conn.commit()
    conn.close()

    trials_dir = darwin.DARWIN_DIR / "trials"
    trials_dir.mkdir(parents=True, exist_ok=True)
    (trials_dir / "jobX.json").write_text(json.dumps({
        "child": "good-skill__mutfix", "parent": "good-skill",
        "job_id": "jobX", "job_name": "x",
        "original_skills": ["good-skill"],
        "started": "2026-06-01T00:00:00+00:00",
        "executions_before": 6,   # stale baseline == current row count
    }), encoding="utf-8")
    # job must exist so end_trial can restore the parent skill
    (fake_world["cron"] / "jobs.json").write_text(json.dumps(
        {"jobs": [{"id": "jobX", "name": "x", "enabled": True,
                   "skills": ["good-skill__mutfix"]}]}), encoding="utf-8")

    # the stale positional baseline sees nothing (this is the bug)
    stale = darwin._execution_outcomes("jobX", since_count=6)
    assert stale == {"completed": 0, "error": 0}, stale

    # evaluate_trials must nevertheless settle it from the time window
    results = darwin.evaluate_trials(min_executions=2)
    assert len(results) == 1
    assert results[0]["status"] != "waiting", results
    assert results[0]["outcomes"]["completed"] == 3, results
