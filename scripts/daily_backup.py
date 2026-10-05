#!/usr/bin/env python3
"""Daily filesystem backup — automatic self-preservation.

`auto-backup.py` is the survival organ (it snapshots the whole tree, encrypted,
with retention), but it takes `--now`/`--list`/`--restore` args and a no-arg
call only prints help — so it can never be the body of a cron script directly.
It also had no schedule, so the newest backup was over a month old.

This wrapper is the cron body: it runs a real backup and stays quiet unless it
actually backed up or failed (the watchdog pattern).
"""
import os
import subprocess
import sys
from pathlib import Path

HOME = Path(os.environ.get("OPENAMER_HOME", str(Path.home() / "AppData" / "Local" / "openamer-laptop")))
SCRIPT = HOME / "scripts" / "auto-backup.py"


def main() -> int:
    if not SCRIPT.exists():
        print(f"daily-backup: auto-backup.py missing at {SCRIPT}")
        return 0
    try:
        r = subprocess.run([sys.executable, str(SCRIPT), "--now"],
                           capture_output=True, text=True, timeout=1800,
                           env={**os.environ, "OPENAMER_HOME": str(HOME)})
    except subprocess.TimeoutExpired:
        print("daily-backup: backup timed out (1800s) — see scripts/auto-backup.py")
        return 0
    if r.returncode != 0:
        print(f"daily-backup: backup FAILED (exit {r.returncode})")
        tail = (r.stderr or r.stdout or "")[-300:]
        if tail.strip():
            print(tail)
    # success stays silent (no news is good news)
    return 0


if __name__ == "__main__":
    sys.exit(main())
