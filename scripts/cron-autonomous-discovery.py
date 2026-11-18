#!/usr/bin/env python3
"""Cron entry point for the Autonomous Discovery cycle.

Runs one bounded discovery cycle and prints ONLY newly accepted findings, so a
``no_agent`` cron slot stays silent when nothing new was learned. Zero tokens:
the cycle reads local telemetry and the trend radar, never an LLM.

Registered as a no-agent cron job -> empty stdout means "nothing to report".
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from autonomous_discovery import main  # noqa: E402

if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass
    raise SystemExit(main(["--cron"]))
