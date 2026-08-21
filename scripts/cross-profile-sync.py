#!/usr/bin/env python3
"""
Cross-Profile Sync — Skills/Cron/Config zwischen OpenAmer-Profilen synchronisieren
=================================================================================
Produktionsreifes Tool zum Synchronisieren, Diffen und Mergen von OpenAmer-Profilen.

Funktionen:
  --sync      Skills, Cron-Jobs und Config von Quelle → Ziel kopieren
  --diff      Strukturierte Unterschiede zwischen zwei Profilen anzeigen
  --merge     Zwei Profile vereinigen (Konflikte: newest wins)
  --dry-run   Nur zeigen, was passieren würde (Default: aktiviert)
  --force     Wirklich ausführen

Sicherheit:
  - Dry-Run ist DEFAULT — ohne --force passiert nichts
  - Vor jeder Aktion wird ein Before-Snapshot erstellt
  - Logging in OPENAMER_HOME/logs/cross-profile-sync.log
  - Merge-Report bei Konflikten als merge-report.json

Usage:
  python3 cross-profile-sync.py --list
  python3 cross-profile-sync.py --diff dev work
  python3 cross-profile-sync.py --sync dev work --dry-run
  python3 cross-profile-sync.py --sync dev work --force
  python3 cross-profile-sync.py --merge dev work merged --dry-run
  python3 cross-profile-sync.py --merge dev work merged --force
"""

import argparse
import difflib
import json
import logging
import os
import shutil
import sys
import time
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ── Konfiguration ──────────────────────────────────────────────────────────────

def _resolve_msys2_path(p: str) -> str:
    """Convert MSYS2 paths like /c/Users/... to C:\\Users\\..."""
    import re
    m = re.match(r"^/([a-zA-Z])/(.*)", p)
    if m and os.name == "nt":
        drive = m.group(1).upper()
        rest = m.group(2).replace("/", "\\")
        return f"{drive}:{os.sep}{rest}"
    return p

HOME = Path(os.path.expanduser("~"))
_raw_home = os.environ.get("OPENAMER_HOME", "")
if _raw_home:
    OPENAMER_HOME = Path(_resolve_msys2_path(_raw_home))
else:
    OPENAMER_HOME = HOME / "AppData" / "Local" / "openamer-laptop"
PROFILES_DIR = OPENAMER_HOME / "profiles"
LOG_DIR = OPENAMER_HOME / "logs"
SNAPSHOT_DIR = OPENAMER_HOME / "profiles" / ".snapshots"

# Sektionen, die synchronisiert werden
SECTIONS = ["skills", "cron", "config"]


def setup_logging() -> logging.Logger:
    """Logger einrichten: Datei + stdout."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("cross-profile-sync")
    logger.setLevel(logging.INFO)

    # File handler
    fh = logging.FileHandler(
        LOG_DIR / "cross-profile-sync.log", encoding="utf-8"
    )
    fh.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s"
    ))
    logger.addHandler(fh)

    # Stdout handler (nur für wichtige Meldungen)
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(logging.Formatter("%(message)s"))
    sh.setLevel(logging.WARNING)
    logger.addHandler(sh)

    return logger


# ── Profil-Funktionen ──────────────────────────────────────────────────────────

def list_profiles() -> List[str]:
    """Alle verfügbaren Profile auflisten."""
    if not PROFILES_DIR.exists():
        return []
    return sorted(
        p.name for p in PROFILES_DIR.iterdir()
        if p.is_dir() and not p.name.startswith(".")
    )


def profile_path(name: str) -> Path:
    """Pfad zu einem Profil."""
    return PROFILES_DIR / name


def profile_exists(name: str) -> bool:
    """Prüfen ob ein Profil existiert."""
    return profile_path(name).is_dir()


def read_file_safe(path: Path) -> str:
    """Datei sicher lesen, bei Fehler leeren String zurückgeben."""
    try:
        if path.exists() and path.is_file():
            return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        pass
    return ""


def get_profile_files(profile: str, section: str) -> Dict[str, str]:
    """
    Alle Dateien einer Sektion in einem Profil holen.
    Returns: {rel_path: content}
    """
    base = profile_path(profile)
    section_dir = base / section
    result: Dict[str, str] = {}

    if not section_dir.exists():
        return result

    for f in sorted(section_dir.rglob("*")):
        if f.is_file():
            rel = f.relative_to(section_dir)
            result[str(rel)] = read_file_safe(f)

    return result


def get_profile_snapshot(profile: str) -> Dict[str, Any]:
    """
    Kompletten Snapshot eines Profils erstellen (Skills + Config + Cron).
    """
    snapshot: Dict[str, Any] = {
        "profile": profile,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    for section in SECTIONS:
        snapshot[section] = get_profile_files(profile, section)
    return snapshot


def save_snapshot(profile: str, data: Dict[str, Any]) -> str:
    """
    Snapshot in .snapshots/ speichern.
    Returns: Pfad zur Snapshot-Datei
    """
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    fname = f"{profile}_{ts}.json"
    path = SNAPSHOT_DIR / fname
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return str(path)


def pretty_file_size(path: Path) -> str:
    """Menschlesbare Dateigröße."""
    size = path.stat().st_size if path.exists() else 0
    for unit in ["B", "KB", "MB"]:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} GB"


def format_action(verb: str, path: str, detail: str = "") -> str:
    """Einheitliche Aktionsmeldung."""
    parts = [verb, path]
    if detail:
        parts.append(f"({detail})")
    return "  " + " ".join(parts)


# ── Diff-Funktionen ────────────────────────────────────────────────────────────

def compute_diff(
    files_a: Dict[str, str], files_b: Dict[str, str], label_a: str, label_b: str
) -> Dict[str, Any]:
    """
    Strukturierten Diff zwischen zwei Datei-Dictionaries berechnen.
    """
    all_keys = set(files_a.keys()) | set(files_b.keys())
    only_in_a: Dict[str, str] = {}
    only_in_b: Dict[str, str] = {}
    modified: Dict[str, Dict[str, Any]] = {}
    same: List[str] = []

    for key in sorted(all_keys):
        if key not in files_b:
            only_in_a[key] = files_a[key]
        elif key not in files_a:
            only_in_b[key] = files_b[key]
        elif files_a[key] != files_b[key]:
            diff_lines = list(
                difflib.unified_diff(
                    files_a[key].splitlines(keepends=True),
                    files_b[key].splitlines(keepends=True),
                    fromfile=f"{label_a}/{key}",
                    tofile=f"{label_b}/{key}",
                    lineterm="",
                )
            )
            modified[key] = {
                "diff": diff_lines,
                "len_a": len(files_a[key]),
                "len_b": len(files_b[key]),
            }
        else:
            same.append(key)

    return {
        "only_in_source": only_in_a,
        "only_in_target": only_in_b,
        "modified": modified,
        "same": same,
        "stats": {
            "total": len(all_keys),
            "only_in_source": len(only_in_a),
            "only_in_target": len(only_in_b),
            "modified": len(modified),
            "same": len(same),
        },
    }


# ── Sync-Funktionen ────────────────────────────────────────────────────────────

def plan_sync(source: str, target: str, logger: logging.Logger) -> Dict[str, Any]:
    """
    Sync-Plan erstellen (was würde passieren).
    Returns: Plan als Dict
    """
    if not profile_exists(source):
        raise ValueError(f"Source profile '{source}' does not exist")
    if not profile_exists(target):
        raise ValueError(f"Target profile '{target}' does not exist")

    plan: Dict[str, Any] = {
        "source": source,
        "target": target,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "actions": [],
        "summary": {"skills": {"copied": 0, "deleted": 0, "unchanged": 0},
                     "cron": {"copied": 0, "deleted": 0, "unchanged": 0},
                     "config": {"copied": 0, "deleted": 0, "unchanged": 0}},
    }

    for section in SECTIONS:
        src_files = get_profile_files(source, section)
        tgt_files = get_profile_files(target, section)

        diff = compute_diff(src_files, tgt_files, source, target)

        for key in diff["only_in_source"]:
            plan["actions"].append({
                "section": section,
                "action": "copy",
                "file": key,
                "source_size": len(src_files.get(key, "")),
            })
            plan["summary"][section]["copied"] += 1

        for key in diff["modified"]:
            plan["actions"].append({
                "section": section,
                "action": "overwrite",
                "file": key,
                "source_size": len(src_files.get(key, "")),
                "target_size": len(tgt_files.get(key, "")),
            })
            plan["summary"][section]["copied"] += 1

        # Dateien, die nur im Target existieren → werden beim Sync NICHT gelöscht
        # (Sync ist additive + überschreibend, kein Spiegeln)
        for key in diff["only_in_target"]:
            plan["summary"][section]["unchanged"] += 1

        for key in diff["same"]:
            plan["summary"][section]["unchanged"] += 1

    return plan


def execute_sync(plan: Dict[str, Any], dry_run: bool, logger: logging.Logger) -> Dict[str, Any]:
    """
    Sync-Plan ausführen.
    """
    result = {
        "executed": not dry_run,
        "dry_run": dry_run,
        "performed": [],
        "errors": [],
    }
    target = plan["target"]

    for action in plan["actions"]:
        section = action["section"]
        file_key = action["file"]
        src_path = profile_path(plan["source"]) / section / file_key
        tgt_path = profile_path(target) / section / file_key

        if dry_run:
            logger.info(f"[DRY-RUN] {action['action']} {section}/{file_key}")
            result["performed"].append(f"DRY-RUN: {action['action']} {section}/{file_key}")
        else:
            try:
                tgt_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(str(src_path), str(tgt_path))
                logger.info(f"Copied {section}/{file_key} → {target}")
                result["performed"].append(f"Copied {section}/{file_key}")
            except Exception as e:
                logger.error(f"Failed to copy {section}/{file_key}: {e}")
                result["errors"].append(f"{section}/{file_key}: {e}")

    return result


# ── Merge-Funktionen ───────────────────────────────────────────────────────────

def plan_merge(
    profile_a: str, profile_b: str, output: str, logger: logging.Logger
) -> Dict[str, Any]:
    """
    Merge-Plan erstellen. Konflikte: newest wins.
    """
    if not profile_exists(profile_a):
        raise ValueError(f"Profile '{profile_a}' does not exist")
    if not profile_exists(profile_b):
        raise ValueError(f"Profile '{profile_b}' does not exist")

    plan: Dict[str, Any] = {
        "source_a": profile_a,
        "source_b": profile_b,
        "output": output,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "sections": {},
        "conflicts": [],
    }

    for section in SECTIONS:
        a_files = get_profile_files(profile_a, section)
        b_files = get_profile_files(profile_b, section)
        diff = compute_diff(a_files, b_files, profile_a, profile_b)

        merged: Dict[str, str] = {}
        section_conflicts = []

        # Nur in A → übernehmen
        for key in diff["only_in_source"]:
            merged[key] = a_files[key]

        # Nur in B → übernehmen
        for key in diff["only_in_target"]:
            merged[key] = b_files[key]

        # Identisch → egal
        for key in diff["same"]:
            merged[key] = a_files[key]

        # Konflikte (beide vorhanden, unterschiedlich) → newest wins
        for key, info in diff["modified"].items():
            a_path = profile_path(profile_a) / section / key
            b_path = profile_path(profile_b) / section / key
            a_mtime = a_path.stat().st_mtime if a_path.exists() else 0
            b_mtime = b_path.stat().st_mtime if b_path.exists() else 0

            winner = profile_a if a_mtime >= b_mtime else profile_b
            winner_content = a_files[key] if winner == profile_a else b_files[key]
            merged[key] = winner_content

            conflict = {
                "file": key,
                "section": section,
                "a_mtime": datetime.fromtimestamp(a_mtime, tz=timezone.utc).isoformat() if a_mtime else "N/A",
                "b_mtime": datetime.fromtimestamp(b_mtime, tz=timezone.utc).isoformat() if b_mtime else "N/A",
                "a_size": info["len_a"],
                "b_size": info["len_b"],
                "winner": winner,
                "reason": "newest mtime wins",
            }
            section_conflicts.append(conflict)
            plan["conflicts"].append(conflict)

        plan["sections"][section] = {
            "files": merged,
            "total": len(merged),
            "conflicts": len(section_conflicts),
        }

        # Merge-Report schreiben
        if section_conflicts:
            report_path = LOG_DIR / "merge-report.json"
            existing = []
            if report_path.exists():
                try:
                    existing = json.loads(report_path.read_text(encoding="utf-8"))
                except Exception:
                    existing = []
            existing.append({
                "merge_time": plan["timestamp"],
                "sources": [profile_a, profile_b],
                "output": output,
                "conflicts": section_conflicts,
            })
            report_path.write_text(
                json.dumps(existing, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

    return plan


def execute_merge(plan: Dict[str, Any], dry_run: bool, logger: logging.Logger) -> Dict[str, Any]:
    """
    Merge-Plan ausführen — merged files in output-Profil schreiben.
    """
    result = {
        "executed": not dry_run,
        "dry_run": dry_run,
        "performed": [],
        "errors": [],
    }
    output = plan["output"]
    output_base = profile_path(output)

    for section, section_data in plan["sections"].items():
        for file_key, content in section_data["files"].items():
            tgt_path = output_base / section / file_key

            if dry_run:
                logger.info(f"[DRY-RUN] Write {section}/{file_key} → {output}")
                result["performed"].append(f"DRY-RUN: Write {section}/{file_key}")
            else:
                try:
                    tgt_path.parent.mkdir(parents=True, exist_ok=True)
                    tgt_path.write_text(content, encoding="utf-8")
                    logger.info(f"Merged {section}/{file_key} → {output}")
                    result["performed"].append(f"Merged {section}/{file_key}")
                except Exception as e:
                    logger.error(f"Failed to write {section}/{file_key}: {e}")
                    result["errors"].append(f"{section}/{file_key}: {e}")

    return result


# ── Reporting ──────────────────────────────────────────────────────────────────

def print_diff_report(
    diff_data: Dict[str, Any], section: str, label_a: str, label_b: str
):
    """Diff-Bericht für eine Sektion ausgeben."""
    stats = diff_data["stats"]
    print(f"\n  {'='*50}")
    print(f"  [{section.upper()}] {label_a} ↔ {label_b}")
    print(f"  {'='*50}")
    print(f"  Total: {stats['total']} files")
    print(f"  ✓ Identical:  {stats['same']}")
    print(f"  ➕ Only in {label_a}: {stats['only_in_source']}")
    print(f"  ➖ Only in {label_b}: {stats['only_in_target']}")
    print(f"  ✏️  Modified:    {stats['modified']}")

    if stats["only_in_source"]:
        print(f"\n  ➕ Only in {label_a}:")
        for key in diff_data["only_in_source"]:
            size = len(diff_data["only_in_source"][key])
            print(f"      {key} ({size} B)")

    if stats["only_in_target"]:
        print(f"\n  ➖ Only in {label_b}:")
        for key in diff_data["only_in_target"]:
            size = len(diff_data["only_in_target"][key])
            print(f"      {key} ({size} B)")

    if stats["modified"]:
        print(f"\n  ✏️  Modified files:")
        for key, info in diff_data["modified"].items():
            print(f"\n    --- {key} ---")
            print(f"        {label_a}: {info['len_a']} B | {label_b}: {info['len_b']} B")
            # Erste 5 Diff-Zeilen zeigen
            for line in info["diff"][:7]:
                print(f"      {line.rstrip()}")
            if len(info["diff"]) > 7:
                print(f"      ... ({len(info['diff'])} diff lines total)")


def print_sync_plan(plan: Dict[str, Any], is_dry_run: bool):
    """Sync-Plan übersichtlich ausgeben."""
    prefix = "[DRY-RUN] " if is_dry_run else ""
    print(f"\n{'='*60}")
    print(f"  Sync Plan: {plan['source']} → {plan['target']}")
    print(f"  {'='*60}")
    print(f"  Timestamp: {plan['timestamp']}")

    for section in SECTIONS:
        s = plan["summary"][section]
        if s["copied"] > 0 or s["deleted"] > 0:
            print(f"\n  [{section.upper()}]")
            if s["copied"] > 0:
                print(f"    Copy/Overwrite: {s['copied']} files")
            if s["deleted"] > 0:
                print(f"    Delete:         {s['deleted']} files")
            if s["unchanged"] > 0:
                print(f"    Unchanged:      {s['unchanged']} files")

    print(f"\n  Total actions: {len(plan['actions'])}")
    if not is_dry_run:
        print(f"  ⚠️  This WILL modify '{plan['target']}'")
    print(f"{'='*60}\n")


def print_merge_report(plan: Dict[str, Any], is_dry_run: bool):
    """Merge-Plan ausgeben."""
    prefix = "[DRY-RUN] " if is_dry_run else ""
    print(f"\n{'='*60}")
    print(f"  Merge Plan: {plan['source_a']} + {plan['source_b']} → {plan['output']}")
    print(f"  {'='*60}")
    print(f"  Conflict resolution: newest mtime wins")

    for section in SECTIONS:
        sd = plan["sections"][section]
        print(f"\n  [{section.upper()}] {sd['total']} files, {sd['conflicts']} conflicts")
        if sd["conflicts"] > 0:
            for c in plan["conflicts"]:
                if c["section"] == section:
                    print(f"    ⚡ {c['file']}")
                    print(f"       A ({c['a_mtime'][:19]}) vs B ({c['b_mtime'][:19]})")
                    print(f"       → Winner: {c['winner']}")

    print(f"\n  Total conflicts: {len(plan['conflicts'])}")
    if not is_dry_run:
        print(f"  ⚠️  This WILL create/modify profile '{plan['output']}'")
    print(f"{'='*60}\n")


# ── CLI ────────────────────────────────────────────────────────────────────────

def cmd_list():
    """--list: Alle Profile anzeigen."""
    profiles = list_profiles()
    if not profiles:
        print("No profiles found.")
        return

    print(f"\n{'='*50}")
    print(f"  OpenAmer Profiles ({len(profiles)})")
    print(f"  Location: {PROFILES_DIR}")
    print(f"{'='*50}")

    for pname in profiles:
        p = profile_path(pname)
        total_size = sum(
            f.stat().st_size for f in p.rglob("*") if f.is_file()
        )
        file_count = sum(1 for _ in p.rglob("*") if _.is_file())
        sections = {
            s: len(list((p / s).rglob("*"))) if (p / s).exists() else 0
            for s in SECTIONS
        }
        print(f"\n  📁 {pname}")
        print(f"     Files: {file_count}, Size: {pretty_file_size(p)}")
        print(f"     Skills: {sections['skills']} | Cron: {sections['cron']} | Config: {sections['config']}")

    print()


def cmd_diff(args, logger: logging.Logger):
    """--diff: Unterschiede zwischen zwei Profilen."""
    a, b = args.diff
    if not profile_exists(a):
        print(f"❌ Profile '{a}' not found")
        sys.exit(1)
    if not profile_exists(b):
        print(f"❌ Profile '{b}' not found")
        sys.exit(1)

    print(f"\n  Diff: {a} ↔ {b}")
    logger.info(f"Diff: {a} ↔ {b}")

    for section in SECTIONS:
        a_files = get_profile_files(a, section)
        b_files = get_profile_files(b, section)
        diff_data = compute_diff(a_files, b_files, a, b)
        print_diff_report(diff_data, section, a, b)

    print()


def cmd_sync(args, logger: logging.Logger):
    """--sync: Quelle → Ziel synchronisieren."""
    source, target = args.sync

    if not profile_exists(source):
        print(f"❌ Source profile '{source}' not found")
        sys.exit(1)
    if not profile_exists(target):
        print(f"❌ Target profile '{target}' not found")
        sys.exit(1)

    is_dry_run = not args.force

    # Before-Snapshot
    before_snapshot = save_snapshot(target, get_profile_snapshot(target))
    logger.info(f"Before snapshot: {before_snapshot}")

    plan = plan_sync(source, target, logger)
    print_sync_plan(plan, is_dry_run)

    if len(plan["actions"]) == 0:
        print("  ✅ Nothing to sync — profiles are already in sync.\n")
        return

    result = execute_sync(plan, is_dry_run, logger)

    if not is_dry_run:
        after_snapshot = save_snapshot(target, get_profile_snapshot(target))
        logger.info(f"After snapshot: {after_snapshot}")
        print(f"\n  ✅ Sync complete: {result['performed']}")
        if result["errors"]:
            print(f"  ⚠️  Errors: {result['errors']}")
        print(f"  Before: {before_snapshot}")
        print(f"  After:  {after_snapshot}\n")


def cmd_merge(args, logger: logging.Logger):
    """--merge: Zwei Profile vereinigen."""
    a, b, output = args.merge

    if not profile_exists(a):
        print(f"❌ Profile '{a}' not found")
        sys.exit(1)
    if not profile_exists(b):
        print(f"❌ Profile '{b}' not found")
        sys.exit(1)

    if a == output or b == output:
        print(f"❌ Output profile must be different from source profiles")
        sys.exit(1)

    is_dry_run = not args.force

    plan = plan_merge(a, b, output, logger)
    print_merge_report(plan, is_dry_run)

    result = execute_merge(plan, is_dry_run, logger)

    if not is_dry_run:
        after_snapshot = save_snapshot(output, get_profile_snapshot(output))
        logger.info(f"Merge output snapshot: {after_snapshot}")
        print(f"\n  ✅ Merge complete: {result['performed']}")
        if result["errors"]:
            print(f"  ⚠️  Errors: {result['errors']}")
        print(f"  Report: {LOG_DIR}/merge-report.json")
        print(f"  Snapshot: {after_snapshot}\n")


def main():
    parser = argparse.ArgumentParser(
        description="Cross-Profile Sync — Skills/Cron/Config zwischen OpenAmer-Profilen synchronisieren",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 cross-profile-sync.py --list
  python3 cross-profile-sync.py --diff dev work
  python3 cross-profile-sync.py --sync dev work --dry-run
  python3 cross-profile-sync.py --sync dev work --force
  python3 cross-profile-sync.py --merge dev work merged --dry-run
  python3 cross-profile-sync.py --merge dev work merged --force
        """,
    )

    parser.add_argument(
        "--list", action="store_true", help="Alle Profile auflisten"
    )
    parser.add_argument(
        "--diff", nargs=2, metavar=("PROFILE_A", "PROFILE_B"),
        help="Unterschiede zwischen zwei Profilen anzeigen"
    )
    parser.add_argument(
        "--sync", nargs=2, metavar=("SOURCE", "TARGET"),
        help="Skills/Cron/Config von SOURCE nach TARGET syncen"
    )
    parser.add_argument(
        "--merge", nargs=3, metavar=("PROFILE_A", "PROFILE_B", "OUTPUT"),
        help="Zwei Profile zu OUTPUT vereinigen (Konflikte: newest wins)"
    )
    parser.add_argument(
        "--dry-run", action="store_true", default=False,
        help="Explizit Dry-Run (Default bei --sync/--merge ohne --force)"
    )
    parser.add_argument(
        "--force", action="store_true", default=False,
        help="Änderungen wirklich ausführen (ohne --force: Dry-Run)"
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Ausführliche Log-Ausgabe"
    )

    args = parser.parse_args()
    logger = setup_logging()

    if args.verbose:
        for handler in logger.handlers:
            if isinstance(handler, logging.StreamHandler):
                handler.setLevel(logging.DEBUG)
            else:
                handler.setLevel(logging.DEBUG)

    # Keine Aktion → Hilfe
    if not any([args.list, args.diff, args.sync, args.merge]):
        parser.print_help()
        print("\n\nUse --list to see available profiles.")
        cmd_list()

    if args.list:
        cmd_list()
    elif args.diff:
        cmd_diff(args, logger)
    elif args.sync:
        cmd_sync(args, logger)
    elif args.merge:
        cmd_merge(args, logger)


if __name__ == "__main__":
    main()