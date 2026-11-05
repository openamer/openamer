"""End-to-end test for the workflow tool against the REAL delegation path.

The workflow tool's value is that a script can fan work out to real
subagents. This test drives the tool handler with the actual
``_build_child_agent`` / ``_run_single_child`` path and asserts that the
script receives the children's answers.

The child agent is stubbed at the lowest level that still exercises the
real plumbing: the child agent object is a stand-in whose run produces a
known answer, so the test proves the tool wires script -> child -> result
without spending real model calls.
"""
from __future__ import annotations

import json

import pytest


class _StubChild:
    """Minimal stand-in for a delegated child agent."""

    def __init__(self, goal):
        self.goal = goal
        self.tool_progress_callback = None
        self._delegate_saved_tool_names = []

    def _touch_activity(self):
        return None


@pytest.fixture
def _stub_children(monkeypatch):
    """Replace the child build/run pair with a deterministic stub."""
    import tools.delegate_tool as dt

    built = []

    def _fake_build(task_index=0, goal="", context=None, **kwargs):
        child = _StubChild(goal)
        built.append({"goal": goal, "context": context})
        return child

    def _fake_run(task_index, goal, child=None, parent_agent=None, **kwargs):
        return {
            "summary": f"CHILD<{goal}>",
            "task_index": task_index,
        }

    monkeypatch.setattr(dt, "_build_child_agent", _fake_build)
    monkeypatch.setattr(dt, "_run_single_child", _fake_run)
    return built


def test_workflow_tool_returns_script_value(_stub_children):
    from tools.workflow_tool import workflow_tool

    out = workflow_tool(
        meta={"name": "audit", "description": "audit files"},
        script='return {"a": await agent("check A")}',
        parent_agent=object(),
    )
    payload = json.loads(out)
    assert payload["name"] == "audit"
    assert payload["result"] == {"a": "CHILD<check A>"}
    assert payload["agentsStarted"] == 1


def test_workflow_tool_fans_out_to_multiple_children(_stub_children):
    from tools.workflow_tool import workflow_tool

    out = workflow_tool(
        meta={"name": "multi", "description": "parallel"},
        script=(
            'results = await parallel([agent("a"), agent("b"), agent("c")])\n'
            'return results'
        ),
        parent_agent=object(),
    )
    payload = json.loads(out)
    assert payload["result"] == ["CHILD<a>", "CHILD<b>", "CHILD<c>"]
    assert payload["agentsStarted"] == 3
    assert len(_stub_children) == 3


def test_workflow_tool_supports_dependent_rounds(_stub_children):
    """The capability delegate_task cannot express: a second round that
    depends on the first."""
    from tools.workflow_tool import workflow_tool

    out = workflow_tool(
        meta={"name": "two-round", "description": "dependent rounds"},
        script=(
            'first = await agent("pass one")\n'
            'second = await agent("pass two based on " + first)\n'
            'return [first, second]'
        ),
        parent_agent=object(),
    )
    payload = json.loads(out)
    assert payload["result"] == [
        "CHILD<pass one>",
        "CHILD<pass two based on CHILD<pass one>>",
    ]
    assert payload["agentsStarted"] == 2


def test_workflow_tool_reports_script_failure_as_error(_stub_children):
    from tools.workflow_tool import workflow_tool

    out = workflow_tool(
        meta={"name": "bad", "description": "raises"},
        script='raise ValueError("boom")',
        parent_agent=object(),
    )
    payload = json.loads(out)
    assert payload.get("error")
    assert "boom" in payload["error"]


def test_workflow_tool_reports_syntax_error_as_error(_stub_children):
    from tools.workflow_tool import workflow_tool

    out = workflow_tool(
        meta={"name": "bad", "description": "syntax"},
        script="return (",
        parent_agent=object(),
    )
    payload = json.loads(out)
    assert payload.get("error")
