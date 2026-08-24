#!/usr/bin/env python3
"""
OpenAmer Senses - the NERVOUS SYSTEM.
=====================================
Three senses a living being needs that were missing:

  PAIN      - 429 rate-limits = hunger/exhaustion. Counts recent 429s in cron
              outputs; high pain => the organism should slow down.
  SATIETY   - token/API budget feeling. Reads traffic-cop's last state;
              hungry (no provider) vs satisfied.
  BALANCE   - fleet equilibrium. How many cron jobs are healthy vs failing?
              Dizzy when too many organs misfire.

Usage: senses.py  ->  JSON {pain, satiety, balance, overall}
Exit 0 always (a sense reports, it does not fail).
"""
import json
import re
import sys
from datetime import datetime
from pathlib import Path

CRON_OUTPUT = Path(r"C:\Users\damir\AppData\Local\openamer-laptop\cron\output")
JOBS_FILE = Path(r"C:\Users\damir\AppData\Local\openamer-laptop\cron\jobs.json")
SENSES_FILE = Path(r"C:\Users\damir\AppData\Local\openamer-laptop\senses.json")


def read_text_safe(p, limit=4000):
    try:
        return p.read_text(encoding="utf-8", errors="replace")[:limit]
    except Exception:
        return ""


def sense_pain():
    """Scan the newest cron output per job for 429 exhaustion signals.
    Pain decays: only the last 3 hours count fully, 3-6h counts half."""
    pain = 0
    now = datetime.now().timestamp()
    if CRON_OUTPUT.exists():
        for job_dir in CRON_OUTPUT.iterdir():
            files = sorted(job_dir.glob("*.md"), key=lambda f: f.stat().st_mtime)
            if not files:
                continue
            newest = files[-1]
            age_h = (now - newest.stat().st_mtime) / 3600
            if age_h > 6:  # older pain is forgotten - a healthy being lets go
                continue
            txt = read_text_safe(newest)
            hits = len(re.findall(r"429|rate.limit|Rate limited", txt, re.I))
            weight = 1.0 if age_h <= 3 else 0.5
            pain += min(hits, 3) * weight
    pain = int(round(pain))
    level = "calm" if pain == 0 else "uncomfortable" if pain <= 4 else "exhausted"
    return {"score": pain, "level": level}


def sense_satiety():
    """Traffic-cop's latest verdict: are we fed (providers OK) or hungry?"""
    tc = CRON_OUTPUT / "traffic_cop_15m"
    files = sorted(tc.glob("*.md"), key=lambda f: f.stat().st_mtime) if tc.exists() else []
    if not files:
        return {"state": "unknown"}
    txt = read_text_safe(files[-1])
    ok = len(re.findall(r"✅ OK \(HTTP 200\)", txt))
    dead = len(re.findall(r"❌ .*Tot|❌ .*dead", txt, re.I))
    if ok >= 2:
        state = "satisfied"
    elif ok >= 1:
        state = "fed"
    elif dead:
        state = "starving"
    else:
        state = "hungry"
    return {"state": state, "ok_providers": ok, "dead_providers": dead}


def sense_balance():
    """Fleet equilibrium from jobs.json last_status."""
    try:
        data = json.loads(JOBS_FILE.read_text(encoding="utf-8"))
        jobs = data if isinstance(data, list) else data.get("jobs", [])
    except Exception:
        return {"state": "unknown"}
    total = len(jobs)
    err = sum(1 for j in jobs if j.get("last_status") == "error")
    ratio = err / total if total else 0
    state = ("steady" if ratio < 0.05 else
             "wobbly" if ratio < 0.15 else "falling")
    return {"state": state, "jobs": total, "errors": err, "error_ratio": round(ratio, 3)}


def main():
    result = {
        "time": datetime.now().isoformat(timespec="seconds"),
        "pain": sense_pain(),
        "satiety": sense_satiety(),
        "balance": sense_balance(),
    }
    # Overall wellbeing - one word the rest of the organism can act on
    p, s, b = result["pain"], result["satiety"], result["balance"]
    if p["level"] == "exhausted" or s["state"] in ("starving",):
        result["overall"] = "suffering"
    elif p["level"] != "calm" or s["state"] in ("hungry", "fed") or b["state"] != "steady":
        result["overall"] = "uneasy"
    else:
        result["overall"] = "well"

    SENSES_FILE.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
