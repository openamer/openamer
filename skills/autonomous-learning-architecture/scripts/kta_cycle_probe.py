#!/usr/bin/env python3
"""KTA cycle probe — run ONE real cycle as a SUBPROCESS (exactly as cron does)
and prove whether it actually persisted.

Why a subprocess probe and not an in-process import: `kta_cycle_verify.py`
imports the module and calls `kta_cycle()`, which proves the *function* works.
This probe instead reproduces the *cron* invocation (`python knowledge_to_action.py`)
and then measures the two side effects the cron report depends on:

  * `kta_log.jsonl` line count  (a printed "[kta] ..." line is NOT proof —
    observed 2026-09-23: stdout showed a result while the log never grew)
  * `.kta_rotation` counter     (incremented on EVERY call, logged or not)

It also re-hashes the log a few seconds later to catch a writer that rewrites
rather than appends (content changed under a stable line count).

Usage:
    python kta_cycle_probe.py            # one cycle + persistence verdict
    python kta_cycle_probe.py --no-run   # measure only, do not run a cycle

Exit code: 0 if the cycle persisted, 1 if it printed but did not persist.
"""

import hashlib
import os
import subprocess
import sys
import time
from pathlib import Path

HOME = Path(os.environ.get("OPENAMER_HOME") or (Path.home() / "AppData" / "Local" / "openamer-laptop"))
T = HOME / "scripts" / "training"
SCRIPT = T / "knowledge_to_action.py"
LOG = T / "kta_log.jsonl"
ROT = T / ".kta_rotation"


def _lines(path: Path) -> int:
    if not path.exists():
        return -1
    with path.open(encoding="utf-8", errors="replace") as fh:
        return sum(1 for line in fh if line.strip())


def _md5(path: Path) -> str:
    if not path.exists():
        return "missing"
    h = hashlib.md5()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()[:12]


def _rot() -> str:
    try:
        return ROT.read_text(encoding="utf-8").strip() or "<empty>"
    except Exception:
        return "<missing>"


def main() -> int:
    if not SCRIPT.exists():
        print(f"VERDICT: UNMEASURABLE — no script at {SCRIPT}")
        return 1

    before_lines, before_rot = _lines(LOG), _rot()
    print(f"T={T}")
    print(f"LOG_LINES_BEFORE={before_lines} ROTATION_BEFORE={before_rot}")

    printed = None
    if "--no-run" not in sys.argv:
        proc = subprocess.run(
            [sys.executable, str(SCRIPT)],
            capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=600, cwd=str(T),
        )
        out = (proc.stdout or "").strip().splitlines()
        printed = out[-1] if out else ""
        print(f"EXIT_CODE={proc.returncode}")
        print(f"STDOUT_LAST={printed[:200]}")
        if (proc.stderr or "").strip():
            print(f"STDERR_TAIL={proc.stderr.strip().splitlines()[-1][:200]}")

    time.sleep(3)   # let any competing writer land
    after_lines, after_rot, after_md5 = _lines(LOG), _rot(), _md5(LOG)
    time.sleep(5)
    stable_md5 = _md5(LOG)
    print(f"LOG_LINES_AFTER={after_lines} ROTATION_AFTER={after_rot}")
    print(f"MD5_STABLE={after_md5 == stable_md5} ({after_md5} -> {stable_md5})")

    grew = after_lines > before_lines
    rotated = after_rot != before_rot

    if "--no-run" in sys.argv:
        print("VERDICT: MEASURED_ONLY (no cycle requested)")
        return 0
    if grew and rotated and after_md5 == stable_md5:
        print("VERDICT: APPENDED=True — stdout line is backed by a real log row")
        return 0
    if printed and not grew:
        print("VERDICT: PRINTED_BUT_NOT_PERSISTED — stdout is not proof. "
              "Re-run once to separate a one-off glitch from a reproducible fault, "
              "then check for a second writer (there is only ONE kta_log.jsonl in "
              "the live tree; the repo copy has none).")
        return 1
    if after_md5 != stable_md5:
        print("VERDICT: LOG_REWRITTEN_UNDER_READ — content changed between two reads; "
              "suspect a competing writer, do NOT report success.")
        return 1
    print("VERDICT: NO_APPEND — no usable insight (exit 0 is normal, nothing is "
          "logged: see the 'no usable insight' pitfall).")
    return 1


if __name__ == "__main__":
    sys.exit(main())
