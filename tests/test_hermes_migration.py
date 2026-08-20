"""Tests for Hermes Migration."""

from __future__ import annotations

import tempfile
from pathlib import Path

from openamer_cli.hermes_migration import (
    check_hermes,
    migrate_skills,
    migrate_memories,
    run_full_migration,
)


def _create_mock_hermes(base: Path) -> None:
    """Erstelle eine simulierte Hermes-Installation."""
    hermes = base / ".hermes"
    # Skills
    (hermes / "skills" / "general").mkdir(parents=True)
    (hermes / "skills" / "general" / "test-skill.md").write_text("# Test Skill\n\nA test skill for migration", encoding="utf-8")
    (hermes / "skills" / "coding").mkdir(parents=True)
    (hermes / "skills" / "coding" / "python.md").write_text("# Python Skill\n\nPython coding skill", encoding="utf-8")
    # Memories
    (hermes / "memories").mkdir(parents=True)
    (hermes / "memories" / "MEMORY.md").write_text("User prefers dark mode", encoding="utf-8")
    (hermes / "memories" / "USER.md").write_text("Name: Test User", encoding="utf-8")
    # Config
    (hermes / "config.yaml").write_text("model:\n  default: gpt-4\nprovider: openai", encoding="utf-8")
    # A2A
    (hermes / "a2a").mkdir(parents=True)
    (hermes / "a2a" / "identity.json").write_text('{"id": "test-node"}', encoding="utf-8")


def test_check_hermes_found():
    """Check erkennt eine Hermes-Installation."""
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        _create_mock_hermes(base)
        import openamer_cli.hermes_migration as hm
        orig = hm._hermes_home
        hm._hermes_home = lambda: base / ".hermes"
        hm._home = lambda: base / ".openamer"
        try:
            result = hm.check_hermes()
            assert result["hermes_found"] is True
            assert result["migratable"]["skills"] == 2
            assert result["migratable"]["memories"] == 2
            assert result["migratable"]["config"] is True
        finally:
            hm._hermes_home = orig


def test_check_hermes_not_found():
    """Check erkennt wenn Hermes nicht installiert ist."""
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        import openamer_cli.hermes_migration as hm
        orig = hm._hermes_home
        hm._hermes_home = lambda: base / ".hermes"
        try:
            result = hm.check_hermes()
            assert result["hermes_found"] is False
        finally:
            hm._hermes_home = orig


def test_migrate_skills():
    """Skills werden korrekt kopiert."""
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        _create_mock_hermes(base)
        import openamer_cli.hermes_migration as hm
        orig_hermes = hm._hermes_home
        orig_home = hm._home
        hm._hermes_home = lambda: base / ".hermes"
        hm._home = lambda: base / ".openamer"
        try:
            result = hm.migrate_skills(dry_run=False)
            assert len(result) == 2
            target = base / ".openamer" / "skills" / "hermes-imported"
            assert (target / "general" / "test-skill.md").exists()
            assert (target / "coding" / "python.md").exists()
        finally:
            hm._hermes_home = orig_hermes
            hm._home = orig_home


def test_migrate_memories():
    """Memories werden korrekt kopiert."""
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        _create_mock_hermes(base)
        import openamer_cli.hermes_migration as hm
        orig_hermes = hm._hermes_home
        orig_home = hm._home
        hm._hermes_home = lambda: base / ".hermes"
        hm._home = lambda: base / ".openamer"
        try:
            result = hm.migrate_memories(dry_run=False)
            assert len(result) == 2
            target = base / ".openamer" / "memories"
            assert (target / "hermes_MEMORY.md").exists()
            assert (target / "hermes_USER.md").exists()
        finally:
            hm._hermes_home = orig_hermes
            hm._home = orig_home


def test_dry_run():
    """Dry-Run verändert nichts."""
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        _create_mock_hermes(base)
        import openamer_cli.hermes_migration as hm
        orig_hermes = hm._hermes_home
        orig_home = hm._home
        hm._hermes_home = lambda: base / ".hermes"
        hm._home = lambda: base / ".openamer"
        try:
            result = hm.run_full_migration(dry_run=True)
            assert result["dry_run"] is True
            assert result["total_actions"] >= 1
            # Nichts wurde kopiert
            target = base / ".openamer" / "skills" / "hermes-imported"
            assert not target.exists()
        finally:
            hm._hermes_home = orig_hermes
            hm._home = orig_home


def test_full_migration():
    """Vollständige Migration funktioniert."""
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        _create_mock_hermes(base)
        import openamer_cli.hermes_migration as hm
        orig_hermes = hm._hermes_home
        orig_home = hm._home
        hm._hermes_home = lambda: base / ".hermes"
        hm._home = lambda: base / ".openamer"
        try:
            result = hm.run_full_migration(dry_run=False)
            assert result["status"] == "completed"
            assert result["total_actions"] >= 4
            assert "summary_file" in result
        finally:
            hm._hermes_home = orig_hermes
            hm._home = orig_home


def test_no_hermes():
    """Migration ohne Hermes-Installation gibt Fehler."""
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        import openamer_cli.hermes_migration as hm
        orig_hermes = hm._hermes_home
        hm._hermes_home = lambda: base / ".hermes-missing"
        try:
            result = hm.run_full_migration()
            assert result["status"] == "error"
        finally:
            hm._hermes_home = orig_hermes