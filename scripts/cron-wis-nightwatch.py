#!/usr/bin/env python3
"""WIS nightwatch wrapper for the cron job.

Why this exists: the cron job ran the WIS check through an AGENT session, so it
depended on a model API call. It died with
  TimeoutError: idle for 604s (limit 600s) -- waiting for non-streaming API response
even though the check itself is pure local Python. The fix is not a longer
timeout; it is removing the LLM from the path. This script runs the check and
prints the summary itself, so the job can be no_agent=True.

Output contract (no_agent: stdout is delivered verbatim, empty = silent):
  - healthy, no drift  -> one compact line
  - drifts / errors    -> several lines, loud
Exit code is ALWAYS 0: a non-zero exit makes the scheduler send an error alert
on top of whatever we printed, which would duplicate the message.
"""
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPTS = Path(r"C:\Users\damir\AppData\Local\openamer-laptop\scripts")
CHECK = SCRIPTS / "workflow_immune.py"
CDP = "http://localhost:9222/json/version"


def cdp_up(timeout=4):
    import urllib.request
    try:
        urllib.request.urlopen(CDP, timeout=timeout).read()
        return True
    except Exception:
        return False


def main():
    if not CHECK.exists():
        print(f"[WIS] FAIL: {CHECK} not found")
        return 0
    if not cdp_up():
        # No Chrome on :9222 -> the check cannot navigate. Say so plainly instead
        # of printing a traceback nobody reads.
        print("[WIS] SKIPPED: Chrome CDP :9222 nicht erreichbar -- "
              "Workflow-Check konnte nicht laufen (kein Drift-Urteil moeglich).")
        return 0

    try:
        r = subprocess.run([sys.executable, str(CHECK), "check"],
                           capture_output=True, text=True, timeout=900)
        out = (r.stdout or "") + (r.stderr or "")
    except subprocess.TimeoutExpired:
        print("[WIS] FAIL: Check lief länger als 900s und wurde abgebrochen.")
        return 0

    m = re.search(r"IMMUNE REPORT:\s*(\d+)/(\d+) healthy\s*\|\s*"
                  r"heals:\s*(\d+)\s*\|\s*open drifts:\s*(\d+)", out)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    if not m:
        tail = "\n".join(out.strip().splitlines()[-6:])
        print(f"[WIS] FAIL ({stamp}): kein IMMUNE REPORT in der Ausgabe. Letzte Zeilen:")
        print(tail)
        return 0

    healthy, total, heals, drifts = (int(g) for g in m.groups())
    if drifts == 0:
        print(f"[WIS] OK ({stamp}): {healthy}/{total} Workflows gesund, "
              f"{heals} geheilt, 0 offene Drifts.")
        return 0

    print(f"[WIS] DRIFT ({stamp}): {healthy}/{total} gesund, {heals} geheilt, "
          f"{drifts} OFFEN")
    for wf, st in _worst_statuses():
        print(f"  - {wf}: {st}")
    return 0


def _worst_statuses():
    """Surface which workflows are still drifted, from the saved state."""
    wf_file = Path(r"C:\Users\damir\AppData\Local\openamer-laptop"
                   r"\workflow-immune\workflows.json")
    out = []
    try:
        data = json.loads(wf_file.read_text(encoding="utf-8"))
        for name, wf in (data.get("workflows") or {}).items():
            if wf.get("last_status") == "drift":
                out.append((name, wf.get("last_check", "?")))
    except Exception:
        pass
    return out[:5]


if __name__ == "__main__":
    sys.exit(main())