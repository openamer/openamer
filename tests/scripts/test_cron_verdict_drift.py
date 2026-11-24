"""Tests for scripts/cron_verdict_drift.py.

The checker exists because three of four "failed" cron jobs on 2026-11-24 were
not failing. Its value is entirely in NOT crying wolf, so these tests pin the
exclusions as hard as the findings: a job that has not had its first tick, a job
whose rows were pruned by the rolling history window, and a slot that is simply
still running must all stay silent.
"""

from __future__ import annotations

import importlib.util
import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
CHECKER = REPO_ROOT / "scripts" / "cron_verdict_drift.py"


@pytest.fixture()
def checker(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("cron_verdict_drift", CHECKER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "JOBS", tmp_path / "jobs.json")
    monkeypatch.setattr(module, "EXECUTIONS", tmp_path / "executions.db")
    return module


def write_board(path: Path, jobs: list[dict]) -> None:
    path.write_text(json.dumps({"jobs": jobs}), encoding="utf-8")


def write_history(path: Path, rows: list[dict]) -> None:
    connection = sqlite3.connect(path)
    connection.execute(
        "CREATE TABLE executions (id TEXT, job_id TEXT, source TEXT, process_id TEXT, "
        "pid INTEGER, process_started_at TEXT, status TEXT, claimed_at TEXT, "
        "started_at TEXT, finished_at TEXT, error TEXT)"
    )
    for index, row in enumerate(rows):
        connection.execute(
            "INSERT INTO executions VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (
                f"id{index}",
                row["job_id"],
                "builtin",
                None,
                None,
                None,
                row["status"],
                row.get("at"),
                row.get("at"),
                row.get("at"),
                row.get("error"),
            ),
        )
    connection.commit()
    connection.close()


def job(**overrides) -> dict:
    base = {
        "id": "job1",
        "name": "Test Job",
        "enabled": True,
        "last_status": "ok",
        "schedule": {"kind": "interval", "minutes": 30},
        "created_at": (datetime.now(timezone.utc) - timedelta(days=3)).isoformat(),
        "last_run_at": (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat(),
        "next_run_at": (datetime.now(timezone.utc) + timedelta(minutes=20)).isoformat(),
    }
    base.update(overrides)
    return base


NOW = datetime(2026, 11, 24, 23, 0, tzinfo=timezone.utc)


def test_agreement_produces_no_finding(checker):
    write_board(checker.JOBS, [job(last_status="ok")])
    write_history(checker.EXECUTIONS, [{"job_id": "job1", "status": "completed", "at": (NOW - timedelta(minutes=10)).isoformat()}])

    assert checker.findings(now=NOW) == []


def test_board_verdict_contradicting_history_is_reported(checker):
    """The measured bug: board says error, the newest durable run exited 0."""
    write_board(checker.JOBS, [job(last_status="error")])
    write_history(checker.EXECUTIONS, [{"job_id": "job1", "status": "completed", "at": (NOW - timedelta(minutes=5)).isoformat()}])

    found = checker.findings(now=NOW)

    assert [item["check"] for item in found] == ["DISAGREE"]
    assert "completed" in found[0]["detail"]


def test_unknown_outcome_is_reported(checker):
    write_board(checker.JOBS, [job(last_status="ok")])
    write_history(checker.EXECUTIONS, [{"job_id": "job1", "status": "unknown", "at": (NOW - timedelta(minutes=5)).isoformat()}])

    found = checker.findings(now=NOW)

    assert [item["check"] for item in found] == ["UNKNOWN"]


def test_running_slot_is_not_a_contradiction(checker):
    """A slot in flight has no verdict yet — reporting it would be noise."""
    write_board(checker.JOBS, [job(last_status="ok")])
    write_history(checker.EXECUTIONS, [{"job_id": "job1", "status": "running", "at": (NOW - timedelta(minutes=2)).isoformat()}])

    assert checker.findings(now=NOW) == []


def test_running_slot_past_its_grace_becomes_hung(checker):
    write_board(checker.JOBS, [job(last_status="ok")])
    write_history(checker.EXECUTIONS, [{"job_id": "job1", "status": "running", "at": (NOW - timedelta(hours=5)).isoformat()}])

    found = checker.findings(now=NOW)

    assert [item["check"] for item in found] == ["HUNG"]


def test_job_whose_first_tick_has_not_arrived_is_silent(checker):
    write_board(
        checker.JOBS,
        [
            job(
                created_at=(NOW - timedelta(minutes=1)).isoformat(),
                last_status="never",
                last_run_at=None,
                next_run_at=(NOW + timedelta(minutes=29)).isoformat(),
            )
        ],
    )
    write_history(checker.EXECUTIONS, [{"job_id": "other", "status": "completed", "at": (NOW - timedelta(hours=6)).isoformat()}])

    assert checker.findings(now=NOW) == []


def test_job_whose_rows_were_pruned_by_the_window_is_silent(checker):
    """A daily job has no row in a 6-hour window; that is not evidence it is dead."""
    write_board(checker.JOBS, [job(schedule={"kind": "interval", "minutes": 1440})])
    write_history(
        checker.EXECUTIONS,
        [
            {"job_id": "other", "status": "completed", "at": (NOW - timedelta(hours=6)).isoformat()},
            {"job_id": "other", "status": "completed", "at": (NOW - timedelta(minutes=1)).isoformat()},
        ],
    )

    assert checker.findings(now=NOW) == []


def test_short_interval_job_with_no_row_at_all_is_reported(checker):
    write_board(checker.JOBS, [job(schedule={"kind": "interval", "minutes": 30})])
    write_history(
        checker.EXECUTIONS,
        [
            {"job_id": "other", "status": "completed", "at": (NOW - timedelta(hours=6)).isoformat()},
            {"job_id": "other", "status": "completed", "at": (NOW - timedelta(minutes=1)).isoformat()},
        ],
    )

    found = checker.findings(now=NOW)

    assert [item["check"] for item in found] == ["NEVER"]


def test_overdue_job_is_reported(checker):
    write_board(checker.JOBS, [job(next_run_at=(NOW - timedelta(days=1)).isoformat())])
    write_history(checker.EXECUTIONS, [{"job_id": "job1", "status": "completed", "at": (NOW - timedelta(days=1)).isoformat()}])

    found = checker.findings(now=NOW)

    assert "OVERDUE" in [item["check"] for item in found]


def test_disabled_job_is_ignored(checker):
    write_board(checker.JOBS, [job(enabled=False, last_status="error")])
    write_history(checker.EXECUTIONS, [{"job_id": "job1", "status": "completed", "at": (NOW - timedelta(minutes=5)).isoformat()}])

    assert checker.findings(now=NOW) == []


def test_unreadable_inputs_exit_two(checker, monkeypatch):
    """Exit 2 is 'I could not measure', never 'everything is fine'."""
    monkeypatch.setattr("sys.argv", ["cron_verdict_drift.py"])

    assert checker.main() == 2
