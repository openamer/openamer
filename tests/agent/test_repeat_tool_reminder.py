"""Tests for the advisory repeat-tool reminder.

Adapted from deepseek-ai/deepseek-harness ``repeat-tool-reminder``.
The reminder counts identical tool calls regardless of outcome, so a
successful polling loop is caught too — that is the gap against
``agent/tool_guardrails.py``, which only counts failures.

The reminder must stay advisory: it never blocks and never alters the
tool result itself.
"""
from __future__ import annotations

import pytest

from agent.repeat_tool_reminder import (
    RepeatToolReminderConfig,
    RepeatToolReminderController,
)
from agent.tool_dispatch_helpers import append_repeat_tool_reminder


class _FakeAgent:
    def __init__(self, controller):
        self._repeat_tool_reminder = controller


def test_no_reminder_before_threshold():
    c = RepeatToolReminderController()
    args = {"path": "a.txt"}
    assert c.record_call("read_file", args) is None
    assert c.record_call("read_file", args) is None
    reminder = c.record_call("read_file", args)
    assert reminder is not None
    assert reminder.count == 3


def test_successful_repeats_are_counted():
    """The gap vs. tool_guardrails: success must count too."""
    c = RepeatToolReminderController()
    args = {"path": "a.txt"}
    for _ in range(2):
        c.record_call("read_file", args)
    assert c.record_call("read_file", args) is not None


def test_different_arguments_do_not_count():
    c = RepeatToolReminderController()
    for i in range(5):
        assert c.record_call("read_file", {"path": f"f{i}.txt"}) is None


def test_argument_order_does_not_matter():
    c = RepeatToolReminderController()
    c.record_call("read_file", {"a": 1, "b": 2})
    c.record_call("read_file", {"b": 2, "a": 1})
    assert c.record_call("read_file", {"a": 1, "b": 2}) is not None


def test_different_tools_are_independent():
    c = RepeatToolReminderController()
    for _ in range(4):
        c.record_call("read_file", {"path": "a.txt"})
    assert c.record_call("search_files", {"path": "a.txt"}) is None


def test_excluded_tool_is_not_tracked():
    c = RepeatToolReminderController()
    for _ in range(10):
        assert c.record_call("todo_write", {"a": 1}) is None


def test_include_filter_restricts_tracking():
    c = RepeatToolReminderController(
        RepeatToolReminderConfig(include=frozenset({"read_file"}))
    )
    for _ in range(10):
        assert c.record_call("terminal", {"cmd": "ls"}) is None
    c.record_call("read_file", {"p": 1})
    c.record_call("read_file", {"p": 1})
    assert c.record_call("read_file", {"p": 1}) is not None


def test_detailed_reminder_names_the_arguments():
    c = RepeatToolReminderController()
    args = {"path": "important.txt"}
    reminder = None
    for _ in range(5):
        reminder = c.record_call("read_file", args)
    assert reminder is not None
    assert reminder.detailed is True
    assert "important.txt" in reminder.message


def test_reset_clears_counts():
    c = RepeatToolReminderController()
    args = {"path": "a.txt"}
    c.record_call("read_file", args)
    c.record_call("read_file", args)
    c.reset_for_turn()
    assert c.record_call("read_file", args) is None


def test_disabled_controller_never_fires():
    c = RepeatToolReminderController(RepeatToolReminderConfig(enabled=False))
    for _ in range(10):
        assert c.record_call("read_file", {"p": 1}) is None


def test_from_mapping_ignores_invalid_thresholds():
    cfg = RepeatToolReminderConfig.from_mapping({"thresholds": [1, "x", 3]})
    # Values below 2 and non-ints are dropped; 3 survives.
    assert cfg.thresholds == (3,)


def test_from_mapping_empty_thresholds_falls_back_to_default():
    cfg = RepeatToolReminderConfig.from_mapping({"thresholds": []})
    assert cfg.thresholds == (3, 5, 8)


def test_append_helper_leaves_content_unchanged_below_threshold():
    c = RepeatToolReminderController()
    agent = _FakeAgent(c)
    out = append_repeat_tool_reminder(agent, "read_file", {"p": 1}, "content")
    assert out == "content"


def test_append_helper_adds_notice_at_threshold():
    c = RepeatToolReminderController()
    agent = _FakeAgent(c)
    args = {"p": 1}
    out = "content"
    for _ in range(3):
        out = append_repeat_tool_reminder(agent, "read_file", args, out)
    assert "Repeat-tool reminder" in out
    assert "content" in out


def test_append_helper_without_controller_is_noop():
    class Bare:
        pass

    assert append_repeat_tool_reminder(Bare(), "read_file", {}, "x") == "x"


def test_append_helper_handles_multimodal_content():
    c = RepeatToolReminderController()
    agent = _FakeAgent(c)
    args = {"p": 1}
    content = [{"type": "text", "text": "hi"}]
    for _ in range(3):
        content = append_repeat_tool_reminder(agent, "read_file", args, content)
    assert content[0]["text"] == "hi"
    assert any("Repeat-tool reminder" in part.get("text", "") for part in content)
