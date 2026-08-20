"""Tests for openamer_cli.observability_ui — Web Observability Portal."""
import json
import pathlib
import tempfile

import pytest

from openamer_cli.observability_ui import _ObserveHandler, cmd_observe, build_observe_parser, _trace_to_dict
from openamer_cli.observability import (
    TraceEvent,
    AgentTrace,
    build_trace_from_events,
    get_trace_stats,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


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
    brainlog = isolate_home / "a2a" / "session-test123.jsonl"
    events = [
        {"kind": "user_message", "timestamp": "2026-01-01T10:00:00", "content": "Hello"},
        {"kind": "tool_call", "timestamp": "2026-01-01T10:00:01", "tool_name": "web_search",
         "tool_args": {"query": "test"}, "duration_ms": 1500},
        {"kind": "tool_result", "timestamp": "2026-01-01T10:00:03", "content": "Search results",
         "duration_ms": 2000, "success": True},
        {"kind": "assistant_message", "timestamp": "2026-01-01T10:00:04",
         "content": "Here are the results"},
    ]
    brainlog.write_text("\n".join(json.dumps(e) for e in events), encoding="utf-8")
    return brainlog


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestObserveCLI:
    def test_build_observe_parser(self):
        import argparse
        parser = argparse.ArgumentParser()
        sub = parser.add_subparsers()
        build_observe_parser(sub)
        assert "observe" in sub.choices

    def test_cmd_observe_importable(self):
        assert callable(cmd_observe)


class TestTraceToDict:
    def test_converts_full_trace(self):
        trace = AgentTrace(
            session_id="sess-1",
            title="Test Session",
            started_at="2026-01-01T10:00:00",
            total_duration_ms=5000.0,
            event_count=3,
            tool_calls=2,
            events=[
                TraceEvent(timestamp="2026-01-01T10:00:00", event_type="user_message", content="hi"),
                TraceEvent(timestamp="2026-01-01T10:00:01", event_type="tool_call",
                           tool_name="search", tool_args={"q": "x"}, duration_ms=1000),
            ],
        )
        d = _trace_to_dict(trace)
        assert d["session_id"] == "sess-1"
        assert d["event_count"] == 3
        assert d["tool_calls"] == 2
        assert len(d["events"]) == 2
        assert d["events"][1]["tool_name"] == "search"

    def test_empty_trace(self):
        trace = AgentTrace(session_id="empty")
        d = _trace_to_dict(trace)
        assert d["session_id"] == "empty"
        assert d["events"] == []


class TestObserveAPIResponses:
    """Test the HTTP handler logic without starting a server."""

    def test_handler_imports(self):
        assert _ObserveHandler is not None

    def test_stats_api_returns_dict(self, sample_brainlog):
        """Verify get_trace_stats returns a dict (used by the handler)."""
        stats = get_trace_stats()
        assert isinstance(stats, dict)
        assert "total_events" in stats
        assert "total_tool_calls" in stats

    def test_traces_from_brainlog(self, sample_brainlog):
        """Verify traces can be loaded from brainlog files."""
        from openamer_cli.observability import _brainlog_files, _read_brainlog
        files = list(_brainlog_files())
        assert len(files) >= 1
        events = _read_brainlog(files[0], max_lines=100)
        trace = build_trace_from_events(events, session_id=files[0].stem)
        assert trace.event_count >= 4
        assert trace.tool_calls >= 2

    def test_trace_to_json_serializable(self, sample_brainlog):
        """Verify the trace dict can be serialized to JSON (for the HTTP response)."""
        from openamer_cli.observability import get_recent_traces
        traces = get_recent_traces(limit=5)
        for t in traces:
            d = _trace_to_dict(t)
            json_str = json.dumps(d)
            assert isinstance(json_str, str)
            # Round-trip
            loaded = json.loads(json_str)
            assert loaded["session_id"] == t.session_id


class TestObserveIntegration:
    """Integration tests for the observability UI backend."""

    def test_stats_via_api_path(self, sample_brainlog):
        """Simulate the /api/observe/stats path."""
        from openamer_cli.observability import get_recent_traces
        stats = get_trace_stats()
        assert stats["total_events"] >= 4
        assert stats["total_tool_calls"] >= 2
        assert "web_search" in stats["top_tools"]

    def test_single_trace_via_api_path(self, sample_brainlog):
        """Simulate the /api/observe/trace/<id> path."""
        from openamer_cli.observability import get_recent_traces
        traces = get_recent_traces(limit=5)
        assert len(traces) >= 1
        first = traces[0]
        assert first.session_id  # non-empty
        assert first.event_count >= 4
        assert first.tool_calls >= 2

    def test_export_trace_as_json(self, sample_brainlog):
        """Verify a trace can be exported as JSON."""
        from openamer_cli.observability import get_recent_traces
        traces = get_recent_traces(limit=5)
        for t in traces:
            d = _trace_to_dict(t)
            exported = {
                "trace": d,
                "exported_at": "2026-01-01T12:00:00Z",
            }
            json_str = json.dumps(exported, indent=2)
            assert '"session_id"' in json_str
            assert '"events"' in json_str