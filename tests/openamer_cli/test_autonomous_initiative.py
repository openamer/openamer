"""Tests for ``openamer_cli.autonomous_initiative`` and ``openamer_cli.subcommands.initiative``.

Exercises the health check, auto-fix, proactive suggestions, and the
full initiative cycle with an isolated temp OPENAMER_HOME so no real
user data is touched.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from unittest.mock import patch

import pytest


# =========================================================================
# Fixtures
# =========================================================================


@pytest.fixture
def openamer_home(tmp_path: Path) -> Path:
    """Isolated OPENAMER_HOME with minimal skeleton."""
    home = tmp_path / ".openamer"
    home.mkdir(parents=True)
    # Create minimal infrastructure
    (home / "a2a").mkdir()
    (home / "skills").mkdir()
    (home / "memories").mkdir()
    (home / "cron").mkdir()
    return home


@pytest.fixture
def patch_home(openamer_home: Path, monkeypatch) -> None:
    """Point OPENAMER_HOME at the isolated temp directory."""
    monkeypatch.setenv("OPENAMER_HOME", str(openamer_home))


@pytest.fixture
def patch_superintelligence(monkeypatch) -> None:
    """Mock ``check_all_systems`` to return a predictable health state so
    tests don't depend on the actual filesystem state under default home."""

    def _fake_check() -> dict:
        return {
            "brain_learning_loop": "pass",
            "a2a_swarm_connectivity": "pass",
            "skills_count": "pass",
            "skills_improvement_rate": "pass",
            "memory_usage": "pass",
            "memory_growth": "pass",
            "computer_use_readiness": "pass",
            "multi_agent_orchestration": "pass",
            "overall_score": 95,
            "timestamp": "2026-01-01T00:00:00+00:00",
        }

    monkeypatch.setattr(
        "openamer_cli.superintelligence.check_all_systems",
        _fake_check,
    )


@pytest.fixture
def patch_unhealthy_superintelligence(monkeypatch) -> None:
    """Mock ``check_all_systems`` to return a DEGRADED state."""

    def _fake_check() -> dict:
        return {
            "brain_learning_loop": "fail",
            "a2a_swarm_connectivity": "fail",
            "skills_count": "fail",
            "skills_improvement_rate": "warn",
            "memory_usage": "pass",
            "memory_growth": "warn",
            "computer_use_readiness": "fail",
            "multi_agent_orchestration": "fail",
            "overall_score": 25,
            "timestamp": "2026-01-01T00:00:00+00:00",
        }

    monkeypatch.setattr(
        "openamer_cli.superintelligence.check_all_systems",
        _fake_check,
    )


# =========================================================================
# Test 1: check_system_health()
# =========================================================================


def test_check_system_health_returns_dict(patch_superintelligence) -> None:
    """check_system_health() should return a dict with overall_score."""
    from openamer_cli.autonomous_initiative import check_system_health

    result = check_system_health()

    assert isinstance(result, dict)
    assert "overall_score" in result
    assert result["overall_score"] == 95
    assert result["brain_learning_loop"] == "pass"


# =========================================================================
# Test 2: auto_fix_issues() — healthy system (no fixes needed)
# =========================================================================


def test_auto_fix_issues_healthy(patch_superintelligence) -> None:
    """When all systems pass, auto_fix should return a no-op action."""
    from openamer_cli.autonomous_initiative import auto_fix_issues

    fixes = auto_fix_issues()

    assert isinstance(fixes, list)
    assert len(fixes) >= 1
    # The last fix should be the "all pass" message
    assert fixes[-1]["status"] == "pass"
    assert fixes[-1]["action"] == "none_needed"


# =========================================================================
# Test 3: auto_fix_issues() — unhealthy system with dry_run
# =========================================================================


def test_auto_fix_issues_unhealthy_dry_run(
    patch_unhealthy_superintelligence, patch_home, openamer_home
) -> None:
    """When system is degraded, dry_run should report would_fix without
    actually creating files."""
    from openamer_cli.autonomous_initiative import auto_fix_issues

    fixes = auto_fix_issues(dry_run=True)

    assert isinstance(fixes, list)
    assert len(fixes) > 0

    # There should be "would_fix" entries, not "fixed"
    would_fix = [f for f in fixes if f.get("status") == "would_fix"]
    assert len(would_fix) > 0, "Expected at least one would_fix action"

    # Dry run must NOT create files
    brain_file = openamer_home / "a2a" / "openamer-brain.jsonl"
    assert not brain_file.exists(), "Dry run should not create files"

    a2a_readme = openamer_home / "a2a" / "README.md"
    assert not a2a_readme.exists(), "Dry run should not create A2A files"


# =========================================================================
# Test 4: auto_fix_issues() — unhealthy system actually fixing
# =========================================================================


def test_auto_fix_issues_unhealthy_actual_fix(
    patch_unhealthy_superintelligence, patch_home, openamer_home
) -> None:
    """When system is degraded, actual run should create missing files."""
    from openamer_cli.autonomous_initiative import auto_fix_issues

    fixes = auto_fix_issues(dry_run=False)

    assert isinstance(fixes, list)
    assert len(fixes) > 0

    # Should have fixed brain
    fixed = [f for f in fixes if f.get("status") == "fixed"]
    assert len(fixed) > 0, "Expected at least one fixed action"

    # Files should now exist — brain.jsonl is created first which also
    # satisfies the A2A directory check (it's in the same a2a/ dir).
    brain_file = openamer_home / "a2a" / "openamer-brain.jsonl"
    assert brain_file.exists(), "Brain JSONL should be created"

    # README won't be written because brain.jsonl being in the same
    # directory already satisfies _fix_a2a_connectivity's count check.
    # Verify the brain jsonl was written instead.
    content = json.loads(brain_file.read_text(encoding="utf-8"))
    assert content == [], "Brain JSONL should contain empty array"

    # Skills dir should have a new skill
    md_files = list(openamer_home.rglob("*.md"))
    assert any("system-health" in str(f) for f in md_files), (
        "Expected a base skill to be created"
    )


# =========================================================================
# Test 5: proactive_suggestions() — detects stale patterns
# =========================================================================


def test_proactive_suggestions_detects_stale_skills(
    patch_superintelligence, patch_home, openamer_home
) -> None:
    """When no skills exist or they're old, suggestions should flag it."""
    from openamer_cli.autonomous_initiative import proactive_suggestions

    # No skills at all -> will trigger stale detection
    suggestions = proactive_suggestions()

    assert isinstance(suggestions, list)
    assert len(suggestions) > 0

    # Should have cron suggestion (empty cron dir)
    categories = [s["category"] for s in suggestions]
    assert "cron" in categories, "Expected cron category suggestion"


# =========================================================================
# Test 6: run_initiative_cycle() — full cycle
# =========================================================================


def test_run_initiative_cycle_full(
    patch_superintelligence, patch_home
) -> None:
    """run_initiative_cycle should return a complete result dict."""
    from openamer_cli.autonomous_initiative import run_initiative_cycle

    result = run_initiative_cycle(dry_run=True, verbose=False)

    assert isinstance(result, dict)
    assert "health" in result
    assert "fixes" in result
    assert "suggestions" in result
    assert "summary" in result
    assert result["summary"]["score"] == 95
    assert result["summary"]["fixes_applied"] == 0  # All pass


# =========================================================================
# Test 7: CLI parser — registers all subcommands
# =========================================================================


def test_build_initiative_parser_registers_subcommands() -> None:
    """build_initiative_parser should register check, fix, suggest, auto."""
    import argparse

    from openamer_cli.subcommands.initiative import build_initiative_parser

    parser = argparse.ArgumentParser(prog="openamer")
    sub = parser.add_subparsers()
    build_initiative_parser(sub)

    for cmd in ("check", "fix", "suggest", "auto"):
        args = parser.parse_args(["initiative", cmd])
        assert args.initiative_command == cmd
        assert hasattr(args, "func"), f"{cmd} should set func"


# =========================================================================
# Test 8: CLI parser — prints help on no subcommand
# =========================================================================


def test_build_initiative_parser_prints_help_on_no_subcommand(capsys) -> None:
    """``openamer initiative`` without subcommand should print help."""
    import argparse

    from openamer_cli.subcommands.initiative import build_initiative_parser

    parser = argparse.ArgumentParser(prog="openamer")
    sub = parser.add_subparsers()
    build_initiative_parser(sub)

    args = parser.parse_args(["initiative"])
    rc = args.func(args) if hasattr(args, "func") else parser.print_help()
    out = capsys.readouterr().out
    err = capsys.readouterr().err

    # The handler prints to stderr when no subcommand
    # Re-run to capture stderr
    import io
    stderr = io.StringIO()
    with patch("sys.stderr", stderr):
        import argparse as ap
        p = ap.ArgumentParser(prog="openamer")
        s = p.add_subparsers()
        build_initiative_parser(s)
        a = p.parse_args(["initiative"])
        a.func(a) if hasattr(a, "func") else None

    output = stderr.getvalue()
    assert "check" in output
    assert "fix" in output
    assert "suggest" in output
    assert "auto" in output


# =========================================================================
# Test 9: CLI --json flag works
# =========================================================================


def test_cmd_check_json(patch_superintelligence, capsys) -> None:
    """``initiative check --json`` should output raw JSON."""
    from openamer_cli.subcommands.initiative import _cmd_check

    class FakeArgs:
        initiative_command = "check"
        json = True

    rc = _cmd_check(FakeArgs())
    out = capsys.readouterr().out

    assert rc == 0
    parsed = json.loads(out)
    assert parsed["overall_score"] == 95


# =========================================================================
# Test 10: auto_fix_issues unhealthy without dry_run actually writes files
# =========================================================================


def test_auto_fix_issues_creates_memory_snapshot(
    patch_unhealthy_superintelligence, patch_home, openamer_home
) -> None:
    """When memory_growth is warn/fail, auto_fix should create a snapshot."""
    from openamer_cli.autonomous_initiative import auto_fix_issues

    auto_fix_issues(dry_run=False)

    # Should have created a memory snapshot
    md_files = list(openamer_home.rglob("*.md"))
    snapshot_found = any("initiative-snapshot" in f.name for f in md_files)
    assert snapshot_found, "Expected a memory snapshot file"


# =========================================================================
# Test 11: run_cron_entry logs to file
# =========================================================================


def test_run_cron_entry_logs(patch_superintelligence, patch_home, openamer_home) -> None:
    """run_cron_entry should write a log file under OPENAMER_HOME/logs/."""
    from openamer_cli.autonomous_initiative import run_cron_entry

    rc = run_cron_entry()

    assert rc == 0

    log_dir = openamer_home / "logs"
    assert log_dir.is_dir()

    log_files = list(log_dir.glob("initiative-*.json"))
    assert len(log_files) >= 1

    # Verify content
    content = json.loads(log_files[0].read_text(encoding="utf-8"))
    assert content["summary"]["score"] == 95
    assert "health" in content