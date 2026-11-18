#!/usr/bin/env python3
"""Turn cron failures into CAUSE CLASSES, not a red/green count.

Measured 2026-11-18: three failures in one day had one shape — *the measurement
lied, the code did not*:

  1. the locale verifier reported 891 broken placeholders, none real (it compared
     translated words instead of variables);
  2. the dashboard answered /api/discovery with 404 while the route existed on
     disk, because a stale process kept serving its old route table and every
     watchdog only asked "is the port open?";
  3. the repo autocommit wrote `push_failed` into a ledger, and the artifact-debt
     check kept reporting it for hours after the condition had cleared.

Counting those as "3 red cron runs" teaches nothing. Naming the class — the
instrument reported a verdict it had not earned — produces a rule that prevents
the fourth one. That is what this script does: it reads real failures from
`cron/executions.db`, sorts each into a small taxonomy, and prints the *rule*
that class implies.

    python scripts/incident_classes.py                    # classify the last 30 days
    python scripts/incident_classes.py --days 7 --json
    python scripts/incident_classes.py --self-test        # today's 3 incidents as fixtures

Exit 0 always — this is a report, not a gate. The gate lives in the class rules.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
from pathlib import Path

HOME = Path(os.environ.get("OPENAMER_HOME")
            or (Path.home() / "AppData" / "Local" / "openamer-laptop"))
DB = HOME / "cron" / "executions.db"
REPORT = HOME / "reports" / "incident-classes.json"

# class -> (patterns, rule)
# The rule is the part that generalises: what check would have caught this class
# BEFORE it produced a failure.
CLASSES: dict[str, dict] = {
    "measurement_lie": {
        "patterns": [
            r"false positive", r"0 of \d+ judged", r"reported ok while",
            r"contains '(failed|error|push_failed)'", r"SKIPPED",
            r"verified: true .*nothing", r"reported .* but never",
        ],
        "rule": ("A verdict must come from a reading that could have failed. If a check "
                 "cannot see its source it reports SKIPPED, never OK."),
    },
    "stale_process": {
        "patterns": [
            r"stale build", r"served \w+, disk \w+", r"already served",
            r"404 Not Found.*api", r"WinError 10048",
        ],
        "rule": ("Ask WHICH build answers, not whether the port is open: identity endpoint "
                 "plus an exclusive bind, so a stale process cannot stay invisible."),
    },
    "missing_handoff": {
        "patterns": [
            r"push_failed", r"unpublished", r"dirty path", r"outside the sweep scope",
            r"nothing to publish", r"commit_but_push_failed",
        ],
        "rule": ("Work that is produced must be handed to the next stage in the same run: "
                 "a pipeline without a publish step accumulates invisible output."),
    },
    "quota_network": {
        "patterns": [
            r"\b429\b", r"\b402\b", r"rate.?limit", r"timeout", r"timed out",
            r"URLError", r"ConnectionError", r"DNS", r"Name or service not known",
        ],
        "rule": ("Backoff and a named fallback per provider; a quota is an environment "
                 "verdict and must not be logged as a capability result."),
    },
    "config_drift": {
        "patterns": [
            r"invalid choice", r"unknown model", r"model .*not found", r"\b404\b.*model",
            r"config", r"api key", r"unauthorized", r"\b401\b", r"\b403\b",
        ],
        "rule": ("Validate the model/provider/credential against the live registry at "
                 "start, and fail with the resolved value in the message."),
    },
    "unknown_outcome": {
        "patterns": [
            r"scheduler restarted", r"owner exited", r"side effects ran is unknown",
            r"no durable terminal state", r"re-?queue",
        ],
        "rule": ("A run whose owner died has an UNKNOWN outcome, not a failure: re-run it "
                 "idempotently and say unknown — counting it as either success or failure "
                 "invents a fact."),
    },
    "self_kill": {
        "patterns": [
            r"Stop-Process.*own", r"killed itself", r"exit=4294967295",
            r"process .*died.*parent", r"backend exited",
        ],
        "rule": ("Never match the pattern you are killing inside the killing command; "
                 "kill by exact PID after listing, never by substring in-process."),
    },
}

FIXTURES = [
    ("measurement_lie", "1 of 27 judged declared artifacts are not what the job promised: "
                        "false positive in the locale verifier, 891 broken placeholders"),
    ("stale_process", "drift :8899 stale build: served 58d46e7fdec3, disk 95995a7eee04"),
    ("missing_handoff", "committed 6 file(s) as b6ad1c267a but PUSH FAILED: "
                        "commit_but_push_failed (push_failed)"),
]


def classify(text: str) -> str:
    low = (text or "").lower()
    best, best_hits = "unknown", 0
    for name, spec in CLASSES.items():
        hits = sum(1 for pat in spec["patterns"] if re.search(pat, low, re.I))
        if hits > best_hits:
            best, best_hits = name, hits
    return best


def load_failures(days: int) -> list[dict]:
    if not DB.exists():
        raise SystemExit(f"no execution store at {DB}")
    con = sqlite3.connect(str(DB))
    con.row_factory = sqlite3.Row
    rows = con.execute(
        "select job_id, status, started_at, coalesce(error,'') as error "
        "from executions where status != 'completed' and started_at >= date('now', ?) "
        "order by started_at desc", (f"-{days} days",)).fetchall()
    return [dict(r) for r in rows]


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Classify cron failures by cause.")
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args(argv)

    if args.self_test:
        bad = []
        for expected, text in FIXTURES:
            got = classify(text)
            print(f"  {expected:<16} <- {got:<16} {'ok' if got == expected else 'WRONG'}")
            if got != expected:
                bad.append((expected, got))
        print(f"self-test: {len(FIXTURES) - len(bad)}/{len(FIXTURES)} incidents classified")
        return 1 if bad else 0

    rows = load_failures(args.days)
    counts: dict[str, int] = {}
    by_job: dict[str, dict[str, int]] = {}
    samples: dict[str, str] = {}
    for row in rows:
        cls = classify(row["error"])
        counts[cls] = counts.get(cls, 0) + 1
        by_job.setdefault(row["job_id"], {}).setdefault(cls, 0)
        by_job[row["job_id"]][cls] += 1
        samples.setdefault(cls, (row["error"] or "")[:220].replace("\n", " "))

    payload = {
        "ts": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
        "days": args.days,
        "failures": len(rows),
        "classes": {cls: {"count": n, "rule": CLASSES.get(cls, {}).get("rule", "unclassified"),
                          "sample": samples.get(cls, "")}
                    for cls, n in sorted(counts.items(), key=lambda kv: -kv[1])},
        "jobs": {jid: dict(sorted(v.items(), key=lambda kv: -kv[1]))
                 for jid, v in sorted(by_job.items(), key=lambda kv: -sum(kv[1].values()))[:10]},
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(payload, indent=1, ensure_ascii=False), encoding="utf-8")

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=1))
        return 0

    print(f"incident classes — {len(rows)} failure(s) in the last {args.days} day(s)")
    for cls, n in sorted(counts.items(), key=lambda kv: -kv[1]):
        rule = CLASSES.get(cls, {}).get("rule", "unclassified")
        print(f"  {cls:<16} {n:>4}   {rule}")
    if isinstance(payload["jobs"], dict) and payload["jobs"]:
        print("  worst jobs:")
        for jid, classes in list(payload["jobs"].items())[:5]:
            print(f"    {jid}  {classes}")
    print(f"  wrote {REPORT}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
