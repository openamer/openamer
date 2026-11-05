"""Tests for the model-facing goal tool.

Adapted from deepseek-ai/deepseek-harness ``packages/goal``, which
exposes the goal to the model through ``get_goal`` / ``create_goal`` /
``update_goal`` tools.

The tool is a thin wrapper over the existing ``GoalManager``: every
existing guarantee (persistence, turn budget, continuation loop) keeps
working. The tests assert the *contract* the model relies on — it can
see the goal, set it, amend it, and report completion.
"""
from __future__ import annotations

import json

import pytest


@pytest.fixture
def agent(tmp_path, monkeypatch, request):
    """A fake agent bound to an isolated session.

    The goal state lives in the session DB, so each test needs its own
    session id — otherwise one test's goal leaks into the next.
    """
    monkeypatch.setenv("OPENAMER_HOME", str(tmp_path / "home"))
    session_id = f"goal-test-{request.node.name}"

    class _Agent:
        _goal_manager = None

    agent = _Agent()
    agent.session_id = session_id
    return agent


def _call(agent, **kwargs):
    from tools.goal_tool import goal_tool

    out = goal_tool(parent_agent=agent, **kwargs)
    return json.loads(out)


def test_works_without_parent_agent_via_session_id(tmp_path, monkeypatch):
    """The registry dispatch passes session_id but NOT parent_agent.

    This is the shape the real agent uses: model_tools dispatches every
    registry tool with ``task_id``/``session_id``/``user_task`` kwargs.
    A tool that binds only on ``parent_agent`` fails in production while
    fake-agent unit tests stay green — this test pins the real shape.
    """
    monkeypatch.setenv("OPENAMER_HOME", str(tmp_path / "home"))

    class _NoAgent:
        pass

    out = _call(_NoAgent(), action="read", session_id="registry-dispatch-session")
    assert out.get("error") is None, out
    assert out.get("goal") is None


def test_missing_session_id_reports_a_clear_error(tmp_path, monkeypatch):
    """No session identity at all -> a clear error, not a crash."""
    monkeypatch.setenv("OPENAMER_HOME", str(tmp_path / "home"))

    class _NoAgent:
        pass

    out = _call(_NoAgent(), action="read")
    assert out.get("error")
    assert "session" in out["error"].lower()


def test_read_without_goal(agent):
    payload = _call(agent, action="read")
    assert payload["goal"] is None
    assert payload["status"] == "none"


def test_set_then_read(agent):
    payload = _call(agent, action="set", goal="Alle Tests gruen machen")
    assert payload["ok"] is True
    assert payload["goal"] == "Alle Tests gruen machen"
    assert payload["status"] == "active"

    read_back = _call(agent, action="read")
    assert read_back["goal"] == "Alle Tests gruen machen"
    assert read_back["turns_used"] == 0


def test_set_requires_a_goal(agent):
    payload = _call(agent, action="set")
    assert payload.get("error")


def test_amend_appends_a_subgoal(agent):
    _call(agent, action="set", goal="Basisziel")
    payload = _call(agent, action="amend", goal="Zusatzkriterium")
    assert payload["subgoals"] == ["Zusatzkriterium"]


def test_report_done(agent):
    _call(agent, action="set", goal="Ziel")
    payload = _call(agent, action="report", status="done", reason="fertig")
    assert payload["ok"] is True


def test_report_blocked_requires_a_reason(agent):
    _call(agent, action="set", goal="Ziel")
    payload = _call(agent, action="report", status="blocked")
    assert payload.get("error")
    assert "reason" in payload["error"]


def test_report_blocked_with_reason(agent):
    _call(agent, action="set", goal="Ziel")
    payload = _call(agent, action="report", status="blocked", reason="warte auf CI")
    assert payload["ok"] is True


def test_report_requires_a_status(agent):
    _call(agent, action="set", goal="Ziel")
    payload = _call(agent, action="report")
    assert payload.get("error")


def test_pause_and_resume(agent):
    _call(agent, action="set", goal="Ziel")
    paused = _call(agent, action="pause", reason="kurz warten")
    assert paused["ok"] is True

    resumed = _call(agent, action="resume")
    assert resumed["ok"] is True
    assert resumed["status"] == "active"


def test_unknown_action_is_rejected(agent):
    payload = _call(agent, action="teleport")
    assert payload.get("error")


def test_requires_a_session_bound_agent():
    from tools.goal_tool import goal_tool

    out = json.loads(goal_tool(action="read", parent_agent=None))
    assert out.get("error")


def test_tool_is_registered():
    from tools.registry import registry
    import tools.goal_tool  # noqa: F401

    assert registry.get_entry("goal") is not None
    assert registry.get_toolset_for_tool("goal") == "goal"


def test_schema_is_wellformed():
    from tools.goal_tool import GOAL_SCHEMA

    assert GOAL_SCHEMA["name"] == "goal"
    params = GOAL_SCHEMA["parameters"]
    assert params["required"] == ["action"]
    actions = params["properties"]["action"]["enum"]
    assert "read" in actions and "set" in actions and "report" in actions
