#!/usr/bin/env python3
"""
KI-gesteuerter Auto-Test-Runner: Git-Change-basierte Test-Priorisierung,
parallele Ausführung, Failure-History-Verfolgung.

Analysiert den letzten Git-Diff, identifiziert abhängige Testfiles,
priorisiert sie (geänderte Dateien + historische Fehlschläge → höchste Prio),
führt max 3 parallel aus und schreibt eine Failure-History in
``.auto-test-runner/history.json``.

Syntax:
    python scripts/auto-test-runner.py [--diff-ref REF] [--max-workers N] [--file-timeout SEC]

Output (JSON, stdout):
{
    "prioritized_tests": [[prio_score, test_file, "reason"], ...],
    "failures": [test_file, ...],
    "duration": 12.34,
    "total_tests": 42,
    "passed": 40,
    "failed": 2,
    "new_failures": [...] | null,
    "history_summary": {"total_entries": ..., "known_failures": ...}
}
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ── Consts ──────────────────────────────────────────────────────────────────

REPO_ROOT = Path(__file__).resolve().parent.parent
HISTORY_DIR = REPO_ROOT / ".auto-test-runner"
HISTORY_FILE = HISTORY_DIR / "history.json"
DEFAULT_DIFF_REF = "HEAD~1"  # letzter Commit; "--diff-ref HEAD" für uncommitted
DEFAULT_MAX_WORKERS = 3
DEFAULT_FILE_TIMEOUT = 300.0

# Mapping: Quellmodule → Testverzeichnis
# Erweiterbar durch Einträge in ``.auto-test-runner/module_map.json``
SOURCE_TO_TEST_MAP: dict[str, str] = {
    "cli.py":                    "tests/openamer_cli",
    "run_agent.py":              "tests/run_agent",
    "openamer_state.py":         "tests/openamer_state",
    "model_tools.py":            "tests/openamer_cli",
    "trajectory_compressor.py":  "tests/openamer_cli",
    "utils.py":                  "tests/openamer_cli",
    "openamer_constants.py":     "tests/openamer_cli",
    "openamer_logging.py":       "tests/openamer_cli",
    "toolsets.py":               "tests/openamer_cli",
    "toolset_distributions.py":  "tests/openamer_cli",
    "openamer_bootstrap.py":     "tests/openamer_cli",
    "mcp_serve.py":              "tests/openamer_cli",
    "batch_runner.py":           "tests/openamer_cli",

    # Plugins & Cron
    "plugins/":                  "tests/plugins",
    "cron/":                     "tests/cron",

    # Agent & ACP
    "agent/":                    "tests/agent",
    "acp_adapter/":              "tests/acp_adapter",
    "acp/":                      "tests/acp",

    # Gateway
    "gateway/":                  "tests/gateway",

    # Provider
    "providers/":                "tests/providers",

    # Skills
    "skills/":                   "tests/skills",
}

# Directories whose tests are ALWAYS included (low-prio baseline)
_ALWAYS_TEST_DIRS = [
    "tests/openamer_cli",
    "tests/run_agent",
]


# ── History ─────────────────────────────────────────────────────────────────

def _load_history() -> dict[str, Any]:
    """Lade .auto-test-runner/history.json oder gib Default-Struktur."""
    if HISTORY_FILE.exists():
        try:
            data = json.loads(HISTORY_FILE.read_text("utf-8"))
            if isinstance(data, dict) and "failures" in data:
                return data
        except (json.JSONDecodeError, OSError):
            pass
    return {
        "failures": {},       # {test_file_rel: {count, first_seen, last_seen, last_output}}
        "runs": [],           # Liste vergangener Run-Summaries
        "version": 2,
    }


def _save_history(history: dict[str, Any]) -> None:
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    tmp = HISTORY_FILE.with_suffix(".tmp")
    tmp.write_text(
        json.dumps(history, indent=2, default=str, ensure_ascii=False),
        "utf-8",
    )
    tmp.replace(HISTORY_FILE)


def _update_history(
    history: dict[str, Any],
    results: dict[Path, Tuple[bool, str]],  # test_file → (passed/True, output)
    duration: float,
) -> dict[str, Any]:
    """Failures eintragen/aktualisieren, alten Run loggen."""
    now = datetime.now(timezone.utc).isoformat()
    failures = history.setdefault("failures", {})
    run_entry: dict[str, Any] = {
        "timestamp": now,
        "duration": duration,
        "files": {},
    }

    for test_file, (passed, output) in results.items():
        rel = str(test_file.relative_to(REPO_ROOT).as_posix())
        run_entry["files"][rel] = "PASS" if passed else "FAIL"
        if not passed:
            if rel not in failures:
                failures[rel] = {
                    "count": 0,
                    "first_seen": now,
                    "last_output": "",
                }
            failures[rel]["count"] += 1
            failures[rel]["last_seen"] = now
            failures[rel]["last_output"] = output[-500:] if len(output) > 500 else output
        else:
            # Erfolgreich → Zähler zurücksetzen, Eintrag aber behalten (Statistik)
            if rel in failures:
                # Nur löschen wenn es beim letzten Mal auch geklappt hat → "geheilt"
                if failures[rel].get("count", 0) > 0:
                    failures[rel]["count"] = max(0, failures[rel]["count"] - 1)
                    failures[rel]["fixed_at"] = now
                    if failures[rel]["count"] == 0:
                        del failures[rel]

    history.setdefault("runs", []).append(run_entry)
    # Runs auf 50 begrenzen
    if len(history["runs"]) > 50:
        history["runs"] = history["runs"][-50:]
    return history


# ── Git-Diff Analyse ────────────────────────────────────────────────────────

def _get_changed_files(diff_ref: str) -> list[str]:
    """Ermittle via git diff die geänderten Dateien seit diff_ref."""
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", diff_ref],
            capture_output=True, text=True, timeout=30,
            cwd=REPO_ROOT,
        )
        if result.returncode != 0:
            print(f"⚠ git diff fehlgeschlagen: {result.stderr.strip()}", file=sys.stderr)
            return []
        files = [f.strip() for f in result.stdout.splitlines() if f.strip()]
        return files
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        print(f"⚠ git diff Fehler: {e}", file=sys.stderr)
        return []


def _get_staged_or_uncommitted() -> list[str]:
    """Ermittle uncommitted + staged Änderungen (für --diff-ref HEAD)."""
    files: set[str] = set()
    try:
        # Unstaged
        r = subprocess.run(
            ["git", "diff", "--name-only"],
            capture_output=True, text=True, timeout=30, cwd=REPO_ROOT,
        )
        if r.returncode == 0:
            files.update(f.strip() for f in r.stdout.splitlines() if f.strip())
        # Staged
        r = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            capture_output=True, text=True, timeout=30, cwd=REPO_ROOT,
        )
        if r.returncode == 0:
            files.update(f.strip() for f in r.stdout.splitlines() if f.strip())
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return sorted(files)


def _map_to_tests(changed_files: list[str]) -> dict[str, list[str]]:
    """Bilde geänderte Dateien auf Testverzeichnisse ab.

    Returns {test_dir: [changed_source_file, ...]}
    """
    mapping: dict[str, list[str]] = {}

    for cf in changed_files:
        cf_posix = cf.replace("\\", "/")
        matched = False

        # Explizites Mapping
        for src_pattern, test_dir in SOURCE_TO_TEST_MAP.items():
            if cf_posix.startswith(src_pattern) or cf_posix == src_pattern:
                mapping.setdefault(test_dir, []).append(cf)
                matched = True
                break

        # Fallback: Test-Dateien selbst geändert
        if not matched and cf_posix.startswith("tests/"):
            # Direkt geänderte Test-Datei → das Elter + ggf. abhängige
            parent = str(Path(cf_posix).parent)
            mapping.setdefault(parent, []).append(cf)

        # Python source in unbekanntem Verzeichnis → openamer_cli baseline
        if not matched and cf_posix.endswith(".py") and not cf_posix.startswith("tests/"):
            mapping.setdefault("tests/openamer_cli", []).append(cf)

    return mapping


# ── Test-Discovery ──────────────────────────────────────────────────────────

def _discover_tests_in_dir(test_dir: str) -> list[Path]:
    """Finde alle test_*.py unter einem Verzeichnis."""
    full = REPO_ROOT / test_dir
    if not full.is_dir():
        return []
    return sorted(full.rglob("test_*.py"))


def _compute_priority(
    test_file: Path,
    changed_sources: list[str],
    history: dict[str, Any],
) -> Tuple[float, str]:
    """Berechne Prioritäts-Score (höher = wichtiger) und Grund.

    Faktoren:
      +10  Direkt geänderte Test-Datei
      +5   Quelle geändert, die in SOURCE_TO_TEST_MAP gematched ist
      +3   Historically gefailed (≥2 mal)
      +1   Historically gefailed (1 mal)
      +1   Baseline (immer testen)
    """
    rel = str(test_file.relative_to(REPO_ROOT).as_posix())
    score = 0.0
    reasons: list[str] = []

    # 1) Direkt geändert?
    for src in changed_sources:
        if src.replace("\\", "/") == rel:
            score += 10
            reasons.append("DIRECT_CHANGE")
            break

    # 2) Source-Match
    for src in changed_sources:
        src_posix = src.replace("\\", "/")
        for src_pattern, test_dir in SOURCE_TO_TEST_MAP.items():
            if src_posix.startswith(src_pattern) or src_posix == src_pattern:
                if rel.startswith(test_dir):
                    score += 5
                    reasons.append(f"CHANGED:{src}")
                    break

    # 3) Failure-History
    failures = history.get("failures", {})
    if rel in failures:
        fcount = failures[rel].get("count", 0)
        if fcount >= 2:
            score += 3
            reasons.append(f"HIST_FAILURE(x{fcount})")
        elif fcount >= 1:
            score += 1
            reasons.append(f"HIST_FAILURE(x{fcount})")

    # 4) Baseline
    for base_dir in _ALWAYS_TEST_DIRS:
        if rel.startswith(base_dir + "/"):
            score += 1
            reasons.append("BASELINE")
            break

    return score, ";".join(reasons) if reasons else "AUTO"


# ── Test Execution ──────────────────────────────────────────────────────────

def _run_single_test(
    test_file: Path,
    file_timeout: float,
) -> Tuple[Path, bool, str]:
    """Führe pytest für eine einzelne Datei aus. Gibt (file, passed, output)."""
    cmd = [
        sys.executable, "-m", "pytest",
        str(test_file),
        "-q",                          # quiet
        "--tb=short",                  # short traceback
        "--no-header",
        "--no-summary",
        "-p", "no:cacheprovider",      # keine __pycache__-Konflikte
    ]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True, text=True,
            timeout=file_timeout,
            cwd=REPO_ROOT,
        )
        passed = result.returncode == 0
        output = result.stdout + result.stderr
        if not output.strip():
            output = f"(exit code {result.returncode}, no output)"
        return test_file, passed, output
    except subprocess.TimeoutExpired:
        return test_file, False, f"TIMEOUT after {file_timeout}s"
    except FileNotFoundError:
        return test_file, False, f"pytest not found: {sys.executable} -m pytest"
    except Exception as e:
        return test_file, False, str(e)


def _run_prioritized_tests(
    prioritized: list[Tuple[float, Path, str]],
    max_workers: int,
    file_timeout: float,
) -> dict[Path, Tuple[bool, str]]:
    """Führe Tests parallel aus, max_workers gleichzeitig."""
    results: dict[Path, Tuple[bool, str]] = {}
    # Nach Prio sortieren (höchste zuerst)
    sorted_tests = sorted(prioritized, key=lambda x: -x[0])

    print(f"▶ Starte {len(sorted_tests)} Tests mit max {max_workers} parallel", file=sys.stderr)

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        fut_map = {
            pool.submit(_run_single_test, path, file_timeout): path
            for _, path, _ in sorted_tests
        }
        for fut in as_completed(fut_map):
            path = fut_map[fut]
            try:
                fpath, passed, output = fut.result()
                label = "✓" if passed else "✗"
                print(f"  {label} {path.relative_to(REPO_ROOT)}", file=sys.stderr)
                results[path] = (passed, output)
            except Exception as e:
                print(f"  ⚠ {path.relative_to(REPO_ROOT)} — {e}", file=sys.stderr)
                results[path] = (False, str(e))

    return results


# ── Main ────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Auto-Test-Runner: Git-Change-basierte Test-Priorisierung",
    )
    parser.add_argument(
        "--diff-ref", default=DEFAULT_DIFF_REF,
        help="Git-Ref für diff (default: HEAD~1). 'HEAD' = uncommitted+staged",
    )
    parser.add_argument(
        "--max-workers", type=int, default=DEFAULT_MAX_WORKERS,
        help=f"Maximale parallele Testprozesse (default: {DEFAULT_MAX_WORKERS})",
    )
    parser.add_argument(
        "--file-timeout", type=float, default=DEFAULT_FILE_TIMEOUT,
        help=f"Timeout pro Test-Datei in Sekunden (default: {DEFAULT_FILE_TIMEOUT})",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Nur analysieren, keine Tests ausführen",
    )
    parser.add_argument(
        "--json", action="store_true", default=True,
        help="JSON-Output (default: True)",
    )
    args = parser.parse_args()

    start_time = time.time()

    # ── 1) Git-Änderungen analysieren ───────────────────────────────────────
    print("📂 Analysiere Git-Änderungen...", file=sys.stderr)

    if args.diff_ref == "HEAD":
        changed_files = _get_staged_or_uncommitted()
    else:
        changed_files = _get_changed_files(args.diff_ref)

    if not changed_files:
        print("ℹ Keine Änderungen seit {}. Führe Baseline-Tests aus.".format(
            args.diff_ref
        ), file=sys.stderr)
        # Baseline: alle _ALWAYS_TEST_DIRS
        test_mapping: dict[str, list[str]] = {
            d: ["(no changes)"] for d in _ALWAYS_TEST_DIRS
        }
    else:
        print(f"  Geänderte Dateien ({len(changed_files)}):", file=sys.stderr)
        for cf in changed_files:
            print(f"    • {cf}", file=sys.stderr)
        test_mapping = _map_to_tests(changed_files)

    print(f"  Betroffene Test-Verzeichnisse: {list(test_mapping.keys())}", file=sys.stderr)

    # ── 2) History laden ────────────────────────────────────────────────────
    history = _load_history()

    # ── 3) Tests priorisieren ──────────────────────────────────────────────
    all_changed = set()
    for sources in test_mapping.values():
        all_changed.update(sources)

    discovered_tests: list[Tuple[float, Path, str]] = []
    for test_dir, sources in test_mapping.items():
        test_files = _discover_tests_in_dir(test_dir)
        for tf in test_files:
            score, reason = _compute_priority(tf, list(all_changed), history)
            discovered_tests.append((score, tf, reason))

    # Deduplizieren (gleicher Pfad kann aus mehreren Mappings kommen)
    seen: set[Path] = set()
    unique_tests: list[Tuple[float, Path, str]] = []
    for score, path, reason in sorted(discovered_tests, key=lambda x: -x[0]):
        if path not in seen:
            seen.add(path)
            unique_tests.append((score, path, reason))

    # Nach Priorität sortieren
    unique_tests.sort(key=lambda x: -x[0])

    # ── 4) Test-Infos ausgeben ──────────────────────────────────────────────
    print(file=sys.stderr)
    print("📊 Priorisierte Test-Dateien:", file=sys.stderr)
    for i, (score, path, reason) in enumerate(unique_tests):
        rel = path.relative_to(REPO_ROOT)
        print(f"  {i+1:3d}. [{score:4.1f}] {rel}  ({reason})", file=sys.stderr)

    # Known failures from history
    known_failures = history.get("failures", {})
    if known_failures:
        print(f"\n⚠ Bekannte historische Fehlschläge ({len(known_failures)}):", file=sys.stderr)
        for fname, finfo in sorted(known_failures.items()):
            print(f"  • {fname} (x{finfo['count']}, zuletzt {finfo.get('last_seen', '?')})", file=sys.stderr)

    # ── 5) Erweiterte Modul-Map laden ──────────────────────────────────────
    custom_map_file = HISTORY_DIR / "module_map.json"
    global SOURCE_TO_TEST_MAP
    if custom_map_file.exists():
        try:
            custom = json.loads(custom_map_file.read_text("utf-8"))
            if isinstance(custom, dict):
                SOURCE_TO_TEST_MAP = {**SOURCE_TO_TEST_MAP, **custom}
                print(f"\n📦 Custom module mapping geladen: {len(custom)} Einträge", file=sys.stderr)
        except (json.JSONDecodeError, OSError):
            pass

    # ── 6) Tests ausführen ──────────────────────────────────────────────────
    output: dict[str, Any] = {
        "prioritized_tests": [
            [score, str(path.relative_to(REPO_ROOT).as_posix()), reason]
            for score, path, reason in unique_tests
        ],
        "failures": [],
        "duration": 0.0,
        "total_tests": len(unique_tests),
        "passed": 0,
        "failed": 0,
        "new_failures": None,
        "history_summary": {
            "total_entries": len(history.get("failures", {})),
            "known_failures": sum(
                v.get("count", 0) for v in history.get("failures", {}).values()
            ),
        },
        "changed_files": changed_files,
        "diff_ref": args.diff_ref,
    }

    if args.dry_run or not unique_tests:
        output["duration"] = round(time.time() - start_time, 2)
        output["dry_run"] = True
        if not unique_tests:
            output["note"] = "Keine Tests gefunden/correlated"
        print(json.dumps(output, indent=2, ensure_ascii=False))
        return

    results = _run_prioritized_tests(
        unique_tests, args.max_workers, args.file_timeout,
    )

    # ── 7) Ergebnisse auswerten ─────────────────────────────────────────────
    new_failures: list[str] = []
    for path, (passed, _output) in results.items():
        rel = str(path.relative_to(REPO_ROOT).as_posix())
        if not passed:
            output["failures"].append(rel)
            output["failed"] += 1
            # Prüfen ob neu (nicht in history)
            if rel not in history.get("failures", {}):
                new_failures.append(rel)
        else:
            output["passed"] += 1

    output["new_failures"] = new_failures if new_failures else None

    # ── 8) History aktualisieren ────────────────────────────────────────────
    history = _update_history(history, results, time.time() - start_time)
    _save_history(history)

    output["duration"] = round(time.time() - start_time, 2)
    output["history_summary"] = {
        "total_entries": len(history.get("failures", {})),
        "known_failures": sum(
            v.get("count", 0) for v in history.get("failures", {}).values()
        ),
    }

    # ── 9) JSON-Output ──────────────────────────────────────────────────────
    print(json.dumps(output, indent=2, ensure_ascii=False))

    # Exit-Code: 0 = alles grün, 1 = failures
    sys.exit(1 if output["failed"] > 0 else 0)


if __name__ == "__main__":
    main()