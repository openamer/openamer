"""Tests for openamer_cli.observability — tracing & execution browser."""
import json
import pathlib
import tempfile

import pytest

from openamer_cli.observability import (
    TraceEvent,
    AgentTrace,
    build_trace_from_events,
    get_trace_stats,
    build_trace_parser,
)


@pytest.fixture(autouse=True)
def isolate_home(monkeypatch):
    """Redirect brainlog dir to a temp location."""
    with tempfile.TemporaryDirectory() as tmp:
        p = pathlib.Path(tmp)
        a2a_dir = p / "a2a"
        a2a_dir.mkdir(parents=True)
        monkeypatch.setattr("openamer_cli.observability._BRAINLOG_DIR", a2a_dir)
        monkeypatch.setattr("openamer_cli.observability._HOME", p)
        yield p


@pytest.fixture
def sample_brainlog(isolate_home):
    """Create a sample brainlog JSONL file."""
    brainlog = isolate_home / "a2a" / "session-123.jsonl"
    events = [
        {"kind": "user_message", "timestamp": "2026-01-01T10:00:00", "content": "Hello"},
        {"kind": "tool_call", "timestamp": "2026-01-01T10:00:01", "tool_name": "web_search", "tool_args": {"query": "test"}, "duration_ms": 1500},
        {"kind": "tool_result", "timestamp": "2026-01-01T10:00:03", "content": "Search results", "duration_ms": 2000, "success": True},
        {"kind": "assistant_message", "timestamp": "2026-01-01T10:00:04", "content": "Here are the results"},
    ]
    brainlog.write_text("\n".join(json.dumps(e) for e in events), encoding="utf-8")
    return brainlog


class TestTraceEvent:
    def test_default_creation(self):
        ev = TraceEvent(timestamp="2026-01-01", event_type="tool_call", tool_name="web_search")
        assert ev.event_type == "tool_call"
        assert ev.tool_name == "web_search"
        assert ev.success is True


class TestBuildTrace:
    def test_build_from_events(self, sample_brainlog):
        import json
        events = [json.loads(l) for l in sample_brainlog.read_text(encoding="utf-8").splitlines() if l.strip()]
        trace = build_trace_from_events(events, session_id="session-123")
        assert trace.session_id == "session-123"
        assert trace.event_count == 4
        assert trace.tool_calls == 2  # tool_call + tool_result

    def test_empty_events(self):
        trace = build_trace_from_events([], session_id="empty")
        assert trace.event_count == 0
        assert trace.tool_calls == 0

    def test_max_events_limit(self, sample_brainlog):
        import json
        events = [json.loads(l) for l in sample_brainlog.read_text(encoding="utf-8").splitlines() if l.strip()]
        trace = build_trace_from_events(events, max_events=2)
        assert trace.event_count == 2


class TestGetTraceStats:
    def test_no_files(self, isolate_home):
        stats = get_trace_stats()
        assert stats["total_events"] == 0
        assert stats["total_tool_calls"] == 0

    def test_with_brainlog(self, sample_brainlog):
        stats = get_trace_stats()
        assert stats["total_events"] >= 4
        assert stats["total_tool_calls"] >= 2
        assert "web_search" in stats["top_tools"]

    def test_trace_files_count(self, sample_brainlog):
        stats = get_trace_stats()
        assert stats["trace_files"] >= 1


class TestCLI:
    def test_build_trace_parser(self):
        import argparse
        parser = argparse.ArgumentParser()
        sub = parser.add_subparsers()
        build_trace_parser(sub)
        assert "trace" in sub.choices

    def test_cmd_functions_importable(self):
        from openamer_cli.observability import (
            cmd_trace_list, cmd_trace_show, cmd_trace_stats, cmd_trace_watch,
        )
        assert callable(cmd_trace_list)
        assert callable(cmd_trace_show)
        assert callable(cmd_trace_stats)
        assert callable(cmd_trace_watch)