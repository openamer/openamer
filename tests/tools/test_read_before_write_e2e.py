"""End-to-end test for the read-before-write policy through the real
write/patch tool path.

No mocks: the policy must actually REFUSE the mutation when the agent
has not read the file, and must let it through after a real read.
"""
from __future__ import annotations

import json
import os

import pytest

from tools import file_state, read_before_write


@pytest.fixture(autouse=True)
def _clean_policy():
    read_before_write.reset()
    file_state.get_registry().clear()
    yield
    read_before_write.reset()
    file_state.get_registry().clear()


def _enable():
    read_before_write.configure(
        read_before_write.ReadBeforeWriteConfig(enabled=True)
    )


def test_write_file_tool_refuses_unread_file(tmp_path):
    from tools.file_tools import write_file_tool

    target = tmp_path / "secret.txt"
    target.write_text("original", encoding="utf-8")
    _enable()

    raw = write_file_tool(str(target), "overwritten", task_id="t1")
    result = json.loads(raw)

    assert result.get("error"), f"expected refusal, got: {result}"
    # The file on disk must be untouched.
    assert target.read_text(encoding="utf-8") == "original"


def test_write_file_tool_allows_after_read(tmp_path):
    from tools.file_tools import read_file_tool, write_file_tool

    target = tmp_path / "ok.txt"
    target.write_text("original", encoding="utf-8")
    _enable()

    read_file_tool(str(target), task_id="t1")
    raw = write_file_tool(str(target), "updated", task_id="t1")
    result = json.loads(raw)

    assert not result.get("error"), f"unexpected refusal: {result}"
    assert target.read_text(encoding="utf-8") == "updated"


def test_write_file_tool_allows_new_file(tmp_path):
    from tools.file_tools import write_file_tool

    target = tmp_path / "created.txt"
    _enable()

    raw = write_file_tool(str(target), "fresh", task_id="t1")
    result = json.loads(raw)

    assert not result.get("error"), f"unexpected refusal: {result}"
    assert target.read_text(encoding="utf-8") == "fresh"


def test_policy_disabled_keeps_old_behaviour(tmp_path):
    """Default config must not change any existing behaviour."""
    from tools.file_tools import write_file_tool

    target = tmp_path / "legacy.txt"
    target.write_text("original", encoding="utf-8")

    raw = write_file_tool(str(target), "overwritten", task_id="t1")
    result = json.loads(raw)

    assert not result.get("error"), f"unexpected refusal: {result}"
    assert target.read_text(encoding="utf-8") == "overwritten"
