#!/usr/bin/env python3
"""Nightly test-suite watchdog: run the canonical suite, alert only on failure.

Why this exists: "the system works" is not a state that can be asserted once —
the repo moves (cron jobs commit to it daily), so yesterday's green says nothing
about today. This job converts the claim into a *measurement that refreshes
itself*: it runs the canonical runner, records the result, and stays silent
unless something went red.

Deliberately a watchdog, not a reporter: empty stdout means "all green, nothing
to say" and the cron delivers nothing. Silence is the success signal. A message
only arrives when the suite is red, or when the run itself could not complete.

Canonical runner contract (do NOT substitute a bare pytest call): scripts/
run_tests.sh runs under `env -i` with TZ=UTC/LANG=C.UTF-8/PYTHONHASHSEED=0 —
a raw pytest inherits PYTHONPATH and can be green while this is red. On Windows
the wrapper needs OPENAMER_PYTHON because it probes the POSIX .venv/bin layout.

Usage:
    python test-suite-watchdog.py [target]     # target defaults to tests/

Exit codes:
  0 -> suite green                       -> silent (or one "recovered" line)
  1 -> suite red, or run could not complete -> prints the alert
"""
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

REPO = Path(os.environ.get("OPENAMER_REPO", str(Path.home() / "openamer-repo")))
HOME = Path(
    os.environ.get("OPENAMER_HOME", str(Path.home() / "AppData" / "Local" / "openamer-laptop"))
)
# Repo-local venv: the canonical runner needs a python with the project deps,
# and this is the one that ships with the checkout.
PYTHON = REPO / ".venv" / "Scripts" / "python.exe"
RUNNER = REPO / "scripts" / "run_tests.sh"
STATE = HOME / "logs" / "test-suite-watchdog.json"
LOG = HOME / "logs" / "test-suite-watchdog.log"

# Whole suite normally; argv[1] narrows it (scoped re-runs, and the only way to
# exercise this watchdog end-to-end without burning 30 minutes per test).
DEFAULT_TARGET = "tests/"

# A full-suite run at 32 workers measured ~30+ min on this box; give it room
# without letting a hung runner block the tick forever.
TIMEOUT_S = 3000
SUMMARY_RE = re.compile(
    r"Summary:\s*(\d+)\s*files,\s*(\d+)\s*tests passed,\s*(\d+)\s*failed"
)
# The runner marks a failing file as "✗ tests\path\file.py"; the same glyph also
# appears as the running counter ("✗ 2]"), so match the path explicitly.
FAILING_FILE_RE = re.compile(r"✗\s+(tests\\[^\s(]+\.py)")
# The last progress line of a red run; its trailing "✗ N" is the failure count
# that belongs to the file named earlier in that same line.
FAILED_FILE_LINE_RE = re.compile(r"✗\s+(tests\\[^\s(]+\.py)\s+\((\d+)✓\s+(\d+)✗")


def _log(log_path: Path, line: str) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(f"{datetime.now().isoformat(timespec='seconds')} {line}\n")


def _load_state(state_path: Path) -> dict:
    try:
        return json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _env_override(name: str, default: Path) -> Path:
    """Let the test harness redirect a file so it cannot clobber live state."""
    raw = os.environ.get(f"TEST_WATCHDOG_{name}")
    return Path(raw) if raw else default


def _summarize_failures(out: str) -> list[str]:
    """Per-file failure counts, worst first — from the runner's progress lines."""
    counts = {
        path: int(failed)
        for path, _passed, failed in FAILED_FILE_LINE_RE.findall(out)
    }
    if not counts:  # fall back to names without counts
        return sorted(set(FAILING_FILE_RE.findall(out)))
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return [f"{path}  ({n} failing)" for path, n in ranked]


def main() -> int:
    state_path = _env_override("STATE", STATE)
    log_path = _env_override("LOG", LOG)

    if not RUNNER.exists() or not PYTHON.exists():
        print("TEST-WATCHDOG: runner or venv python missing")
        print(f"  runner: {RUNNER} exists={RUNNER.exists()}")
        print(f"  python: {PYTHON} exists={PYTHON.exists()}")
        return 1

    target = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_TARGET
    env = dict(os.environ)
    env["OPENAMER_PYTHON"] = str(PYTHON)
    started = time.time()
    try:
        proc = subprocess.run(
            ["bash", str(RUNNER), target, "-q"],
            cwd=str(REPO),
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=TIMEOUT_S,
        )
    except subprocess.TimeoutExpired:
        _log(log_path, f"TIMEOUT after {TIMEOUT_S}s (target={target})")
        print(f"TEST-WATCHDOG: suite did not finish within {TIMEOUT_S}s")
        return 1

    elapsed = int(time.time() - started)
    out = (proc.stdout or "") + (proc.stderr or "")

    m = SUMMARY_RE.search(out)
    if m is None:
        _log(log_path, f"NO SUMMARY rc={proc.returncode} in {elapsed}s")
        print("TEST-WATCHDOG: could not read a summary from the runner output")
        print(f"  exit={proc.returncode}  elapsed={elapsed}s")
        print("--- last 25 lines ---")
        print("\n".join(out.strip().splitlines()[-25:]))
        return 1

    n_files, n_passed, n_failed = (int(g) for g in m.groups())
    prev = _load_state(state_path)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        json.dumps(
            {
                "ts": datetime.now().isoformat(timespec="seconds"),
                "target": target,
                "files": n_files,
                "passed": n_passed,
                "failed": n_failed,
                "elapsed_s": elapsed,
            },
            indent=1,
        ),
        encoding="utf-8",
    )

    if n_failed == 0:
        _log(log_path, f"GREEN {n_passed} passed / {n_files} files in {elapsed}s")
        prev_failed = prev.get("failed")
        if prev_failed not in (None, 0):
            # Recovery is worth one message: the previous run was red.
            print(
                f"TEST-WATCHDOG: recovered — suite is green again.\n"
                f"  {n_passed} passed, {n_files} files, {elapsed}s "
                f"(previous run had {prev_failed} failing)"
            )
        return 0  # silent when it was already green

    _log(log_path, f"RED {n_failed} failed / {n_passed} passed in {elapsed}s")
    print(
        f"TEST-WATCHDOG: {n_failed} failing test(s) in the canonical suite\n"
        f"  {n_passed} passed, {n_files} files, {elapsed}s\n"
    )
    failing = _summarize_failures(out)
    if failing:
        print("Affected files:")
        for line in failing[:15]:
            print(f"  {line}")
        if len(failing) > 15:
            print(f"  … and {len(failing) - 15} more")
        print()
    print(f"--- runner tail ({target}) ---")
    print("\n".join(out.strip().splitlines()[-40:]))
    return 1


if __name__ == "__main__":
    sys.exit(main())
