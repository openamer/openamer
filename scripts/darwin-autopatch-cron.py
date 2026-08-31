#!/usr/bin/env python3
"""darwin-autopatch-cron.py — cron wrapper: launch autopatch detached, exit fast.

The full autopatch run (3 validator passes) exceeds the 110s cron timeout,
so we start it detached and let it write reports/darwin-autopatch.{md,json}.
"""
import subprocess
import sys
import datetime
from pathlib import Path

REPO = Path(r"C:\Users\damir\openamer-repo")
LOG = REPO / "reports" / "darwin-autopatch-last.log"

r = subprocess.Popen(
    [sys.executable, str(REPO / "scripts" / "darwin_skill_autopatch.py"), "--apply"],
    cwd=str(REPO), stdout=open(LOG, "w"), stderr=subprocess.STDOUT,
    creationflags=0x00000008,  # DETACHED_PROCESS
)
print(f"autopatch launched pid={r.pid} at {datetime.datetime.now().isoformat(timespec='seconds')}")
print("results -> reports/darwin-autopatch.md")
sys.exit(0)
