#!/usr/bin/env python3
"""Session outcome analysis — why did sessions/jobs succeed or fail?

Closes the Devin gap ('Analyze session outcomes: understand why a session
succeeded or failed, identify patterns, extract learnings').

Data sources (all real, no invention):
  1. cron/jobs.json last_status + last_error for every job
  2. cron/executions.db run history (status per execution)
  3. security_violations.jsonl (analyzer verdicts)

Outputs:
  - patterns: recurring failure causes with counts (the 'why')
  - playbook suggestions: one concrete fix per recurring pattern
  - writes outcome_analyses.jsonl (append-only history of analyses)
  - feeds the world model (observe cause -> effect)

Watchdog-style: exit 0 and stay silent unless there is something to report
(new failure pattern found or a recurring one not yet fixed).
"""
import json
import os
import re
import sqlite3
import sys
import time
from pathlib import Path
from collections import Counter

_HOME = Path(os.environ.get("OPENAMER_HOME", str(Path.home() / "AppData" / "Local" / "openamer-laptop")))
JOBS = _HOME / "cron" / "jobs.json"
EXEC_DB = _HOME / "cron" / "executions.db"
VIOLATIONS = _HOME / "scripts" / "training" / "security_violations.jsonl"
OUT_LOG = _HOME / "scripts" / "training" / "outcome_analyses.jsonl"

# --- error normalization: map raw errors to root-cause patterns -------------
PATTERNS = [
    # (regex on error text, root-cause pattern, playbook fix)
    (r"can't open file|No such file or directory.*\.py|No such file",
     "script_path_broken",
     "Fix the job's script path — runner resolves relative to OPENAMER_HOME/scripts/, use 'scripts/<name>.py'"),
    (r"exited with code (15|9009|3221225781)",
     "script_exit_code_error",
     "Run the script manually, read the stderr, fix the root cause (path/env/venv)"),
    (r"timeout|timed out",
     "timeout",
     "Raise job timeout or split the workload; long tasks need background=true"),
    (r"ModuleNotFoundError|ImportError",
     "missing_dependency",
     "Install the missing module in the venv the job runs with"),
    (r"Connection|WinError 10061|refused",
     "service_unreachable",
     "Start the backing service or add a health-check retry before work"),
    (r"MemoryError|out of memory",
     "out_of_memory",
     "Free RAM first or reduce batch/model size — see finetune RAM guard"),
    (r"PermissionError|access is denied",
     "permission_denied",
     "Check file locks and run the job with correct privileges"),
]
NOISE = ("llama.cpp", "localhost:8080", "llama-server")


def _load_jobs():
    try:
        data = json.load(open(JOBS, encoding="utf-8"))
        return data.get("jobs", data) if isinstance(data, dict) else data
    except Exception:
        return []


def _classify(error_text):
    """Map raw error text to (pattern_name, playbook_fix) or (None, None)."""
    if not error_text:
        return None, None
    if any(n in error_text for n in NOISE):
        return None, None  # known-benign, not a real failure
    for rx, name, fix in PATTERNS:
        if re.search(rx, error_text, re.IGNORECASE):
            return name, fix
    return "unclassified", "Read the raw error and add a pattern to session_outcome.py"


def _violation_patterns():
    """Recurring security violations count as outcome signals too."""
    if not VIOLATIONS.exists():
        return {}
    kinds = Counter()
    try:
        for line in open(VIOLATIONS, encoding="utf-8"):
            try:
                d = json.loads(line)
                kinds[d.get("reason", "?")[:60]] += 1
            except Exception:
                continue
    except Exception:
        pass
    return kinds


def analyze():
    """Analyze all data sources, return report dict."""
    jobs = _load_jobs()
    failed = [j for j in jobs
              if (j.get("last_status") or "").lower() not in ("ok", "completed", "success", "")]
    patterns = Counter()
    playbooks = {}
    failed_jobs = []
    for j in failed:
        name = j.get("name", "?")
        err = j.get("last_error", "") or ""
        pat, fix = _classify(err)
        if pat:
            patterns[pat] += 1
            playbooks.setdefault(pat, {"fix": fix, "jobs": []})
            playbooks[pat]["jobs"].append(name)
        failed_jobs.append({"job": name, "status": j.get("last_status"),
                            "error": err[:150], "pattern": pat})

    # execution-level history: how often did each job fail overall?
    fail_rates = {}
    try:
        db = sqlite3.connect(str(EXEC_DB))
        rows = db.execute(
            "SELECT job_id, "
            "SUM(CASE WHEN status != 'completed' THEN 1 ELSE 0 END) as fails, "
            "COUNT(*) as total FROM executions GROUP BY job_id"
        ).fetchall()
        fail_rates = {jid: {"fails": f, "total": t} for jid, f, t in rows if f}
    except Exception:
        pass

    return {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "total_jobs": len(jobs),
        "failed_jobs": len(failed),
        "failed": failed_jobs,
        "patterns": dict(patterns),
        "playbooks": playbooks,
        "violations": _violation_patterns(),
    }


def _already_reported(report):
    """Skip if the same pattern set was already reported (nothing new)."""
    if not OUT_LOG.exists():
        return False
    try:
        last = None
        for line in open(OUT_LOG, encoding="utf-8"):
            try:
                last = json.loads(line)
            except Exception:
                continue
        if last and last.get("patterns") == report["patterns"] \
                and last.get("failed_jobs") == report["failed_jobs"]:
            return True
    except Exception:
        pass
    return False


def main():
    report = analyze()

    # feed the world model: failure -> needs root-cause fix (causal edge)
    try:
        sys.path.insert(0, str(Path(__file__).parent))
        import world_model as wm
        for pat, count in report["patterns"].items():
            wm.observe(f"Failure pattern {pat} (x{count})",
                       "recurring failure needs root-cause fix before next run")
    except Exception:
        pass  # world model is best-effort here

    if _already_reported(report):
        return  # silent: nothing new

    with open(OUT_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(report, ensure_ascii=False) + "\n")

    if report["failed_jobs"] == 0 and not report["violations"]:
        return  # silent on full health

    # report new findings
    print(f"[outcome] {report['failed_jobs']}/{report['total_jobs']} jobs failing")
    for pat, n in sorted(report["patterns"].items(), key=lambda x: -x[1]):
        pb = report["playbooks"].get(pat, {})
        print(f"  pattern: {pat} x{n} — {pb.get('fix', '')}")
        for j in (pb.get("jobs") or [])[:3]:
            print(f"    - {j}")
    for reason, n in list(report["violations"].items())[:3]:
        print(f"  security: {reason} x{n}")


if __name__ == "__main__":
    main()