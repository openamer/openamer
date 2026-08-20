"""Tests for ``openamer_cli.brain_cli`` — ``openamer brain stats|status|graph|insights``.

Exercises the four display functions with a temporary brain dataset, trajectories
and mesh memory so no real user data is touched.
"""

from __future__ import annotations

import json
import pathlib
import time
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

import pytest

from openamer_cli import brain_cli


# ── fixtures ───────────────────────────────────────────────────────────────

@pytest.fixture
def brain_path(tmp_path: pathlib.Path) -> pathlib.Path:
    """Create a realistic brain JSONL with a handful of records."""
    brain = tmp_path / "a2a" / "openamer-brain.jsonl"
    brain.parent.mkdir(parents=True)
    records = [
        {"engine": "trajectory", "topic": "chat",
         "messages": [{"role": "user", "content": "hello"},
                      {"role": "assistant", "content": "hi"}]},
        {"engine": "trajectory", "topic": "chat", "_session_id": "sess_001",
         "messages": [{"role": "user", "content": "help"},
                      {"role": "assistant", "content": "sure"}]},
        {"engine": "skill", "topic": "",
         "messages": [{"role": "system", "content": "You are OpenAmer."},
                      {"role": "user", "content": "Describe the skill 'code-review'"},
                      {"role": "assistant", "content": "Skill 'code-review' published by openamer, 3 files"}]},
        {"engine": "insight", "topic": "general",
         "messages": [{"role": "system", "content": "You are OpenAmer."},
                      {"role": "user", "content": "Share a lesson"},
                      {"role": "assistant", "content": "Always verify tool results."}]},
        {"engine": "trajectory", "topic": "coding", "_session_id": "sess_002",
         "messages": [{"role": "user", "content": "write code"},
                      {"role": "assistant", "content": "```python\nx=1\n```"}]},
    ]
    brain.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in records),
        encoding="utf-8",
    )
    return brain


@pytest.fixture
def traj_path(tmp_path: pathlib.Path) -> pathlib.Path:
    """Daemon trajectories staging file with _exported_at timestamps."""
    traj = tmp_path / "trajectories" / "daemon-trajectories.jsonl"
    traj.parent.mkdir(parents=True)
    now = datetime.now(timezone.utc)
    records = []
    for i in range(10):
        dt = now - timedelta(days=i // 3)  # spread across 3-4 days
        records.append({
            "_fingerprint": f"traj:sess_{i}:hash",
            "_session_id": f"sess_{i:03d}",
            "_session_title": f"Session {i}",
            "_exported_at": dt.isoformat(),
            "engine": "trajectory",
            "topic": "chat",
            "messages": [],
            "stats": {"total_turns": 3},
        })
    traj.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in records),
        encoding="utf-8",
    )
    return traj


@pytest.fixture
def memory_path(tmp_path: pathlib.Path) -> pathlib.Path:
    """Minimal mesh memory file."""
    mem = tmp_path / "MEMORY-official-mesh.md"
    mem.write_text(
        "#mesh:general: Lesson Learned — Always verify tool outputs before acting.\n"
        "#mesh:security: Key Insight — Never log secrets to stdout.\n",
        encoding="utf-8",
    )
    return mem


@pytest.fixture
def skills_dir(tmp_path: pathlib.Path) -> pathlib.Path:
    """Simulated skills directory."""
    sk = tmp_path / "skills"
    sk.mkdir(parents=True)
    (sk / "code-review.md").write_text("# Code Review Skill\n", encoding="utf-8")
    (sk / "github.md").write_text("# GitHub Skill\n", encoding="utf-8")
    (sk / "testing.md").write_text("# Testing Skill\n", encoding="utf-8")
    return sk


@pytest.fixture
def home_dir(tmp_path, brain_path, traj_path, memory_path) -> pathlib.Path:
    """Orchestrates all data files under a temp OPENAMER_HOME."""
    # Files are already created by the other fixtures which place them under
    # tmp_path. We just need to make sure the paths are consistent.
    return tmp_path


# ── brain_stats ────────────────────────────────────────────────────────────

def test_brain_stats_no_brain(capsys):
    """brain_stats() should gracefully report no data when the file is missing."""
    # Temporarily point _home at an empty dir
    with patch.object(brain_cli, "_home", return_value=pathlib.Path("/tmp/nonexistent-openamer-XXXX")):
        rc = brain_cli.brain_stats()
    assert rc == 0
    captured = capsys.readouterr().out
    assert "not found" in captured


def test_brain_stats_with_data(capsys, home_dir, brain_path):
    """brain_stats() should report record counts, sizes, and timestamps."""
    # Ensure skills dir exists under home_dir with contents
    skills_path = home_dir / "skills"
    skills_path.mkdir(parents=True, exist_ok=True)
    (skills_path / "review.md").write_text("# Review\n", encoding="utf-8")
    (skills_path / "test.md").write_text("# Test\n", encoding="utf-8")

    # Ensure memory file exists
    (home_dir / "MEMORY-official-mesh.md").write_text(
        "#mesh:general: lesson\n", encoding="utf-8",
    )

    with (
        patch.object(brain_cli, "_home", return_value=home_dir),
        patch.object(brain_cli, "_skills_dir", return_value=skills_path),
    ):
        rc = brain_cli.brain_stats()

    assert rc == 0
    out = capsys.readouterr().out
    # Check key stats are displayed
    assert "total records" in out.lower()
    assert "5" in out  # 5 records in brain_path
    assert "trajectories" in out.lower()
    assert "skills" in out.lower()
    assert "insights" in out.lower()


# ── brain_status ────────────────────────────────────────────────────────────

def test_brain_status_healthy(capsys, home_dir, brain_path, memory_path):
    """brain_status() should show active loop when everything is in place."""
    # Ensure activity log exists too
    (home_dir / "a2a" / "activity.jsonl").write_text(
        json.dumps({"ts": 1000, "kind": "user"}) + "\n",
        encoding="utf-8",
    )

    with (
        patch.object(brain_cli, "_home", return_value=home_dir),
        patch.object(brain_cli, "_autolog_enabled", return_value=True),
        patch.object(brain_cli, "_check_daemon_running", return_value=True),
        patch.object(brain_cli, "_skills_dir", return_value=home_dir / "skills"),
    ):
        (home_dir / "skills").mkdir(parents=True, exist_ok=True)
        rc = brain_cli.brain_status()

    assert rc == 0
    out = capsys.readouterr().out
    assert "✅" in out
    assert "active" in out.lower()


def test_brain_status_missing(capsys):
    """brain_status() should warn when no brain file exists."""
    with (
        patch.object(brain_cli, "_home", return_value=pathlib.Path("/tmp/empty-brain-test")),
        patch.object(brain_cli, "_autolog_enabled", return_value=False),
        patch.object(brain_cli, "_check_daemon_running", return_value=False),
    ):
        rc = brain_cli.brain_status()

    assert rc == 0
    out = capsys.readouterr().out
    assert "⚠️" in out or "❌" in out
    assert "learning loop" in out.lower()


# ── brain_graph ────────────────────────────────────────────────────────────

def test_brain_graph_no_data(capsys):
    """brain_graph() should handle an empty trajectories directory."""
    with patch.object(brain_cli, "_trajectory_file", return_value=pathlib.Path("/tmp/no-traj.jsonl")):
        rc = brain_cli.brain_graph()
    assert rc == 0
    out = capsys.readouterr().out
    assert "no brain growth data" in out.lower() or "no" in out.lower()


def test_brain_graph_with_trajectories(capsys, home_dir, traj_path):
    """brain_graph() should plot bars when trajectories exist."""
    with patch.object(brain_cli, "_trajectory_file", return_value=traj_path):
        rc = brain_cli.brain_graph()
    assert rc == 0
    out = capsys.readouterr().out
    # Should show the graph header and some bars
    assert "Brain Growth" in out or "Records per Day" in out
    # Should have something like "|" and "█" or "░"
    assert "|" in out


# ── brain_insights ─────────────────────────────────────────────────────────

def test_brain_insights_empty(capsys):
    """brain_insights() should report empty when no brain file."""
    with patch.object(brain_cli, "_brain_jsonl", return_value=pathlib.Path("/tmp/no-brain.jsonl")):
        rc = brain_cli.brain_insights()
    assert rc == 0
    out = capsys.readouterr().out
    assert "no brain data" in out.lower() or "empty" in out.lower()


def test_brain_insights_with_data(capsys, home_dir, brain_path, memory_path):
    """brain_insights() should show engine distribution and memory entries."""
    with (
        patch.object(brain_cli, "_home", return_value=home_dir),
        patch.object(brain_cli, "_trajectory_file", return_value=home_dir / "trajectories" / "daemon-trajectories.jsonl"),
        patch.object(brain_cli, "_activity_log", return_value=home_dir / "a2a" / "activity.jsonl"),
        patch.object(brain_cli, "_skills_dir", return_value=home_dir / "skills"),
    ):
        (home_dir / "skills").mkdir(parents=True, exist_ok=True)
        rc = brain_cli.brain_insights()

    assert rc == 0
    out = capsys.readouterr().out
    # Check key outputs
    assert "5" in out  # total records
    assert "trajectory" in out
    assert "skill" in out
    assert "insight" in out
    assert "memory" in out.lower()
    assert "Lesson" in out or "Insight" in out or "Always verify" in out


# ── Parser builder ─────────────────────────────────────────────────────────

def test_build_brain_parser_creates_subcommands():
    """build_brain_parser() should register stats, status, graph, insights."""
    import argparse
    parser = argparse.ArgumentParser(prog="openamer")
    sub = parser.add_subparsers()

    brain_cli.build_brain_parser(sub)

    # Try parsing each subcommand
    for cmd in ("stats", "status", "graph", "insights"):
        args = parser.parse_args(["brain", cmd])
        assert args.brain_subcommand == cmd
        assert hasattr(args, "func"), f"{cmd} should set func"


def test_build_brain_parser_print_help_on_no_subcommand(capsys):
    """``openamer brain`` without subcommand should print help."""
    import argparse
    parser = argparse.ArgumentParser(prog="openamer")
    sub = parser.add_subparsers()
    brain_cli.build_brain_parser(sub)

    args = parser.parse_args(["brain"])
    rc = args.func(args) if hasattr(args, "func") else parser.print_help()
    if rc is None:
        rc = 0
    out = capsys.readouterr().out
    assert "stats" in out
    assert "status" in out
    assert "graph" in out
    assert "insights" in out