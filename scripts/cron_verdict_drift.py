#!/usr/bin/env python3
"""Does every cron job's reported verdict match its own run history?

Why this exists, measured 2026-11-24: three of the four jobs sitting on
`last_status: error` were not failing at all.

* Provider-Liveness Watchdog: last durable run at 08:06 exited 0, but the
  verdict still said error from 07:15, and the artifact-debt checker read that
  stale verdict for 14 hours.
* i18n Converge: the 20:30 slot hit its 1800s cap, then the 22:00 slot
  completed — and the error was still on the board.
* Repo-Auto-Commit: a `commit_but_push_failed` ledger entry outlived three
  runs that exited 0, because several early-return paths wrote no ledger at all.

The scheduler keeps a durable row per execution in ``cron/executions.db``, so a
contradiction between ``jobs.json`` (what the board shows) and that history
(what actually ran) is a *measurement*, not an opinion. This script reports
those contradictions and nothing else — it does not retry jobs, mutate the
board, or guess at causes.

Checks, per ENABLED job:

  DISAGREE   the newest durable execution's status differs from ``last_status``
  UNKNOWN    the newest execution never reached a terminal state (scheduler
             died mid-run) — side effects are genuinely unknown
  HUNG       the newest execution is still 'running' long past its interval
  OVERDUE    ``next_run_at`` is more than 2 intervals in the past (with a 1h
             floor), i.e. the job is not being dispatched at all
  NEVER      no execution row exists for an enabled job

Two non-findings are excluded on purpose, because a check that cries wolf gets
ignored (measured 2026-11-24, first run of this script: 15 findings, of which 8
were noise):

* a job whose first tick has not arrived yet has no execution row and is not
  broken — NEVER only fires once ``created_at + interval`` has passed;
* a slot that is 'running' right now is not a contradiction with a previous
  verdict — it only fires as HUNG after more than max(1h, 2 intervals).

The execution history is a rolling window (measured 2026-11-24: 1001 rows
spanning 03:45-23:10 of one day), so "no row" only means "did not run" for a job
whose interval is short enough that it must have ticked inside that window. A
daily job whose last row was pruned is not broken; a 30-minute job that never
appears is.

Exit codes: 0 = no contradiction (silent, so a cron slot stays quiet when
healthy), 1 = findings, 2 = the inputs could not be read (a real error, and it
must not be confused with "everything is fine").
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

HOME = Path(
    os.environ.get("OPENAMER_HOME")
    or (
        Path.home() / "AppData" / "Local" / "openamer-laptop"
        if os.name == "nt"
        else Path.home() / ".openamer-laptop"
    )
)
JOBS = HOME / "cron" / "jobs.json"
EXECUTIONS = HOME / "cron" / "executions.db"

# Scheduler status -> the durable execution status it should correspond to.
STATUS_EQUIVALENTS = {
    "ok": {"completed"},
    "success": {"completed"},
    "completed": {"completed"},
    "error": {"failed"},
    "failed": {"failed"},
}


def parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def load_jobs() -> list[dict]:
    if not JOBS.is_file():
        raise FileNotFoundError(f"no job board at {JOBS}")
    data = json.loads(JOBS.read_text(encoding="utf-8"))
    jobs = data if isinstance(data, list) else data.get("jobs", [])
    return [job for job in jobs if isinstance(job, dict)]


def newest_executions() -> tuple[dict[str, dict], timedelta]:
    """job_id -> its newest durable execution row, plus the window those rows cover."""
    if not EXECUTIONS.is_file():
        raise FileNotFoundError(f"no execution history at {EXECUTIONS}")
    uri = f"file:{EXECUTIONS.as_posix()}?mode=ro"
    connection = sqlite3.connect(uri, uri=True, timeout=15)
    try:
        cursor = connection.execute(
            "SELECT job_id, status, started_at, finished_at, claimed_at, error "
            "FROM executions"
        )
        newest: dict[str, dict] = {}
        earliest = None
        latest = None
        for job_id, status, started_at, finished_at, claimed_at, error in cursor:
            stamp = parse_time(finished_at) or parse_time(started_at) or parse_time(claimed_at)
            if stamp is None:
                continue
            if earliest is None or stamp < earliest:
                earliest = stamp
            if latest is None or stamp > latest:
                latest = stamp
            current = newest.get(job_id)
            if current is None or stamp > current["at"]:
                newest[job_id] = {
                    "status": status,
                    "at": stamp,
                    "error": (error or "")[:160],
                }
        window = (latest - earliest) if earliest and latest else timedelta(0)
        return newest, window
    finally:
        connection.close()


def interval_of(job: dict) -> timedelta:
    """Best-effort schedule width, used only for the OVERDUE grace period."""
    schedule = job.get("schedule") or {}
    kind = schedule.get("kind")
    if kind == "interval":
        minutes = schedule.get("minutes")
        if isinstance(minutes, (int, float)) and minutes > 0:
            return timedelta(minutes=float(minutes))
    last = parse_time(job.get("last_run_at"))
    nxt = parse_time(job.get("next_run_at"))
    if last and nxt and nxt > last:
        return nxt - last
    return timedelta(hours=24)


def findings(now: datetime | None = None) -> list[dict]:
    now = now or datetime.now(timezone.utc)
    jobs = load_jobs()
    history, window = newest_executions()
    out: list[dict] = []

    for job in jobs:
        if job.get("enabled") is not True:
            continue
        job_id = job.get("id") or ""
        name = job.get("name") or job_id
        verdict = (job.get("last_status") or "").strip().lower()
        run = history.get(job_id)
        interval = interval_of(job)
        hung_after = max(timedelta(hours=1), interval * 2)

        if run is None:
            created = parse_time(job.get("created_at"))
            first_due = created + interval if created else None
            # Two ways "no row" is not evidence of anything: the first tick has
            # not arrived, or the job's interval is longer than the window the
            # rolling history covers (its row was pruned, not never written).
            must_have_ticked = interval <= window / 2 if window > timedelta(0) else False
            first_due_passed = first_due is not None and now - first_due > timedelta(0)
            if must_have_ticked and first_due_passed:
                out.append(
                    {
                        "check": "NEVER",
                        "job": name,
                        "id": job_id,
                        "detail": (
                            f"enabled, interval {interval}, but no execution row in the "
                            f"{window} history window"
                            + (f" (first tick was due {first_due.isoformat()})" if first_due else "")
                        ),
                    }
                )
            continue

        expected = STATUS_EQUIVALENTS.get(verdict)
        if run["status"] == "running":
            # In flight is not a contradiction; only a run that overstays is.
            if now - run["at"] > hung_after:
                out.append(
                    {
                        "check": "HUNG",
                        "job": name,
                        "id": job_id,
                        "detail": (
                            f"execution still 'running' since {run['at'].isoformat()} "
                            f"({now - run['at']} > {hung_after})"
                        ),
                    }
                )
        elif run["status"] == "unknown":
            out.append(
                {
                    "check": "UNKNOWN",
                    "job": name,
                    "id": job_id,
                    "detail": (
                        f"newest execution ({run['at'].isoformat()}) never reached a terminal "
                        "state; side effects are unknown"
                    ),
                }
            )
        elif expected is not None and run["status"] not in expected:
            out.append(
                {
                    "check": "DISAGREE",
                    "job": name,
                    "id": job_id,
                    "detail": (
                        f"board says '{verdict}' but the newest execution "
                        f"({run['at'].isoformat()}) is '{run['status']}'"
                        + (f" — {run['error']}" if run["error"] else "")
                    ),
                }
            )

        nxt = parse_time(job.get("next_run_at"))
        if nxt is not None:
            grace = hung_after
            if now - nxt > grace:
                out.append(
                    {
                        "check": "OVERDUE",
                        "job": name,
                        "id": job_id,
                        "detail": (
                            f"next_run_at {nxt.isoformat()} is {(now - nxt)} old "
                            f"(grace {grace}); the job is not being dispatched"
                        ),
                    }
                )
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args()

    try:
        found = findings()
    except (FileNotFoundError, sqlite3.Error, json.JSONDecodeError) as exc:
        print(f"CRON-DRIFT: cannot read the inputs: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps({"findings": found, "count": len(found)}, indent=2, ensure_ascii=False))
        return 1 if found else 0

    if not found:
        return 0  # healthy stays silent

    print(f"CRON-DRIFT: {len(found)} job(s) whose reported verdict is not their history")
    for item in found:
        print(f"  {item['check']:<9} {item['job'][:42]:<42} {item['detail']}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
