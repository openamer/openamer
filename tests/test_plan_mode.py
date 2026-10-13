"""Tests for enforced plan mode (agent/plan_mode.py).

Plan mode is a *gate*, not a prompt request — the value is that a mutating tool
is refused before it runs. These tests pin the two halves of that claim: the
decision function, and the fact that the executor actually consults it.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from agent.plan_mode import (
    MUTATING_TOOLS,
    READ_ONLY_SAFE_TOOLS,
    PlanModeGate,
    is_mutating,
)

_EXECUTOR_SOURCE = Path(__file__).resolve().parents[1] / "agent" / "tool_executor.py"


def test_disabled_gate_allows_everything():
    gate = PlanModeGate(enabled=False)
    for name in ("write_file", "patch", "terminal", "read_file", "totally_new_tool"):
        allowed, reason = gate.check(name)
        assert allowed, name
        assert reason == ""


@pytest.mark.parametrize("tool", sorted(MUTATING_TOOLS))
def test_enabled_gate_refuses_every_mutating_tool(tool):
    allowed, reason = PlanModeGate(enabled=True).check(tool)
    assert not allowed, f"{tool} must be refused in plan mode"
    assert tool in reason


@pytest.mark.parametrize("tool", sorted(READ_ONLY_SAFE_TOOLS))
def test_enabled_gate_allows_every_read_only_tool(tool):
    allowed, reason = PlanModeGate(enabled=True).check(tool)
    assert allowed, f"{tool} must stay usable in plan mode ({reason})"


def test_unknown_tool_fails_closed():
    """A tool added after these lists were written must not open a write path."""
    assert is_mutating("some_brand_new_mutator")
    allowed, _ = PlanModeGate(enabled=True).check("some_brand_new_mutator")
    assert not allowed


def test_empty_tool_name_is_treated_as_mutating():
    assert is_mutating("")
    assert is_mutating("   ")


def test_the_two_sets_are_disjoint():
    overlap = MUTATING_TOOLS & READ_ONLY_SAFE_TOOLS
    assert not overlap, f"a tool cannot be both: {overlap}"


def test_refusal_message_is_actionable():
    """A refusal the model cannot act on just burns a turn."""
    message = PlanModeGate.refusal_message("write_file")
    lowered = message.lower()
    assert "write_file" in message
    assert "plan mode is active" in lowered
    assert "ask the user" in lowered
    # It must tell the model to stop retrying, or it will loop on the same call.
    assert "do not retry" in lowered


def test_status_reports_both_sides():
    status = PlanModeGate(enabled=True).status()
    assert status["enabled"] is True
    assert "write_file" in status["refused_tools"]
    assert "read_file" in status["allowed_tools_explicit"]


def test_executor_actually_consults_the_gate():
    """Structural drift guard: the gate is worthless if nothing calls it.

    Read the source rather than importing the executor — that module drags in
    the whole agent core, which the canonical per-file-isolated runner does not
    guarantee (same reason as the OpenRouter attribution test).
    """
    source = _EXECUTOR_SOURCE.read_text(encoding="utf-8")
    assert "_plan_mode" in source, "tool_executor must consult agent._plan_mode"
    assert "plan_mode_block" in source, "a plan-mode refusal must be reported as such"
    assert ".check(function_name)" in source
    # There are two execution paths (concurrent + sequential); segmented
    # delegates to concurrent. Patching only one leaks plan mode whenever the
    # agent takes the other path — so require both.
    assert source.count("_plan_gate = getattr(agent, \"_plan_mode\", None)") == 2, (
        "plan mode must be checked on BOTH the concurrent and sequential paths"
    )


def test_agent_init_builds_the_gate_from_config():
    """The gate must exist on every agent, defaulting to off."""
    source = (Path(__file__).resolve().parents[1] / "agent" / "agent_init.py").read_text(
        encoding="utf-8"
    )
    assert "PlanModeGate(enabled=" in source
    assert 'cfg_get("agent.plan_mode", False)' in source