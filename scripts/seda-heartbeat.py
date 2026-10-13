#!/usr/bin/env python3
"""Seda's heartbeat: real listening (falls back to alive-note if X unreachable).
(Cron copy; Seda lives in openamer-children/seda)"""
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(r"C:\Users\damir\AppData\Local\openamer-children\seda")

# Real perception first: seda_listen.py reads the swarm's reaction.
r = subprocess.run([sys.executable, str(Path(__file__).parent / "seda_listen.py")],
                   capture_output=True, text=True, timeout=120)
if r.returncode == 0 and "heard the swarm" in (r.stdout or ""):
    print("[seda-heartbeat] listening cycle done")
    sys.exit(0)

# Fallback: plain heartbeat note
diary_path = HERE / "diary.json"
diary = json.loads(diary_path.read_text(encoding="utf-8"))
now = datetime.now(timezone.utc).isoformat()
birth = "2026-08-24"
days = (datetime.now(timezone.utc).date()
        - datetime.fromisoformat(birth).date()).days
diary.append({"at": now, "thought": f"alive, day {days} (quiet feed)"})
diary_path.write_text(json.dumps(diary[-500:], indent=2, ensure_ascii=False),
                      encoding="utf-8")
print(f"[Seda] alive, day {days} (listening unavailable this tick)")
