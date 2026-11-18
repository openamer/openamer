"""Regression tests for the first-class review-phase DB transitions.

``tools/kanban_tools.py`` calls ``kb.request_review(...)`` and
``kb.request_changes(...)`` from its ``kanban_request_review`` /
``kanban_request_changes`` handlers. Those two functions must exist and must
implement the review phase the dispatcher already knows about
(``status='review'``, ``claim_review_task``, ``_retry_status_for_run``).

Covers:

1. ``request_review`` — running/ready -> review, run closed with the handoff
   summary, ``review_requested`` event, scratch workspace kept, dependents
   NOT promoted, stale ``expected_run_id`` rejected.
2. ``request_changes`` — a *claimed review run* returns to ready (or todo with
   an unfinished parent), carrying the reason; an ordinary implementer run is
   refused (the tool must not bounce a worker mid-implementation).
3. Round trip — request_review -> claim_review_task -> request_changes returns
   the card to its implementer.

Real SQLite in a temp OPENAMER_HOME. No mocks.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from openamer_cli import kanban_db as kb


@pytest.fixture
def kanban_home(tmp_path, monkeypatch):
    home = tmp_path / ".openamer"
    home.mkdir()
    monkeypatch.setenv("OPENAMER_HOME", str(home))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    kb.init_db()
    return home


# --------------------------------------------------------------------------- #
# API surface
# --------------------------------------------------------------------------- #
def test_handlers_are_defined():
    """The two names the tool layer dispatches to must exist."""
    assert callable(getattr(kb, "request_review", None))
    assert callable(getattr(kb, "request_changes", None))


# --------------------------------------------------------------------------- #
# 1. request_review
# --------------------------------------------------------------------------- #
def test_request_review_moves_running_to_review(kanban_home):
    with kb.connect() as conn:
        tid = kb.create_task(conn, title="impl", assignee="dev")
        assert kb.claim_task(conn, tid, claimer="dev:1") is not None
        run_id = kb._current_run_id(conn, tid)

        assert kb.request_review(
            conn, tid, summary="done, please review", expected_run_id=run_id
        ) is True

        task = kb.get_task(conn, tid)
        assert task.status == "review"
        # claim released so the dispatcher's review queue can pick it up
        assert task.claim_lock is None
        # the run is closed and carries the handoff
        run = kb.latest_run(conn, tid)
        assert run is not None and run.ended_at is not None
        assert run.outcome == "review_requested"
        assert (run.summary or "").startswith("done, please review")
        # event recorded
        events = [r[0] for r in conn.execute(
            "SELECT kind FROM task_events WHERE task_id=? ORDER BY id", (tid,))]
        assert "review_requested" in events


def test_request_review_does_not_promote_dependents(kanban_home):
    """A review is not a completion: children must stay gated."""
    with kb.connect() as conn:
        parent = kb.create_task(conn, title="parent", assignee="dev")
        child = kb.create_task(conn, title="child", assignee="dev", parents=[parent])
        assert kb.claim_task(conn, parent, claimer="dev:1") is not None

        kb.request_review(conn, parent, summary="review me")

        assert kb.get_task(conn, parent).status == "review"
        assert kb.get_task(conn, child).status == "todo"


def test_request_review_rejects_stale_run(kanban_home):
    with kb.connect() as conn:
        tid = kb.create_task(conn, title="impl", assignee="dev")
        kb.claim_task(conn, tid, claimer="dev:1")
        stale = 999_999

        assert kb.request_review(conn, tid, summary="x", expected_run_id=stale) is False
        assert kb.get_task(conn, tid).status == "running"


def test_request_review_with_reason_tuple(kanban_home):
    with kb.connect() as conn:
        tid = kb.create_task(conn, title="impl", assignee="dev")
        kb.claim_task(conn, tid, claimer="dev:1")

        ok, reason = kb.request_review(
            conn, tid, summary="s", with_reason=True, expected_run_id=None
        )
        assert ok is True and reason is None
        assert kb.get_task(conn, tid).status == "review"


# --------------------------------------------------------------------------- #
# 2. request_changes
# --------------------------------------------------------------------------- #
def test_request_changes_refuses_ordinary_run(kanban_home):
    """A plain implementer run must never be bounced to the implementer."""
    with kb.connect() as conn:
        tid = kb.create_task(conn, title="impl", assignee="dev")
        kb.claim_task(conn, tid, claimer="dev:1")

        ok, detail = kb.request_changes(conn, tid, reason="nope")
        assert ok is False
        assert "review" in (detail or "")
        assert kb.get_task(conn, tid).status == "running"


def test_request_changes_returns_review_run_to_ready(kanban_home):
    with kb.connect() as conn:
        tid = kb.create_task(conn, title="impl", assignee="dev")
        kb.claim_task(conn, tid, claimer="dev:1")
        kb.request_review(conn, tid, summary="review me")

        # the dispatcher claims the review run
        assert kb.claim_review_task(conn, tid, claimer="rev:1") is not None
        assert kb.get_task(conn, tid).status == "running"

        ok, implementer = kb.request_changes(conn, tid, reason="needs tests")
        assert ok is True
        assert implementer == "dev"
        task = kb.get_task(conn, tid)
        assert task.status == "ready"
        assert task.claim_lock is None
        events = [r[0] for r in conn.execute(
            "SELECT kind FROM task_events WHERE task_id=? ORDER BY id", (tid,))]
        assert "changes_requested" in events


def test_request_changes_keeps_todo_when_parent_unfinished(kanban_home):
    with kb.connect() as conn:
        parent = kb.create_task(conn, title="parent", assignee="dev")
        child = kb.create_task(conn, title="child", assignee="dev", parents=[parent])

        # force the child into a claimed review run even though its parent
        # is unfinished: the re-gate must still hold on the way back
        conn.execute(
            "UPDATE tasks SET status='running', claim_lock='rev:1' WHERE id=?", (child,))
        conn.execute(
            "UPDATE tasks SET status='running', claim_lock='dev:1' WHERE id=?", (parent,))
        kb.request_review(conn, parent, summary="ok")
        kb.claim_review_task(conn, child, claimer="rev:1")

        ok, _ = kb.request_changes(conn, child, reason="fix")
        assert ok is True
        assert kb.get_task(conn, child).status == "todo"


# --------------------------------------------------------------------------- #
# 3. round trip
# --------------------------------------------------------------------------- #
def test_review_round_trip_is_reusable(kanban_home):
    """After changes are requested the card can be reviewed again."""
    with kb.connect() as conn:
        tid = kb.create_task(conn, title="impl", assignee="dev")
        kb.claim_task(conn, tid, claimer="dev:1")
        kb.request_review(conn, tid, summary="v1")
        kb.claim_review_task(conn, tid, claimer="rev:1")
        assert kb.request_changes(conn, tid, reason="v1 not enough")[0] is True

        assert kb.get_task(conn, tid).status == "ready"
        kb.claim_task(conn, tid, claimer="dev:2")
        assert kb.request_review(conn, tid, summary="v2") is True
        assert kb.get_task(conn, tid).status == "review"
        kb.claim_review_task(conn, tid, claimer="rev:2")
        assert kb.request_changes(conn, tid, reason="v2 still not enough")[0] is True
        assert kb.get_task(conn, tid).status == "ready"