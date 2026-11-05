"""End-to-end test: the repeat-tool reminder must reach the model.

The reminder is injected into the tool result the model sees. This test
drives the real dispatch helper with a real agent-shaped object and
asserts the notice is present in the content the model would read.
"""
from __future__ import annotations

import json

from agent.repeat_tool_reminder import (
    RepeatToolReminderConfig,
    RepeatToolReminderController,
)
from agent.tool_dispatch_helpers import (
    append_repeat_tool_reminder,
    make_tool_result_message,
)


class _FakeAgent:
    def __init__(self):
        self._repeat_tool_reminder = RepeatToolReminderController()


def test_reminder_reaches_the_tool_result_content():
    agent = _FakeAgent()
    args = {"path": "x.txt"}
    content = json.dumps({"ok": True})
    for _ in range(3):
        content = append_repeat_tool_reminder(agent, "read_file", args, content)
    message = make_tool_result_message("read_file", content, "call_1")
    assert "Repeat-tool reminder" in message["content"]
    # The original payload must survive alongside the notice.
    assert '"ok": true' in message["content"].lower()


def test_result_is_unchanged_without_repeats():
    agent = _FakeAgent()
    content = json.dumps({"ok": True})
    out = append_repeat_tool_reminder(agent, "read_file", {"path": "x"}, content)
    assert out == content


def test_reminder_names_the_repeated_tool():
    agent = _FakeAgent()
    args = {"path": "x.txt"}
    content = "result"
    for _ in range(3):
        content = append_repeat_tool_reminder(agent, "search_files", args, content)
    assert "search_files" in content


def test_excluded_tool_never_gets_a_reminder():
    agent = _FakeAgent()
    content = "result"
    for _ in range(10):
        content = append_repeat_tool_reminder(agent, "todo_write", {"a": 1}, content)
    assert content == "result"


def test_disabled_reminder_never_fires():
    agent = _FakeAgent()
    agent._repeat_tool_reminder = RepeatToolReminderController(
        RepeatToolReminderConfig(enabled=False)
    )
    content = "result"
    for _ in range(10):
        content = append_repeat_tool_reminder(agent, "read_file", {"a": 1}, content)
    assert content == "result"
