#!/usr/bin/env python3
"""
OpenAmer Fleet Scorecard - ECONOMIC SENSE (AEON fleet-scorecard idea).
=====================================================================
A living organism needs to know what its upkeep costs. This organ reads the
cron fleet + model-benchmarker outputs and computes:

  - runs per job (last status, cadence)
  - agent-jobs vs script-jobs (agent = token-hungry, script = nearly free)
  - estimated daily API call load
  - alerts: jobs with recent errors, jobs running too often for their value

Usage: scorecard.py   -> prints table + writes scorecard.json
Exit 0 always.
"""
import json
import re
from datetime import datetime
from pathlib import Path

OA_HOME = Path(r"C:\Users\damir\AppData\Local\openamer-laptop")
JOBS_FILE = OA_HOME / "cron" / "jobs.json"
OUT_FILE = OA_HOME / "scorecard.json"


def parse_interval(schedule):
    """Best-effort 'every Xh/m' or cron -> estimated runs per day."""
    s = str(schedule or "")
    m = re.search(r"every (\d+)m", s)
    if m:
        return max(1, int(1440 / int(m.group(1))))
    m = re.search(r"every (\d+)h", s)
    if m:
        return max(1, int(24 / int(m.group(1))))
    # cron "M H * * *" daily-ish
    if re.match(r"^\d+ \d+ \* \* \*$", s):
        return 1
    if s.startswith("*/"):
        try:
            return max(1, int(1440 / int(s.split()[0][2:])))
        except Exception:
            pass
    return 24  # unknown -> assume hourly


def main():
    data = json.loads(JOBS_FILE.read_text(encoding="utf-8"))
    jobs = data if isinstance(data, list) else data.get("jobs", [])

    rows = []
    total_runs = 0
    agent_runs = 0
    for j in jobs:
        name = j.get("name", "?")
        is_script = bool(j.get("script")) or j.get("no_agent")
        runs_day = parse_interval(j.get("schedule_display") or j.get("schedule"))
        total_runs += runs_day
        if not is_script:
            agent_runs += runs_day
        err = "ERR" if j.get("last_status") == "error" else ""
        rows.append({"job": name[:38], "kind": "script" if is_script else "AGENT",
                     "runs_per_day": runs_day, "flag": err})

    rows.sort(key=lambda r: -r["runs_per_day"])
    script_runs = total_runs - agent_runs

    print("FLEET SCORECARD")
    print("=" * 66)
    print(f"{'Job':<40} {'Kind':<7} {'Runs/day':>9}  Flag")
    print("-" * 66)
    for r in rows:
        print(f"{r['job']:<40} {r['kind']:<7} {r['runs_per_day']:>9}  {r['flag']}")
    print("=" * 66)

    # Agent-jobs cost tokens; rough weight: 1 agent run ~= 15 API calls,
    # 1 script run ~= 0 (deterministic python).
    est_api_calls_day = agent_runs * 15
    print(f"jobs: {len(rows)} | runs/day total: {total_runs} "
          f"(script {script_runs}, AGENT {agent_runs})")
    print(f"estimated API-heavy calls/day: ~{est_api_calls_day}")

    errs = [r["job"] for r in rows if r["flag"]]
    hot = [r for r in rows if r["runs_per_day"] >= 48]
    if errs:
        print(f"failing: {', '.join(errs)}")
    if hot:
        print(f"high-frequency (>={48}/day): {', '.join(r['job'] for r in hot)}")

    out = {
        "time": datetime.now().isoformat(timespec="seconds"),
        "jobs": len(rows), "runs_total": total_runs,
        "runs_script": script_runs, "runs_agent": agent_runs,
        "est_api_calls_day": est_api_calls_day,
        "failing": errs,
        "rows": rows,
    }
    OUT_FILE.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"written: {OUT_FILE.name}")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
