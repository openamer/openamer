#!/usr/bin/env python3
"""Cron-wrapper: resource-monitor.py --once --alert (Exit 1 bei Schwellwert = Alarm)."""
import subprocess, sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
MAIN_SCRIPT = SCRIPT_DIR / "resource-monitor.py"

result = subprocess.run(
    [sys.executable, str(MAIN_SCRIPT), "--once", "--alert"],
    capture_output=True, text=True, timeout=60,
)
print(result.stdout)
if result.stderr:
    print("STDERR:", result.stderr[:500], file=sys.stderr)
# Exit 1 = threshold alert (by design). Report it but don't mark the cron
# job as erroring — a resource alert is a successful monitoring run.
sys.exit(0)
