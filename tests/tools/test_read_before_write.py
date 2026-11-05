"""Tests for the read-before-write policy.

Adapted from deepseek-ai/deepseek-harness ``fs-observation-policy``. The
policy is off by default; when enabled it refuses a mutation of an
existing file the agent has not read.

The tests assert *behaviour contracts* (a refusal happens / does not
happen under a given observation state), not the exact message text.
"""
from __future__ import annotations

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


def _enable(**kwargs):
    read_before_write.configure(
        read_before_write.ReadBeforeWriteConfig(enabled=True, **kwargs)
    )


def test_disabled_by_default_allows_write(tmp_path):
    target = tmp_path / "a.txt"
    target.write_text("x", encoding="utf-8")
    assert read_before_write.check("t1", str(target)) is None


def test_enabled_refuses_unread_existing_file(tmp_path):
    target = tmp_path / "a.txt"
    target.write_text("x", encoding="utf-8")
    _enable()
    err = read_before_write.check("t1", str(target))
    assert err is not None
    assert "not read" in err


def test_enabled_allows_read_file(tmp_path):
    target = tmp_path / "a.txt"
    target.write_text("x", encoding="utf-8")
    file_state.record_read("t1", str(target))
    _enable()
    assert read_before_write.check("t1", str(target)) is None


def test_enabled_allows_creating_new_file(tmp_path):
    target = tmp_path / "new.txt"
    _enable(allow_create=True)
    assert read_before_write.check("t1", str(target)) is None


def test_allow_create_false_refuses_new_file(tmp_path):
    target = tmp_path / "new.txt"
    _enable(allow_create=False)
    err = read_before_write.check("t1", str(target))
    assert err is not None


def test_other_agent_read_does_not_authorize(tmp_path):
    """A sibling agent's read must not authorize THIS agent's write."""
    target = tmp_path / "a.txt"
    target.write_text("x", encoding="utf-8")
    file_state.record_read("other-agent", str(target))
    _enable()
    err = read_before_write.check("t1", str(target))
    assert err is not None


def test_file_changed_after_read_is_refused(tmp_path):
    target = tmp_path / "a.txt"
    target.write_text("x", encoding="utf-8")
    file_state.record_read("t1", str(target))
    _enable()
    # External modification after the read.
    os.utime(str(target), (0, 0))
    err = read_before_write.check("t1", str(target))
    assert err is not None
    assert "changed" in err


def test_from_mapping_defaults():
    cfg = read_before_write.ReadBeforeWriteConfig.from_mapping(None)
    assert cfg.enabled is False
    assert cfg.allow_create is True
    assert cfg.enforce_existing is True


def test_from_mapping_reads_values():
    cfg = read_before_write.ReadBeforeWriteConfig.from_mapping(
        {"enabled": True, "allow_create": False}
    )
    assert cfg.enabled is True
    assert cfg.allow_create is False


def test_env_kill_switch(tmp_path, monkeypatch):
    target = tmp_path / "a.txt"
    target.write_text("x", encoding="utf-8")
    _enable()
    monkeypatch.setenv("OPENAMER_DISABLE_READ_BEFORE_WRITE", "1")
    assert read_before_write.check("t1", str(target)) is None
