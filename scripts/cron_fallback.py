#!/usr/bin/env python3
"""
429-Resilience Helper - shared logic for cron wrappers that hit rate limits.
============================================================================
When a wrapper job fails with 429, this helper:
  1. checks systemic.json for a known fallback_model (systemic auto-fills it)
  2. if none, asks hunger_reserve.py for the best alive free model
  3. returns the fallback model string (or None)

Usage (from a wrapper):
    from cron_fallback import get_fallback_model, report_429
    model = get_fallback_model()
    ...
    report_429("my-job-name")   # on HTTP 429
"""
import json
import subprocess
import sys
from pathlib import Path

OA_HOME = Path(r"C:\Users\damir\AppData\Local\openamer-laptop")
SYSTEMIC = OA_HOME / "systemic.json"
SCRIPTS = Path(__file__).parent


def get_fallback_model():
    """Best available fallback model or None."""
    # 1. fast path: systemic already resolved one
    try:
        d = json.loads(SYSTEMIC.read_text(encoding="utf-8"))
        m = d.get("fallback_model")
        if m:
            return m
    except Exception:
        pass
    # 2. slow path: probe now
    r = subprocess.run([sys.executable, str(SCRIPTS / "hunger_reserve.py"), "best"],
                       capture_output=True, text=True, timeout=120)
    if r.returncode == 0 and r.stdout.strip():
        return r.stdout.strip()
    return None


def report_429(job_name):
    """Record that job_name hit a 429 (feeds the nightly dream insights)."""
    log = OA_HOME / "cache" / "learnings.json"
    entry = {
        "id": f"cron-429-{job_name}",
        "session_id": "cron",
        "category": "error",
        "text": f"429 rate limit hit by {job_name} - fallback chain engaged",
        "title": "Log: cron-fleet",
        "_ts": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
    }
    # use 'timestamp' key to match learning-loop schema
    entry["timestamp"] = entry.pop("_ts")
    try:
        d = json.loads(log.read_text(encoding="utf-8"))
        items = d if isinstance(d, list) else d.setdefault("learnings", [])
        items.append(entry)
        log.write_text(json.dumps(d, indent=1, ensure_ascii=False), encoding="utf-8")
        return True
    except Exception as e:
        print(f"[cron_fallback] could not record: {e}", file=sys.stderr)
        return False
