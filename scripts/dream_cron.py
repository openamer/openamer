#!/usr/bin/env python3
"""Cron wrapper: run dream cycle (REM replay) + memory consolidation (sleep).

Order matters, like human sleep: first REM replays the day, then deep sleep
consolidates it — compressing old low-usefulness episodes, promoting what
mattered, archiving (never deleting) the rest.

Prints the dream report verbatim (watchdog-style delivery), then appends a
one-line consolidation summary.
"""
import subprocess, sys, datetime, pathlib

BASE = r"C:/Users/damir/AppData/Local/openamer-laptop"
day = datetime.date.today().isoformat()

# 1. REM: replay the day's sessions -> dreams.json + report
r = subprocess.run([sys.executable, BASE + "/scripts/dream_cycle.py"],
                   capture_output=True, text=True, timeout=300)

# 2. Deep sleep: consolidate episodic memory
c = subprocess.run([sys.executable, BASE + "/scripts/training/memory_consolidation.py"],
                   capture_output=True, text=True, timeout=300)

rep = pathlib.Path(BASE + f"/reports/dream-{day}.md")
if rep.exists():
    print(rep.read_text(encoding="utf-8"))
else:
    print("ERROR: no dream report\n" + r.stdout + r.stderr)

# consolidation summary (one line, non-fatal)
if c.returncode == 0 and c.stdout.strip():
    print("\n---\n" + c.stdout.strip())
elif c.returncode != 0:
    print("\n---\n[consolidation] ERROR: " + (c.stderr or c.stdout).strip()[:300])

# 3. Diary: write yesterday's first-person entry (continuity of self)
try:
    d = subprocess.run([sys.executable,
                        BASE + "/scripts/training/session_diary.py", "--days", "1"],
                       capture_output=True, text=True, timeout=300)
    if d.stdout.strip():
        print("\n---\n" + d.stdout.strip())
except Exception as ex:
    print(f"\n---\n[diary] skipped: {ex}")
