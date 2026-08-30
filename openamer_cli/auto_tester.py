"""
Autonomous Test Runner — System testet sich selbst im Hintergrund.

Führt automatisch Tests aus, protokolliert Ergebnisse, schlägt Fixes vor
und kann per Cron im Hintergrund laufen.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _home() -> Path:
    return Path(os.environ.get("OPENAMER_HOME", Path.home() / ".openamer"))


def _repo_dir() -> Path:
    # Explicit OPENAMER_REPO wins over the installed home copy — otherwise
    # cron silently tests a stale tree while the dev repo drifts.
    candidates = [
        Path(os.environ["OPENAMER_REPO"]) if os.environ.get("OPENAMER_REPO") else None,
        _home() / "openamer-agent",
    ]
    for c in [c for c in candidates if c is not None]:
        if (c / "tests").is_dir():
            return c
    return _home() / "openamer-agent"


def _logs_dir() -> Path:
    ldir = _home() / "logs"
    ldir.mkdir(parents=True, exist_ok=True)
    return ldir


# ----- Test Runner -----


def _python_exe() -> str:
    """Wähle den venv-Interpreter, falls vorhanden, sonst sys.executable."""
    repo = _repo_dir()
    venv_py = repo / "venv" / "Scripts" / "python.exe"
    if venv_py.exists():
        return str(venv_py)
    return sys.executable


def run_all_tests(verbose: bool = False) -> dict[str, Any]:
    """Führt ALLE Tests aus und gibt strukturiertes Ergebnis zurück."""
    repo = _repo_dir()
    if not (repo / "tests").is_dir():
        return {"status": "error", "message": "Tests-Verzeichnis nicht gefunden", "test_results": {}}

    py = _python_exe()
    start = time.time()
    result = subprocess.run(
        [py, "-m", "pytest", "tests/", "-x", "--tb=short"],
        capture_output=True,
        text=True,
        timeout=300,
        cwd=repo,
    )
    elapsed = round(time.time() - start, 1)

    # Parse summary aus Output
    passed = 0
    failed = 0
    skipped = 0
    errors: list[str] = []
    for line in result.stdout.split("\n"):
        if "passed" in line and "failed" in line:
            parts = line.split()
            for i, p in enumerate(parts):
                if p == "passed":
                    passed = int(parts[i - 1]) if i > 0 else 0
                elif p == "failed":
                    failed = int(parts[i - 1]) if i > 0 else 0
                elif p == "skipped":
                    skipped = int(parts[i - 1]) if i > 0 else 0
        if "FAILED" in line:
            errors.append(line.strip())

    # Parse exit code
    status = "pass" if result.returncode == 0 else "fail"

    return {
        "status": status,
        "exit_code": result.returncode,
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "total": passed + failed + skipped,
        "elapsed_seconds": elapsed,
        "errors": errors,
        "stdout": result.stdout[-2000:] if not verbose else result.stdout,
        "stderr": result.stderr[-500:] if result.stderr else "",
    }


def run_new_tests() -> dict[str, Any]:
    """Führt NUR die neuen Tests aus (die wir heute gebaut haben)."""
    repo = _repo_dir()
    new_tests = [
        "tests/test_vector_memory.py",
        "tests/test_skills_pipeline.py",
        "tests/openamer_cli/test_autonomous_initiative.py",
        "tests/openamer_cli/test_cross_session_learning.py",
    ]
    existing = [t for t in new_tests if (repo / t).exists()]
    if not existing:
        return {"status": "error", "message": "Keine neuen Tests gefunden"}

    py = _python_exe()
    start = time.time()
    result = subprocess.run(
        [py, "-m", "pytest"] + existing + ["-v", "--tb=short"],
        capture_output=True,
        text=True,
        timeout=120,
        cwd=repo,
    )
    elapsed = round(time.time() - start, 1)

    return {
        "status": "pass" if result.returncode == 0 else "fail",
        "exit_code": result.returncode,
        "stdout": result.stdout[-1500:],
        "stderr": result.stderr[-500:] if result.stderr else "",
        "elapsed_seconds": elapsed,
    }


def save_test_result(result: dict[str, Any]) -> str:
    """Speichert Testergebnis als JSON-Log."""
    logfile = _logs_dir() / f"autotest-{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    result["timestamp"] = datetime.now(timezone.utc).isoformat()
    with open(logfile, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    return str(logfile)


def run_cron_entry() -> str:
    """Cron-kompatibler Einstieg."""
    result = run_new_tests()
    logpath = save_test_result(result)
    return logpath