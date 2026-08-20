"""``openamer_cli.brain_cli`` — make the learning loop visible and measurable.

Provides the ``openamer brain stats | status | graph | insights`` subcommands
that read the A2A brain dataset (``~/.openamer/a2a/openamer-brain.jsonl``),
activity logs, autolog status, trajectories and mesh memory to show _what_ the
brain has collected and _how healthy_ the learning pipeline is.

All functions use stdlib only (no numpy, pandas, or third-party deps).
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from collections import Counter, defaultdict
from datetime import date, datetime, timezone, timedelta
from pathlib import Path


# ── helpers ────────────────────────────────────────────────────────────────

def _home() -> Path:
    return Path(os.environ.get("OPENAMER_HOME", Path.home() / ".openamer"))


def _brain_jsonl() -> Path:
    return _home() / "a2a" / "openamer-brain.jsonl"


def _trajectory_file() -> Path:
    return _home() / "trajectories" / "daemon-trajectories.jsonl"


def _activity_log() -> Path:
    return _home() / "a2a" / "activity.jsonl"


def _memory_file() -> Path:
    return _home() / "MEMORY-official-mesh.md"


def _skills_dir() -> Path:
    # OpenAmer skills live under the profile home
    return Path.home() / "AppData" / "Local" / "openamer-laptop" / "skills"


def _load_jsonl(path: Path) -> list[dict]:
    """Load all non-empty JSON lines from *path*."""
    if not path.exists():
        return []
    records: list[dict] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return records


def _fmt_bytes(n: int) -> str:
    """Human-readable file size."""
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def _autolog_enabled() -> bool:
    """Return True if the autolog is ON."""
    try:
        from openamer_cli.a2a import autolog
        return autolog.enabled()
    except Exception:
        return False


# ── brain_stats ────────────────────────────────────────────────────────────

def brain_stats() -> int:
    """Show brain file size, total records, sessions, skills, memory, last update."""
    brain = _brain_jsonl()
    if not brain.exists():
        print("✗ Brain dataset not found — nothing collected yet.")
        print(f"  Expected at: {brain}")
        return 0

    records = _load_jsonl(brain)
    total = len(records)

    # Count by engine
    engines: Counter[str] = Counter()
    session_ids: set[str] = set()
    for r in records:
        engines[r.get("engine", "unknown")] += 1
        sid = r.get("_session_id") or r.get("session", "")
        if sid:
            session_ids.add(sid)

    # Skills count (on disk)
    skills_dir = _skills_dir()
    skill_count = len([p for p in skills_dir.iterdir() if p.is_dir() or p.suffix == ".md"]) if skills_dir.exists() else 0

    # Memory file
    mem = _memory_file()
    mem_size = mem.stat().st_size if mem.exists() else 0
    mem_entries = 0
    if mem.exists():
        mem_entries = sum(1 for l in mem.read_text(encoding="utf-8", errors="replace").splitlines() if l.startswith("#mesh:"))

    # Last modified timestamps
    brain_mtime = datetime.fromtimestamp(brain.stat().st_mtime, tz=timezone.utc)
    brain_size = brain.stat().st_size

    print("🧠 OpenAmer Brain Statistics")
    print(f"  Dataset file      : {brain}")
    print(f"  File size         : {_fmt_bytes(brain_size)}")
    print(f"  Total records     : {total}")
    print(f"  ─ trajectories    : {engines.get('trajectory', 0)}")
    print(f"  ─ skills          : {engines.get('skill', 0)}")
    print(f"  ─ insights        : {engines.get('insight', 0)}")
    print(f"  Unique sessions   : {len(session_ids) if session_ids else 'N/A'}")
    print(f"  Skills on disk    : {skill_count}")
    print(f"  Mesh memory size  : {_fmt_bytes(mem_size)} ({mem_entries} entries)")
    print(f"  Last updated      : {brain_mtime.strftime('%Y-%m-%d %H:%M UTC')}")
    return 0


# ── brain_status ────────────────────────────────────────────────────────────

def brain_status() -> int:
    """Show if the learning loop is active and what's missing."""
    checks: list[tuple[str, bool, str]] = []

    # 1. Autolog
    autolog_on = _autolog_enabled()
    checks.append(("Automatic activity capture (autolog)", autolog_on,
                    "run `openamer a2a brain autolog on`"))

    # 2. Brain dataset exists
    brain = _brain_jsonl()
    has_brain = brain.exists()
    checks.append(("Brain dataset exists", has_brain,
                    "run `openamer a2a brain collect`"))

    # 3. Brain has records
    has_records = False
    if has_brain:
        records = _load_jsonl(brain)
        has_records = len(records) > 0
    checks.append(("Brain has records", has_records,
                    "use OpenAmer in chat mode to generate trajectories"))

    # 4. Trajectories staging directory
    traj = _trajectory_file()
    has_traj = traj.exists() and traj.stat().st_size > 0
    checks.append(("Trajectories staging file", has_traj,
                    "start the session-to-brain daemon (`openamer session-to-brain --watch`)"))

    # 5. Mesh memory
    mem = _memory_file()
    has_mem = mem.exists()
    checks.append(("Mesh memory file", has_mem,
                    "create ~/.openamer/MEMORY-official-mesh.md"))

    # 6. Daemon process (heuristic: check for session_to_brain running)
    has_daemon = _check_daemon_running()
    checks.append(("Session-to-brain daemon running", has_daemon,
                    "run `python scripts/session_to_brain.py --watch`"))

    # Grade
    ok = sum(1 for _, passed, _ in checks if passed)
    total_checks = len(checks)

    print("┌─ OpenAmer Brain — Learning Loop Status ───────────────────┐")
    for label, passed, hint in checks:
        symbol = "✅" if passed else "⚠️ "
        print(f"  {symbol}  {label}")
        if not passed:
            print(f"        Fix: {hint}")
    print("└────────────────────────────────────────────────────────────┘")

    if ok == total_checks:
        print("✅ Learning loop active — all systems go.")
    elif ok >= total_checks - 2:
        print("⚠️  Learning loop partially active — most components OK.")
    else:
        print("❌ Learning loop inactive — set up missing components.")
    return 0


def _check_daemon_running() -> bool:
    """Heuristic check: is session_to_brain watching?"""
    try:
        # Try openamer-specific process name / python script matching
        if os.name == "nt":
            result = subprocess.run(
                ["tasklist", "/FO", "CSV", "/NH"],
                capture_output=True, text=True, timeout=5,
            )
            # Look for any running openamer processes (the daemon runs as part of the agent)
            return "session_to_brain" in result.stdout.lower()
        else:
            result = subprocess.run(
                ["ps", "aux"],
                capture_output=True, text=True, timeout=5,
            )
            return "session_to_brain" in result.stdout
    except Exception:
        return False


# ── brain_graph ────────────────────────────────────────────────────────────

def brain_graph() -> int:
    """ASCII bar chart: records per day for the last 7 days.

    Uses the daemon trajectories staging file (which has ``_exported_at``
    timestamps) plus the brain dataset modification time as fallback.
    """
    traj = _trajectory_file()

    # Collect per-day counts from the trajectories staging file
    day_counts: dict[str, int] = defaultdict(int)

    if traj.exists():
        records = _load_jsonl(traj)
        for r in records:
            ts = r.get("_exported_at")
            if ts:
                try:
                    d = datetime.fromisoformat(ts).date().isoformat()
                    day_counts[d] += 1
                except (ValueError, TypeError):
                    pass

    # If no trajectory data, fall back to brain file mtime
    brain = _brain_jsonl()
    if not day_counts and brain.exists():
        mtime = datetime.fromtimestamp(brain.stat().st_mtime, tz=timezone.utc)
        day_counts[mtime.date().isoformat()] = 1  # placeholder — just one bar

    # Build the 7-day window
    today = date.today()
    window = [today - timedelta(days=i) for i in range(6, -1, -1)]

    if not day_counts:
        print("📊 No brain growth data available yet.")
        print("   Start using OpenAmer and the brain will begin collecting.")
        return 0

    max_count = max(day_counts.values()) if day_counts else 1
    # Cap scale so bars fit in ~50 chars
    scale = max(1, max_count / 30)

    print("📊 Brain Growth — Records per Day (last 7 days)")
    print(f"    Scale: each {'█' if max_count > 0 else '·'} ≈ {scale:.0f} record(s)")
    print()

    for d in window:
        ds = d.isoformat()
        count = day_counts.get(ds, 0)
        bar_len = int(count / scale) if scale > 0 else 0
        bar = "█" * bar_len + "░" * (30 - bar_len) if bar_len > 0 else "░" * 30
        label = "today" if d == today else d.strftime("%a")
        print(f"  {label:6s} |{bar}| {count}")

    # Summary
    if day_counts:
        total_last_7 = sum(day_counts.get(d.isoformat(), 0) for d in window)
        print(f"\n  Total records in window: {total_last_7}")
        if brain.exists():
            total_all = len(_load_jsonl(brain))
            print(f"  Total brain records:     {total_all}")
    return 0


# ── brain_insights ─────────────────────────────────────────────────────────

def brain_insights() -> int:
    """Show what the brain has learned: top skills, memory patterns, trends."""
    brain = _brain_jsonl()
    if not brain.exists():
        print("✗ No brain data to analyze.")
        return 0

    records = _load_jsonl(brain)
    if not records:
        print("✗ Brain is empty.")
        return 0

    # ── Engine distribution ──
    engines: Counter[str] = Counter()
    for r in records:
        engines[r.get("engine", "unknown")] += 1

    print("🧠 Brain Insights")
    print(f"  Total records: {len(records)}")
    print(f"  Distribution: trajectory={engines.get('trajectory',0)}, "
          f"skill={engines.get('skill',0)}, insight={engines.get('insight',0)}")
    print()

    # ── Session trends ──
    session_ids: set[str] = set()
    total_turns = 0
    for r in records:
        sid = r.get("_session_id") or ""
        if sid:
            session_ids.add(sid)
        msgs = r.get("messages") or []
        total_turns += len(msgs)

    print(f"  📋 Sessions referenced: {len(session_ids)}")
    if records:
        avg_turns = total_turns / len(records)
        print(f"  📏 Avg turns per record: {avg_turns:.1f}")

    # ── Topics ──
    topics: Counter[str] = Counter()
    for r in records:
        t = r.get("topic") or ""
        if t:
            topics[t] += 1
    if topics:
        print(f"  🏷️  Topics ({len(topics)}):")
        for topic, count in topics.most_common(10):
            print(f"    {topic}: {count}")

    # ── Skills analysis ──
    skill_recs = [r for r in records if r.get("engine") == "skill"]
    if skill_recs:
        print(f"\n  🔧 Skills in brain ({len(skill_recs)} records):")
        for r in skill_recs[:5]:
            msgs = r.get("messages") or []
            for m in msgs:
                if m.get("role") == "assistant" and "Skill" in (m.get("content") or ""):
                    snippet = (m.get("content") or "")[:120]
                    print(f"    • {snippet}")
                    break

    # ── Memory patterns ──
    mem = _memory_file()
    if mem.exists():
        content = mem.read_text(encoding="utf-8", errors="replace")
        mesh_lines = [l for l in content.splitlines() if l.startswith("#mesh:")]
        if mesh_lines:
            print(f"\n  🧠 Mesh memory ({len(mesh_lines)} entries):")
            for line in mesh_lines[:5]:
                print(f"    {line[:100]}")

    # ── Daemon trajectory trends ──
    traj = _trajectory_file()
    if traj.exists():
        traj_records = _load_jsonl(traj)
        if traj_records:
            days: set[str] = set()
            for r in traj_records:
                ts = r.get("_exported_at", "")
                if ts:
                    try:
                        days.add(datetime.fromisoformat(ts).date().isoformat())
                    except Exception:
                        pass
            print(f"\n  ⏱️  Trajectory collection over {len(days)} day(s)")
            if len(traj_records) > 20:
                # Show the most recent session
                sorted_recs = sorted(traj_records,
                                     key=lambda r: r.get("_exported_at", ""),
                                     reverse=True)
                latest = sorted_recs[0]
                title = latest.get("_session_title", "untitled")
                ts = latest.get("_exported_at", "?")[:19]
                print(f"  Latest session: {title} ({ts})")

    # ── Activity log ──
    alog = _activity_log()
    if alog.exists():
        events = _load_jsonl(alog)
        if events:
            kinds: Counter[str] = Counter()
            for ev in events:
                kinds[ev.get("kind", "unknown")] += 1
            print(f"\n  📝 Activity log ({len(events)} events):")
            for kind, count in kinds.most_common(8):
                print(f"    {kind}: {count}")

    return 0


# ── Parser builder ─────────────────────────────────────────────────────────

def build_brain_parser(subparsers) -> None:
    """Attach the ``brain`` top-level command tree.

    Usage::

        openamer brain stats     → brain_stats()
        openamer brain status    → brain_status()
        openamer brain graph     → brain_graph()
        openamer brain insights  → brain_insights()
    """
    p = subparsers.add_parser("brain", help="Inspect the A2A brain — stats, status, growth, insights")
    sub = p.add_subparsers(dest="brain_subcommand")

    s = sub.add_parser("stats", help="Show brain file size, record counts, skills, memory")
    s.set_defaults(func=lambda a: brain_stats())

    st = sub.add_parser("status", help="Check if the learning loop is active")
    st.set_defaults(func=lambda a: brain_status())

    g = sub.add_parser("graph", help="ASCII bar chart of brain growth (7-day window)")
    g.set_defaults(func=lambda a: brain_graph())

    i = sub.add_parser("insights", help="Show what the brain has learned — top skills, trends")
    i.set_defaults(func=lambda a: brain_insights())

    p.set_defaults(func=lambda a: p.print_help())