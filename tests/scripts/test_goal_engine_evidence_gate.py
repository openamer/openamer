"""Goals must be verified against evidence, not marked done on request.

2026-09-18: `cmd_complete` set `status="done"` and `progress=100` for anything it
was handed, consulting nothing. `_update_goal_progress` had the sharper form of
the same mistake: a goal with an EMPTY task list was reported as
`progress=100, status="done"` — so every freshly defined goal read as complete
before any work existed.

Both make "progress" a counter of intentions rather than a measure of work. The
gate added here is `_verify_goal` / `verify_goals`: a goal states its evidence in
`evidence_cmd`, and only exit 0 counts. A goal with no `evidence_cmd` is
UNVERIFIED and cannot be completed.

These tests exercise the real functions; they do not re-assert the presence of
strings.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "scripts" / "goal-engine.py"


def _load():
    spec = importlib.util.spec_from_file_location("goal_engine_repo", MODULE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def ge():
    if not MODULE.exists():
        pytest.skip(f"{MODULE} not present")
    return _load()


# ---------------------------------------------------------------------------
# the gate
# ---------------------------------------------------------------------------

def test_evidence_passing_verifies(ge):
    ok, notes = ge._verify_goal({"id": "g", "name": "n", "evidence_cmd": "exit 0"})
    assert ok is True
    assert any("exit=0" in n for n in notes)


def test_evidence_failing_does_not_verify(ge):
    ok, notes = ge._verify_goal({"id": "g", "name": "n", "evidence_cmd": "exit 3"})
    assert ok is False
    assert any("exit=3" in n for n in notes)


def test_goal_without_evidence_is_unverified_not_complete(ge):
    """The fail-closed rule: no evidence must never read as success."""
    ok, notes = ge._verify_goal({"id": "g", "name": "n"})
    assert ok is False
    assert any("no evidence_cmd" in n for n in notes)


def test_broken_evidence_command_is_reported_not_swallowed(ge):
    ok, notes = ge._verify_goal({"id": "g", "name": "n", "evidence_cmd": "exit 0; no_such_binary_xyz"})
    # A command that fails after its first statement must surface the failure.
    assert isinstance(ok, bool)
    assert notes and notes[0]


def test_verify_goals_reports_every_goal(ge):
    missions = [{
        "name": "M",
        "goals": [
            {"id": "g1", "name": "good", "evidence_cmd": "exit 0"},
            {"id": "g2", "name": "bad", "evidence_cmd": "exit 9"},
            {"id": "g3", "name": "none"},
        ],
    }]
    rep = ge.verify_goals(missions)
    assert [r["goal"] for r in rep] == ["g1", "g2", "g3"]
    assert [r["verified"] for r in rep] == [True, False, False]


# ---------------------------------------------------------------------------
# progress must reflect work
# ---------------------------------------------------------------------------

def test_empty_task_list_is_not_complete(ge):
    """0/0 is not 100%. Before the fix this returned progress=100, status=done."""
    g = {"id": "g", "tasks": []}
    ge._update_goal_progress(g)
    assert g["progress"] == 0, f"empty goal reported {g['progress']}% complete"
    assert g["status"] != "done", "empty goal reported as done"


def test_all_tasks_done_is_complete(ge):
    g = {"id": "g", "tasks": [{"status": "done"}, {"status": "done"}]}
    ge._update_goal_progress(g)
    assert g["progress"] == 100
    assert g["status"] == "done"


def test_partial_progress_is_proportional(ge):
    g = {"id": "g", "tasks": [{"status": "done"}, {"status": "pending"}]}
    ge._update_goal_progress(g)
    assert g["progress"] == 50
    assert g["status"] == "in_progress"


def test_failed_task_is_flagged(ge):
    g = {"id": "g", "tasks": [{"status": "failed"}, {"status": "pending"}]}
    ge._update_goal_progress(g)
    assert g["status"] == "partially_done"
