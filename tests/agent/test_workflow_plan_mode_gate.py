"""The workflow tool must be gated by plan mode.

A workflow script fans out to subagents, and a subagent can write files
on our behalf — exactly like ``delegate_task``. If ``workflow`` were not
in the mutating set, plan mode would be bypassable through it.
"""
from __future__ import annotations

import pytest

from agent.plan_mode import MUTATING_TOOLS, is_mutating


def test_workflow_is_a_mutating_tool():
    assert "workflow" in MUTATING_TOOLS


@pytest.mark.parametrize("tool_name", ["delegate_task", "workflow"])
def test_delegation_tools_are_mutating(tool_name):
    assert is_mutating(tool_name)


def test_read_only_tools_stay_read_only():
    assert not is_mutating("read_file")
    assert not is_mutating("web_search")
