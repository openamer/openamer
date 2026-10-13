"""Tests for openamer_cli.durable_execution — checkpoint/resume system."""
import json
import pathlib
import tempfile

import pytest

from openamer_cli.durable_execution import (
    Checkpoint,
    save_checkpoint,
    load_latest_checkpoint,
    list_checkpoints,
    clear_checkpoints,
    auto_checkpoint,
    has_checkpoints,
    get_checkpoint_stats,
    resolve_checkpoint_for_resume,
)


@pytest.fixture(autouse=True)
def isolate_home(monkeypatch):
    """Redirect checkpoints to a temp dir."""
    with tempfile.TemporaryDirectory() as tmp:
        p = pathlib.Path(tmp)
        checkpoints_dir = p / "checkpoints"
        checkpoints_dir.mkdir(parents=True)
        monkeypatch.setattr("openamer_cli.durable_execution._CHECKPOINT_DIR", checkpoints_dir)
        yield p


class TestCheckpoint:
    def test_save_and_load(self):
        messages = [{"role": "user", "content": "hello"}]
        num = save_checkpoint("session-1", messages)
        assert num == 1

        cp = load_latest_checkpoint("session-1")
        assert cp is not None
        assert cp.number == 1
        assert cp.session_id == "session-1"
        assert len(cp.messages) == 1

    def test_multiple_checkpoints_increment(self):
        save_checkpoint("session-1", [{"role": "user", "content": "msg1"}])
        save_checkpoint("session-1", [{"role": "user", "content": "msg2"}])
        save_checkpoint("session-1", [{"role": "user", "content": "msg3"}])

        cp = load_latest_checkpoint("session-1")
        assert cp.number == 3
        assert cp.messages[0]["content"] == "msg3"

    def test_no_checkpoint_for_unknown_session(self):
        cp = load_latest_checkpoint("does-not-exist")
        assert cp is None

    def test_has_checkpoints(self):
        assert not has_checkpoints("session-1")
        save_checkpoint("session-1", [{"role": "user", "content": "hi"}])
        assert has_checkpoints("session-1")


class TestListCheckpoints:
    def test_list_checkpoints(self):
        for i in range(3):
            save_checkpoint("session-list", [{"role": "user", "content": f"msg{i}"}])

        cps = list_checkpoints("session-list")
        assert len(cps) == 3
        assert cps[0]["number"] == 1
        assert cps[2]["number"] == 3

    def test_list_empty(self):
        cps = list_checkpoints("no-session")
        assert cps == []


class TestClearCheckpoints:
    def test_clear(self):
        save_checkpoint("session-clear", [{"role": "user", "content": "x"}])
        assert has_checkpoints("session-clear")
        assert clear_checkpoints("session-clear") is True
        assert not has_checkpoints("session-clear")

    def test_clear_nonexistent(self):
        assert clear_checkpoints("ghost") is False


class TestAutoCheckpoint:
    def test_auto_checkpoint_first(self, monkeypatch):
        monkeypatch.setattr("openamer_cli.durable_execution._CHECKPOINT_INTERVAL", 0)
        num = auto_checkpoint("session-auto", [{"role": "user", "content": "hi"}])
        assert num == 1

    def test_auto_checkpoint_too_soon(self, monkeypatch):
        monkeypatch.setattr("openamer_cli.durable_execution._CHECKPOINT_INTERVAL", 9999)
        save_checkpoint("session-auto", [{"role": "user", "content": "first"}])
        num = auto_checkpoint("session-auto", [{"role": "user", "content": "second"}])
        assert num is None


class TestStats:
    def test_get_checkpoint_stats(self):
        save_checkpoint("stat-session", [{"role": "user", "content": "a"}])
        stats = get_checkpoint_stats()
        assert stats["total_sessions"] >= 1
        assert stats["total_checkpoints"] >= 1
        assert stats["total_size_bytes"] > 0


class TestResolveForResume:
    def test_resolve_with_checkpoints(self):
        messages = [{"role": "user", "content": "hello"}, {"role": "assistant", "content": "hi"}]
        save_checkpoint("resume-session", messages)
        result = resolve_checkpoint_for_resume("resume-session")
        assert result is not None
        num, msgs = result
        assert num == 1
        assert len(msgs) == 2

    def test_resolve_none(self):
        result = resolve_checkpoint_for_resume("ghost")
        assert result is None


class TestCheckpointDataclass:
    def test_to_dict_roundtrip(self):
        cp = Checkpoint(
            number=1,
            session_id="test",
            timestamp="2026-01-01T00:00:00",
            messages=[{"role": "user", "content": "test"}],
            tool_states={},
            memory_state={},
            context_summary="test context",
        )
        d = cp.to_dict()
        assert d["number"] == 1
        assert d["session_id"] == "test"

        cp2 = Checkpoint.from_dict(d)
        assert cp2.number == 1
        assert cp2.context_summary == "test context"


class TestCLI:
    def test_cmd_checkpoint_imports(self):
        from openamer_cli.durable_execution import (
            cmd_checkpoint,
            build_checkpoint_parser,
        )
        assert callable(cmd_checkpoint)
        assert callable(build_checkpoint_parser)

    def test_build_checkpoint_parser(self):
        import argparse
        parser = argparse.ArgumentParser()
        sub = parser.add_subparsers()
        # Import directly inside test to avoid monkeypatch interference
        import openamer_cli.durable_execution as de
        de.build_checkpoint_parser(sub)
        assert "checkpoint" in sub.choices