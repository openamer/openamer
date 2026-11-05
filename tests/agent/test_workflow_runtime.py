"""Tests for the workflow runtime and the workflow tool.

Adapted from deepseek-ai/deepseek-harness ``packages/workflow``.

The runtime executes a model-written script that fans work out to
subagents. The tests assert behaviour contracts: a script that awaits
agents gets their answers, parallel preserves order, a forbidden
construct is rejected, and a failing script reports an error instead of
a partial success.
"""
from __future__ import annotations

import asyncio
import json

import pytest

from agent.workflow_runtime import (
    WorkflowError,
    WorkflowResult,
    WorkflowRunner,
    _validate_script,
)


def _runner(answers=None, max_parallel=3):
    calls = []

    def fake_agent(prompt, context=None, **kwargs):
        calls.append({"prompt": prompt, "context": context})
        if answers is not None:
            return answers.get(prompt, f"ANSWER<{prompt}>")
        return f"ANSWER<{prompt}>"

    runner = WorkflowRunner(agent_hook=fake_agent, max_parallel=max_parallel)
    return runner, calls


def _run(script, **kwargs):
    runner, calls = _runner(**kwargs)
    result = asyncio.run(runner.run(script))
    return result, calls


# ── script basics ──────────────────────────────────────────────────────


def test_script_returning_value():
    result, _ = _run('return {"x": 1}')
    assert result.value == {"x": 1}


def test_top_level_await():
    result, calls = _run('a = await agent("find A")\nreturn a')
    assert result.value == "ANSWER<find A>"
    assert len(calls) == 1


def test_agents_started_is_counted():
    result, _ = _run('a = await agent("x")\nb = await agent("y")\nreturn [a, b]')
    assert result.agents_started == 2


def test_context_is_passed_through():
    result, calls = _run('return await agent("p", "the context")')
    assert calls[0]["context"] == "the context"


def test_args_are_exposed():
    runner, _calls = _runner()
    out = asyncio.run(runner.run('return {"n": args["n"] * 2}', {"n": 21}))
    assert out.value == {"n": 42}


def test_phase_and_log_are_recorded():
    result, _ = _run('phase("research")\nlog("hello")\nreturn 1')
    assert result.phases == ["research"]
    assert result.logs == ["hello"]


# ── parallel / pipeline ────────────────────────────────────────────────


def test_parallel_with_coroutines_preserves_order():
    result, _ = _run(
        'return await parallel([agent("one"), agent("two"), agent("three")])'
    )
    assert result.value == ["ANSWER<one>", "ANSWER<two>", "ANSWER<three>"]
    assert result.agents_started == 3


def test_parallel_with_empty_list():
    result, _ = _run("return await parallel([])")
    assert result.value == []


def test_pipeline_maps_over_items():
    result, _ = _run(
        'return await pipeline(["a", "b"], lambda item: item.upper())'
    )
    assert result.value == ["A", "B"]


def test_pipeline_step_sees_previous_result():
    result, _ = _run(
        'return await pipeline(["a", "b"], lambda item, prev: f"{item}|{prev}")'
    )
    assert result.value == ["a|None", "b|a|None"]


# ── safety ─────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "script",
    [
        "return eval('1+1')",
        "return exec('x=1')",
        "import os\nreturn 1",
        "from os import path\nreturn 1",
        "return open('/etc/passwd').read()",
    ],
)
def test_forbidden_constructs_are_rejected(script):
    with pytest.raises(WorkflowError):
        _validate_script(script)


def test_empty_script_is_rejected():
    with pytest.raises(WorkflowError):
        _validate_script("   ")


def test_syntax_error_is_reported():
    with pytest.raises(WorkflowError):
        _validate_script("return (")


def test_failing_script_raises_rather_than_returning_partial():
    runner, _ = _runner()
    with pytest.raises(ValueError):
        asyncio.run(runner.run('raise ValueError("boom")'))


# ── the model-facing tool ──────────────────────────────────────────────


def test_workflow_tool_rejects_missing_meta():
    from tools.workflow_tool import workflow_tool

    out = workflow_tool(meta=None, script="return 1", parent_agent=object())
    payload = json.loads(out)
    assert payload.get("error")


def test_workflow_tool_rejects_empty_script():
    from tools.workflow_tool import workflow_tool

    out = workflow_tool(
        meta={"name": "x", "description": "y"}, script="", parent_agent=object()
    )
    payload = json.loads(out)
    assert payload.get("error")


def test_workflow_tool_requires_parent_agent():
    from tools.workflow_tool import workflow_tool

    out = workflow_tool(meta={"name": "x", "description": "y"}, script="return 1")
    payload = json.loads(out)
    assert payload.get("error")


def test_workflow_tool_is_registered():
    from tools.registry import registry
    import tools.workflow_tool  # noqa: F401

    assert registry.get_entry("workflow") is not None
    assert registry.get_toolset_for_tool("workflow") == "delegation"


def test_workflow_schema_is_wellformed():
    from tools.workflow_tool import WORKFLOW_SCHEMA

    assert WORKFLOW_SCHEMA["name"] == "workflow"
    params = WORKFLOW_SCHEMA["parameters"]
    assert params["type"] == "object"
    assert "meta" in params["properties"]
    assert "script" in params["properties"]
    assert set(params["required"]) == {"meta", "script"}


def test_workflow_result_to_dict():
    result = WorkflowResult(value=1, agents_started=2, phases=["p"], logs=["l"])
    data = result.to_dict()
    assert data["result"] == 1
    assert data["agents_started"] == 2
    assert data["phases"] == ["p"]
    assert data["logs"] == ["l"]
