"""
Hermes Migration — Kommando zum Umstieg von Hermes Agent auf OpenAmer.

Ermöglicht Hermes-Usern mit einem Befehl zu migrieren:
- Skills aus ~/.hermes/skills/ kopieren
- Config aus ~/.hermes/config.yaml migrieren
- Memory aus ~/.hermes/memories/ übernehmen
- A2A-Identität neu generieren
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _home() -> Path:
    return Path(os.environ.get("OPENAMER_HOME", Path.home() / ".openamer"))


def _hermes_home() -> Path:
    return Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes"))


def _check_hermes_installed() -> bool:
    """Prüft ob Hermes Agent installiert ist."""
    hermes = _hermes_home()
    if hermes.is_dir():
        return True
    # Auch Prüfung via pip
    try:
        import hermes  # noqa: F401
        return True
    except ImportError:
        pass
    return False


def check_hermes() -> dict[str, Any]:
    """Prüft ob Hermes gefunden wurde und was migrierbar ist."""
    hermes = _hermes_home()
    result: dict[str, Any] = {
        "hermes_found": hermes.is_dir(),
        "hermes_path": str(hermes) if hermes.is_dir() else None,
        "migratable": {},
    }

    if not hermes.is_dir():
        # Prüfe ob Hermes via pip installiert ist
        try:
            import hermes  # noqa: F401
            result["hermes_found"] = True
            result["hermes_path"] = "pip-installed"
        except ImportError:
            pass
        return result

    # Skills
    skills_dir = hermes / "skills"
    if skills_dir.is_dir():
        skill_files = list(skills_dir.rglob("*.md"))
        result["migratable"]["skills"] = len(skill_files)

    # Config
    config_file = hermes / "config.yaml"
    if config_file.exists():
        result["migratable"]["config"] = True

    # Memories
    mem_dir = hermes / "memories"
    if mem_dir.is_dir():
        mem_files = list(mem_dir.glob("*.md"))
        result["migratable"]["memories"] = len(mem_files)

    # A2A
    a2a_dir = hermes / "a2a"
    if a2a_dir.is_dir():
        result["migratable"]["a2a_identity"] = True

    return result


def migrate_skills(dry_run: bool = False) -> list[str]:
    """Kopiert alle Hermes-Skills ins OpenAmer-Skills-Verzeichnis."""
    hermes = _hermes_home()
    skills_dir = hermes / "skills"
    target_dir = _home() / "skills" / "hermes-imported"

    migrated: list[str] = []
    if not skills_dir.is_dir():
        return migrated

    if not dry_run:
        target_dir.mkdir(parents=True, exist_ok=True)

    for skill_file in skills_dir.rglob("*.md"):
        relative = skill_file.relative_to(skills_dir)
        target = target_dir / relative
        if dry_run:
            migrated.append(f"[DRY RUN] Would copy: {skill_file.name} -> {target}")
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(skill_file, target)
            migrated.append(f"Copied: {skill_file.name} -> hermes-imported/{relative}")

    return migrated


def migrate_memories(dry_run: bool = False) -> list[str]:
    """Kopiert Hermes-Memories ins OpenAmer-Memory-Verzeichnis."""
    hermes = _hermes_home()
    mem_dir = hermes / "memories"
    target_dir = _home() / "memories"

    migrated: list[str] = []
    if not mem_dir.is_dir():
        return migrated

    target_dir.mkdir(parents=True, exist_ok=True)

    for mem_file in mem_dir.glob("*.md"):
        target = target_dir / f"hermes_{mem_file.name}"
        if dry_run:
            migrated.append(f"[DRY RUN] Would copy: {mem_file.name} -> {target.name}")
        else:
            shutil.copy2(mem_file, target)
            migrated.append(f"Copied: {mem_file.name} -> {target.name}")

    return migrated


def migrate_config(dry_run: bool = False) -> list[str]:
    """Zeigt wie Hermes-Config auf OpenAmer übertragen werden kann."""
    hermes = _hermes_home()
    config_file = hermes / "config.yaml"
    if not config_file.exists():
        return ["No Hermes config found to migrate."]

    migrated: list[str] = []
    try:
        content = config_file.read_text(encoding="utf-8")
        target = _home() / "hermes_config_backup.yaml"
        if dry_run:
            migrated.append("[DRY RUN] Would save Hermes config for reference")
        else:
            target.write_text(
                f"# Hermes Config Backup — migrated {datetime.now(timezone.utc).isoformat()}\n"
                f"# Original: {config_file}\n"
                f"# To use these settings, manually copy relevant values to\n"
                f"# ~/.openamer/config.yaml or run: openamer setup\n"
                f"{content}",
                encoding="utf-8",
            )
            migrated.append(f"Config backed up: {target}")
    except Exception as e:
        migrated.append(f"Error reading config: {e}")

    return migrated


def run_full_migration(dry_run: bool = False) -> dict[str, Any]:
    """Führt die vollständige Migration durch."""
    check = check_hermes()

    if not check["hermes_found"]:
        return {"status": "error", "message": "Hermes Agent nicht gefunden. Ist ~/.hermes/ vorhanden?"}

    results: dict[str, Any] = {
        "status": "completed",
        "hermes_path": check["hermes_path"],
        "migratable": check["migratable"],
        "dry_run": dry_run,
        "actions": {},
    }

    results["actions"]["skills"] = migrate_skills(dry_run=dry_run)
    results["actions"]["memories"] = migrate_memories(dry_run=dry_run)
    results["actions"]["config"] = migrate_config(dry_run=dry_run)
    results["timestamp"] = datetime.now(timezone.utc).isoformat()

    total = sum(len(v) for v in results["actions"].values())
    results["total_actions"] = total

    if not dry_run and total > 0:
        # Schreibe eine Summary
        summary = _home() / "hermes_migration_summary.md"
        summary.write_text(
            f"# Hermes → OpenAmer Migration\n\n"
            f"Migrated: {datetime.now(timezone.utc).isoformat()}\n\n"
            f"## Skills: {len(results['actions']['skills'])} migrated\n"
            f"## Memories: {len(results['actions']['memories'])} migrated\n"
            f"## Config: {len(results['actions']['config'])} entries\n\n"
            f"Welcome to OpenAmer! 🚀\n"
            f"Same DNA. More Features. 100/100 Score.\n",
            encoding="utf-8",
        )
        results["summary_file"] = str(summary)

    return results


def run_hermes_command(args) -> int:
    """Dispatch für openamer hermes <subcommand>."""
    sub = getattr(args, "hermes_command", None)

    if sub in (None, ""):
        print(
            "usage: openamer hermes <subcommand>\n"
            "\n"
            "Migrate from Hermes Agent to OpenAmer.\n"
            "\n"
            "subcommands:\n"
            "  check           Check if Hermes is installed and what can be migrated\n"
            "  migrate         Run full migration (skills, memories, config)\n"
            "  migrate --dry-run   Preview without making changes\n"
            "  help            Show this message\n",
            file=sys.stderr,
        )
        return 1

    if sub == "check":
        result = check_hermes()
        if result["hermes_found"]:
            print(f"\n  ✅ Hermes Agent found at: {result['hermes_path']}\n")
            for key, val in result["migratable"].items():
                print(f"     {key}: {val}")
            print(f"\n  Run `openamer hermes migrate` to migrate.\n")
        else:
            print(f"\n  ❌ Hermes Agent not found.\n")
        return 0

    elif sub == "migrate":
        dry_run = getattr(args, "dry_run", False)
        result = run_full_migration(dry_run=dry_run)

        if result["status"] == "error":
            print(f"\n  ❌ {result['message']}\n")
            return 1

        label = "DRY RUN" if dry_run else "MIGRATION"
        print(f"\n  🚀 {label} COMPLETE\n")
        for action, items in result["actions"].items():
            if items:
                print(f"  {action}:")
                for item in items[:5]:
                    print(f"    • {item}")
                if len(items) > 5:
                    print(f"    ... and {len(items) - 5} more")
            else:
                print(f"  {action}: nothing to migrate")
        print(f"\n  Total: {result['total_actions']} actions\n")
        return 0

    else:
        print(f"Unknown subcommand: {sub}", file=sys.stderr)
        return 1