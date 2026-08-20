"""Observability & Tracing — Agent Execution Browser.

Provides a step-by-step view of what the agent did, which tools it called,
what results it got, and how long each step took. Reads from the existing
brainlog, session DB, and agent.log files.

CLI:
    openamer trace list              — list recent agent traces
    openamer trace show <session>    — show full trace with timeline
    openamer trace stats             — aggregate statistics
    openamer trace watch             — live tail of agent activity
"""

from __future__ import annotations

import json
import logging
import os
import time
from collections import Counter
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_HOME = Path(os.environ.get("OPENAMER_HOME", Path.home() / ".openamer"))
_BRAINLOG_DIR = _HOME / "a2a"
_SESSION_DB = _HOME / "state.db"
_AGENT_LOG = _HOME / "agent.log"


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class TraceEvent:
    """A single event in an agent trace."""

    timestamp: str
    event_type: str  # user_message, assistant_message, tool_call, tool_result, thinking, error
    content: str = ""
    tool_name: str = ""
    tool_args: Dict[str, Any] = field(default_factory=dict)
    duration_ms: float = 0.0
    success: bool = True


@dataclass
class AgentTrace:
    """A complete trace of one agent session or turn."""

    session_id: str
    title: str = ""
    started_at: str = ""
    total_duration_ms: float = 0.0
    event_count: int = 0
    tool_calls: int = 0
    events: List[TraceEvent] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Trace loading from brainlog
# ---------------------------------------------------------------------------


def _brainlog_files() -> List[Path]:
    """Find all brainlog JSONL files."""
    if not _BRAINLOG_DIR.exists():
        return []
    return sorted(_BRAINLOG_DIR.glob("*.jsonl"))


def _read_brainlog(file: Path, max_lines: int = 5000) -> List[dict]:
    """Read events from a brainlog JSONL file."""
    if not file.exists():
        return []
    events = []
    try:
        with open(file, "r", encoding="utf-8") as f:
            for i, line in enumerate(f):
                if i >= max_lines:
                    break
                line = line.strip()
                if line:
                    try:
                        events.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
    except Exception as exc:
        logger.error("Failed to read brainlog %s: %s", file, exc)
    return events


def _read_agent_log(max_lines: int = 200) -> List[str]:
    """Read the last N lines from agent.log."""
    if not _AGENT_LOG.exists():
        return []
    try:
        with open(_AGENT_LOG, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        return lines[-max_lines:]
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Trace building
# ---------------------------------------------------------------------------


def build_trace_from_events(
    events: List[dict],
    session_id: str = "latest",
    max_events: int = 100,
) -> AgentTrace:
    """Build an AgentTrace from a list of raw brainlog events."""
    trace = AgentTrace(session_id=session_id)
    trace_events = []

    for ev in events[:max_events]:
        kind = ev.get("kind", ev.get("event_type", "unknown"))
        ts = ev.get("timestamp", ev.get("t", ""))
        content = ev.get("content", ev.get("text", ""))

        event = TraceEvent(
            timestamp=ts,
            event_type=kind,
            content=str(content)[:500],
            tool_name=ev.get("tool_name", ev.get("tool", "")),
            tool_args=ev.get("tool_args", ev.get("args", {})),
            duration_ms=ev.get("duration_ms", 0.0),
            success=ev.get("success", ev.get("ok", True)),
        )
        trace_events.append(event)

        if kind in ("tool_call", "tool_result"):
            trace.tool_calls += 1

    trace.events = trace_events
    trace.event_count = len(trace_events)
    if trace_events:
        trace.started_at = trace_events[0].timestamp
        if trace_events[-1].timestamp:
            try:
                t1 = datetime.fromisoformat(trace_events[0].timestamp)
                t2 = datetime.fromisoformat(trace_events[-1].timestamp)
                trace.total_duration_ms = (t2 - t1).total_seconds() * 1000
            except Exception:
                pass
    return trace


def get_recent_traces(limit: int = 10) -> List[AgentTrace]:
    """Load recent traces from brainlog files."""
    traces = []
    for f in _brainlog_files():
        events = _read_brainlog(f, max_lines=500)
        if events:
            trace = build_trace_from_events(events, session_id=f.stem)
            traces.append(trace)
    # Sort by start time, newest first
    traces.sort(key=lambda t: t.started_at, reverse=True)
    return traces[:limit]


def get_trace_stats() -> Dict[str, Any]:
    """Return aggregate statistics about all traces."""
    total_events = 0
    total_tool_calls = 0
    tool_counter: Counter = Counter()
    type_counter: Counter = Counter()

    for f in _brainlog_files():
        events = _read_brainlog(f, max_lines=1000)
        for ev in events:
            total_events += 1
            kind = ev.get("kind", ev.get("event_type", "unknown"))
            type_counter[kind] += 1
            if kind in ("tool_call", "tool_result"):
                total_tool_calls += 1
                tool_name = ev.get("tool_name", ev.get("tool", "unknown"))
                tool_counter[tool_name] += 1

    # Get session counts from session DB
    session_count = 0
    brain_records = 0
    brain_file = _BRAINLOG_DIR / "openamer-brain.jsonl"
    if brain_file.exists():
        try:
            with open(brain_file, "r") as f:
                brain_records = sum(1 for _ in f)
        except Exception:
            pass

    return {
        "total_events": total_events,
        "total_tool_calls": total_tool_calls,
        "session_count": session_count,
        "brain_records": brain_records,
        "top_tools": dict(tool_counter.most_common(10)),
        "event_type_distribution": dict(type_counter.most_common(10)),
        "trace_files": len(list(_brainlog_files())),
    }


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------


def _format_duration(ms: float) -> str:
    if ms < 1:
        return f"{ms * 1000:.0f}µs"
    if ms < 1000:
        return f"{ms:.0f}ms"
    return f"{ms / 1000:.1f}s"


def _format_timestamp(ts: str) -> str:
    if not ts:
        return "?"
    try:
        dt = datetime.fromisoformat(ts)
        return dt.strftime("%H:%M:%S.%f")[:12]
    except Exception:
        return ts[:19]


def print_trace(trace: AgentTrace, verbose: bool = False) -> None:
    """Print a trace to the console."""
    print(f"\n{'='*60}")
    print(f"  Trace: {trace.session_id}")
    print(f"  Events: {trace.event_count} | Tool calls: {trace.tool_calls}")
    if trace.total_duration_ms:
        print(f"  Duration: {_format_duration(trace.total_duration_ms)}")
    print(f"{'='*60}")

    for i, ev in enumerate(trace.events):
        prefix = f"  [{i+1:3d}]"
        ts = _format_timestamp(ev.timestamp)
        icon = {
            "user_message": "💬",
            "assistant_message": "🤖",
            "tool_call": "🔧",
            "tool_result": "✅" if ev.success else "❌",
            "thinking": "💭",
            "error": "🔥",
        }.get(ev.event_type, "•")

        duration = ""
        if ev.duration_ms > 0:
            duration = f" ({_format_duration(ev.duration_ms)})"

        if ev.event_type == "tool_call":
            args_preview = str(ev.tool_args)[:80] if ev.tool_args else ""
            print(f"  {icon} {ts} CALL {ev.tool_name}{duration}")
            if args_preview:
                print(f"       args: {args_preview}")
        elif ev.event_type == "tool_result":
            content_preview = ev.content[:100] if ev.content else ""
            print(f"  {icon} {ts} RESULT{duration}")
            if content_preview:
                print(f"       {content_preview}")
        elif ev.event_type in ("user_message", "assistant_message"):
            preview = ev.content[:120].replace("\n", " ")
            print(f"  {icon} {ts} {preview}")
        else:
            preview = ev.content[:120].replace("\n", " ")
            print(f"  {icon} {ts} {preview}")


# ---------------------------------------------------------------------------
# CLI entry points
# ---------------------------------------------------------------------------


def cmd_trace_list(args) -> None:
    """List recent traces."""
    limit = getattr(args, "limit", 10)
    traces = get_recent_traces(limit=limit)
    if not traces:
        print("No traces found. Start using the agent to generate activity.")
        return

    print(f"\nRecent Traces ({len(traces)}):")
    print(f"{'ID':<30} {'Events':<8} {'Tools':<6} {'Duration':<10}")
    print("-" * 60)
    for t in traces:
        dur = _format_duration(t.total_duration_ms) if t.total_duration_ms else "-"
        print(f"{t.session_id:<30} {t.event_count:<8} {t.tool_calls:<6} {dur:<10}")


def cmd_trace_show(args) -> None:
    """Show a full trace with timeline."""
    session_id = getattr(args, "session_id", "")
    verbose = getattr(args, "verbose", False)

    if not session_id:
        traces = get_recent_traces(limit=1)
        if traces:
            print_trace(traces[0], verbose=verbose)
        else:
            print("No traces available.")
        return

    # Try to find the trace by session_id
    for f in _brainlog_files():
        if session_id in f.stem:
            events = _read_brainlog(f, max_lines=200)
            trace = build_trace_from_events(events, session_id=f.stem)
            print_trace(trace, verbose=verbose)
            return

    print(f"No trace found for session: {session_id}")


def cmd_trace_stats(args) -> None:
    """Show aggregate trace statistics."""
    stats = get_trace_stats()
    print("\nTrace Statistics:")
    print(f"  Total events: {stats['total_events']}")
    print(f"  Total tool calls: {stats['total_tool_calls']}")
    print(f"  Brain records: {stats['brain_records']}")
    print(f"  Trace files: {stats['trace_files']}")

    if stats['top_tools']:
        print(f"\n  Top Tools:")
        for tool, count in stats['top_tools'].items():
            print(f"    {tool}: {count}x")

    if stats['event_type_distribution']:
        print(f"\n  Event Distribution:")
        for kind, count in stats['event_type_distribution'].items():
            print(f"    {kind}: {count}x")


def cmd_trace_watch(args) -> None:
    """Live tail of agent activity."""
    lines_count = getattr(args, "lines", 20)
    follow = getattr(args, "follow", False)

    lines = _read_agent_log(max_lines=lines_count)
    if not lines:
        print("No agent.log found. Start the agent first.")
        return

    print(f"\nAgent Log (last {len(lines)} lines):")
    print("-" * 60)
    for line in lines:
        print(line.rstrip())


def build_trace_parser(subparsers) -> None:
    """Add the ``openamer trace`` subcommand."""
    parser = subparsers.add_parser(
        "trace",
        help="View agent execution traces and observability data",
        description=(
            "Inspect what the agent did, which tools it called, "
            "and how long each step took. Read from brainlog and session data."
        ),
    )
    sub = parser.add_subparsers(dest="trace_action")

    # list
    list_p = sub.add_parser("list", help="List recent agent traces")
    list_p.add_argument("--limit", type=int, default=10, help="Max traces to show")

    # show
    show_p = sub.add_parser("show", help="Show full trace for a session")
    show_p.add_argument("session_id", nargs="?", default="", help="Session ID to inspect")
    show_p.add_argument("--verbose", "-v", action="store_true", help="Show full details")

    # stats
    sub.add_parser("stats", help="Show aggregate trace statistics")

    # watch
    watch_p = sub.add_parser("watch", help="Live tail of agent.log")
    watch_p.add_argument("--lines", "-n", type=int, default=20, help="Number of lines")
    watch_p.add_argument("--follow", "-f", action="store_true", help="Follow mode (tail -f)")

    parser.set_defaults(func=cmd_trace_list)