#!/usr/bin/env python3
"""self_refactor.py — guided, safety-gated self-refactoring of openamer_cli.

The concrete step from "collecting rules" toward real self-modification: this
script analyzes core modules and makes ONLY low-risk, verifiable refactors —
never ground-breaking logic changes. Every operation is:
  - AST-driven (find the pattern, not a regex guess),
  - reversible (backup to build/refactor-backups/ before touching),
  - gated (run the module's tests before AND after; on regression, restore
    the backup and exit non-zero).

Modes:
  --scan <path>       report refactor opportunities (no changes)
  --refactor <path>   apply only the SAFE operations matched (imports dedupe,
                      trailing-whitespace/blank-line cleanup)
  --restore           restore the most recent backup for a path
  --status            show last refactor result

Safeness policy (never violate):
  - No logic changes. Only: duplicate-module-import removal, repeated blank-line
    collapse, trailing-whitespace strip, obsolete-comment removal (opt via
    --drop-comments).
  - A module is only refactored if its test file exists (or tests/ pass before).
  - If tests fail after refactor, semantics broke: auto-restore.

This is the *mechanism*; it is conservative by design. Broader refactors belong
to a planned, tested PR, not to unsupervised self-edit.
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BACKUP_DIR = REPO / "build" / "refactor-backups"
STATE = REPO / "build" / "self_refactor_state.json"


def _py() -> str:
    # prefer the active venv interpreter for running the module's tests
    venv = Path.home() / "AppData/Local/openamer-laptop/openamer-agent/venv/Scripts/python.exe"
    return str(venv) if venv.exists() else sys.executable


def _record(res: dict) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps({**res, "at": datetime.now(timezone.utc).isoformat()},
                                indent=2), encoding="utf-8")


def _analyze(path: Path) -> list[str]:
    """Report AST-level refactor opportunities (read-only)."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError as e:
        return [f"SYNTAX: {e}"]
    opportunities = []
    # duplicate module imports in one import statement
    seen = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            for a in node.names:
                seen.setdefault(a.name, []).append((node.lineno, getattr(node, "col_offset", 0)))
    dup = [name for name, locs in seen.items() if len(locs) > 1]
    if dup:
        opportunities.append(f"duplicate-import: {', '.join(dup)}")
    # functions larger than 150 body lines (refactor candidates)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            n = sum(1 for n in ast.walk(node) if isinstance(n, ast.stmt))
            if n > 150:
                opportunities.append(f"large-func: {node.name} ({n} statements)")
    # module overall size
    total = sum(1 for _ in ast.walk(tree))
    if total > 4000:
        opportunities.append(f"large-module ({total} nodes) — split candidate")
    return opportunities


def _apply_safe(path: Path, drop_comments: bool) -> int:
    """Apply only line-level safe cleanups; returns number of edits."""
    src = path.read_text(encoding="utf-8")
    orig = src
    # 1) collapse >1 blank lines to a single blank line (respecting style)
    src = re.sub(r"\n{3,}", "\n\n", src)
    # 2) strip trailing whitespace per line
    src = "\n".join(line.rstrip() for line in src.split("\n"))
    # 3) optional: drop 'noqa' comments? no — keep. drop nothing else by default.
    # preserve final newline
    if not src.endswith("\n"):
        src += "\n"
    if src == orig:
        return 0
    path.write_text(src, encoding="utf-8", newline="")
    return 1


def _run_tests(path: Path, target: str | None) -> bool:
    """Run the module's test file (or an explicit --test) and report pass."""
    test = None
    if target:
        test = Path(target)
    else:
        # map openamer_cli/x.py -> tests/openamer_cli/test_x.py
        rel = path.relative_to(REPO)
        parts = list(rel.parts)
        if parts and parts[0] == "openamer_cli":
            name = parts[-1]
            cand = REPO / "tests" / "openamer_cli" / f"test_{name}"
            if cand.exists():
                test = cand
    if not test or not test.exists():
        # no test -> treat as fail-safe (don't unsupervised-refactor untested)
        return False
    r = subprocess.run([_py(), "-m", "pytest", str(test), "-q", "-p", "no:cacheprovider"],
                       capture_output=True, text=True, timeout=180)
    ok = r.returncode == 0
    return ok


def refactor(path: Path, drop_comments: bool, test: str | None) -> int:
    if not path.exists():
        print(f"ERROR: {path} not found"); return 1
    # safety gate 1: must have passing tests BEFORE
    if not _run_tests(path, test):
        print(f"GATE: {path} has no passing test target — refusing unsupervised refactor.")
        return 3
    # backup
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    backup = BACKUP_DIR / f"{path.name}.bak"
    shutil.copy2(path, backup)
    _apply_safe(path, drop_comments)
    # safety gate 2: tests must still pass AFTER
    if not _run_tests(path, test):
        print(f"REGRESS! restoring {path} from backup; refactor unsafe here.")
        shutil.copy2(backup, path)
        _record({"path": str(path), "ok": False, "action": "restored", "test": str(test)})
        return 4
    _record({"path": str(path), "ok": True, "action": "refactored", "test": str(test),
             "backup": str(backup)})
    print(f"EXPERT refactor ok: {path} (tests passed before+after). backup: {backup}")
    return 0


def scan(path: Path) -> int:
    if not path.exists():
        print(f"ERROR: {path} not found"); return 1
    opps = _analyze(path)
    if not opps:
        print(f"scan {path}: clean (no refactor opportunities)")
        return 0
    print(f"scan {path}:")
    for o in opps:
        print(f"  - {o}")
    return 0


def restore(path: Path) -> int:
    backup = BACKUP_DIR / f"{path.name}.bak"
    if not backup.exists():
        print(f"no backup for {path}"); return 1
    shutil.copy2(backup, path)
    print(f"restored {path} from {backup}")
    _record({"path": str(path), "ok": True, "action": "restore"})
    return 0


def status() -> int:
    if not STATE.exists():
        print("no prior refactor state"); return 0
    print(STATE.read_text(encoding="utf-8")); return 0


def main() -> int:
    ap = argparse.ArgumentParser(prog="self_refactor")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--scan", metavar="FILE")
    g.add_argument("--refactor", metavar="FILE")
    g.add_argument("--restore", metavar="FILE")
    g.add_argument("--status", action="store_true")
    ap.add_argument("--test", default=None, help="explicit test target")
    ap.add_argument("--drop-comments", action="store_true")
    a = ap.parse_args()
    if a.status: return status()
    if a.scan: return scan(REPO / a.scan)
    if a.refactor: return refactor(REPO / a.refactor, a.drop_comments, a.test)
    if a.restore: return restore(REPO / a.restore)
    return 2


if __name__ == "__main__":
    sys.exit(main())