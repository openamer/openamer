#!/usr/bin/env python3
"""
OpenAmer Systemic - PATTERN-RECOGNITION for the immune system (AEON skill-health idea).
=====================================================================================
Single-job errors are accidents. When >=2 jobs share the same error signature,
it is a SYSTEM problem and deserves ONE alarm, not five.

Reads the newest cron output per job, extracts error signatures (429, WinError,
FileNotFoundError, timeouts...), groups them, and reports:

  - individual failures: listed quietly
  - systemic clusters  : one loud verdict with affected jobs

Usage: systemic.py   -> prints report + writes systemic.json
Exit 0 always; exit 2 if a systemic cluster was found (for watchdogs).
"""
import json
import re
import subprocess
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

CRON_OUTPUT = Path(r"C:\Users\damir\AppData\Local\openamer-laptop\cron\output")
JOBS_FILE = Path(r"C:\Users\damir\AppData\Local\openamer-laptop\cron\jobs.json")
OUT_FILE = Path(r"C:\Users\damir\AppData\Local\openamer-laptop\systemic.json")

# signature patterns -> short name (order matters: first match wins)
SIGNATURES = [
    ("rate_limited_429", re.compile(r"(429|rate.limit)", re.I)),
    ("socket_reset", re.compile(r"WinError 10054|ConnectionResetError")),
    ("missing_file", re.compile(r"FileNotFoundError")),
    ("timeout", re.compile(r"(timed? ?out|TimeoutError)", re.I)),
    ("auth", re.compile(r"(401|403|unauthorized|invalid.api.key)", re.I)),
    ("empty_response", re.compile(r"(empty (model )?response|no content)", re.I)),
]

MAX_AGE_H = 24  # only fresh outputs count


def newest_output(job_id):
    d = CRON_OUTPUT / job_id
    if not d.is_dir():
        return None
    files = sorted(d.glob("*.md"), key=lambda f: f.stat().st_mtime)
    return files[-1] if files else None


def classify(text):
    for name, rx in SIGNATURES:
        if rx.search(text):
            return name
    if "## Error" in text or "Traceback" in text:
        return "other_error"
    return None


def main():
    try:
        data = json.loads(JOBS_FILE.read_text(encoding="utf-8"))
        jobs = data if isinstance(data, list) else data.get("jobs", [])
    except Exception as e:
        print(f"jobs.json unreadable: {e}")
        return 0

    now = datetime.now().timestamp()
    sig_jobs = defaultdict(list)   # signature -> [job names]
    healthy = 0

    for j in jobs:
        if j.get("last_status") != "error":
            if j.get("last_status") == "ok":
                healthy += 1
            continue
        f = newest_output(j.get("id", ""))
        if not f:
            continue
        age_h = (now - f.stat().st_mtime) / 3600
        if age_h > MAX_AGE_H:
            continue
        sig = classify(f.read_text(encoding="utf-8", errors="replace")[:4000])
        if sig:
            sig_jobs[sig].append(j.get("name", "?"))

    systemic = {s: js for s, js in sig_jobs.items() if len(js) >= 2}
    singles = {s: js[0] for s, js in sig_jobs.items() if len(js) == 1}

    report = {
        "time": datetime.now().isoformat(timespec="seconds"),
        "healthy": healthy,
        "failing_total": sum(len(v) for v in sig_jobs.values()),
        "systemic_clusters": {k: v for k, v in sorted(systemic.items())},
        "single_failures": singles,
        "verdict": "",
    }

    if systemic:
        worst = max(systemic.items(), key=lambda kv: len(kv[1]))
        report["verdict"] = (
            f"SYSTEMIC: '{worst[0]}' affects {len(worst[1])} jobs "
            f"({', '.join(worst[1][:5])}) - fix the system, not the jobs"
        )
        print("!" * 60)
        print(report["verdict"])
        print("!" * 60)
        rc = 2
        # AUTO-RESPONSE: bei 429-Hunger die Reserve aktivieren und das beste
        # Fallback-Modell in den State schreiben (Wrapper-Jobs koennen es lesen).
        if "rate_limited_429" in systemic or "rate_limited" in systemic:
            try:
                r = subprocess.run(
                    [sys.executable, str(Path(__file__).parent / "hunger_reserve.py"), "best"],
                    capture_output=True, text=True, timeout=120)
                best = (r.stdout or "").strip()
                if r.returncode == 0 and best:
                    report["fallback_model"] = best
                    print(f"[auto] hunger reserve ready: {best}")
                else:
                    report["fallback_model"] = None
                    print("[auto] hunger reserve: kein Fallback lebendig!")
            except Exception as e:
                report["fallback_model"] = None
                print(f"[auto] hunger reserve check failed: {e}")
    else:
        report["verdict"] = "no systemic pattern - failures are individual"
        print(report["verdict"])
        rc = 0

    if singles:
        print(f"individual failures ({len(singles)}):")
        for s, n in singles.items():
            print(f"  - {n}: {s}")

    OUT_FILE.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return rc


if __name__ == "__main__":
    sys.exit(main())
