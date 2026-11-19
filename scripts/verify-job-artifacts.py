#!/usr/bin/env python3
"""Artifact debt: every job declares WHAT it must have produced, and this reads it.

Why this exists (measured 2026-10-10). Every serious failure found that day looked
the same from the outside: a healthy exit code over an organ that had done nothing
for weeks.

  * `longterm-memory-indexer` reported `ok` while its store was frozen 17 days.
  * `goal-engine.py --tick` printed `--help` and exited 0 on a `*/30` schedule.
  * three jobs shared one wrapper, so one broken path hid in three places.
  * `:8898` answered `200 OK` with a twenty-day-old file.

Exit codes cannot catch any of those, because the process really did succeed. An
ARTIFACT can: a file that must be touched, a count that must grow. So this reads
the artifact instead of the status.

Modes:
    verify-job-artifacts.py                       check the registry, silent if fine
    verify-job-artifacts.py --discover <job>      run a job, diff the trees, report noise
    verify-job-artifacts.py --discover-exact <j>  run it under the audit hook: exact writes
    verify-job-artifacts.py --discover-all --exact   measure the weak entries, 5 at a time
    verify-job-artifacts.py --verify-produced     check each declaration against real writes
    verify-job-artifacts.py --sync                declare every active job not yet declared
    verify-job-artifacts.py --list                print the registry

`--sync` fills the gap mechanically. Its artifact is `cron/output/<id>` - the
scheduler's stdout archive, which gets a file per run even when the script prints
nothing. Those entries carry `kind: "ran"`: they prove the job EXECUTED, not that it
did its job. A declared artifact elsewhere is `kind: "produced"`. The distinction is
in the data because a green row must never be ambiguous about which of the two facts
it stands for. Refine a `ran` entry with `--discover`.

Generated entries also carry `since`, and the check stays quiet until a full window
has elapsed past it: a job enabled at noon with a six-hour cadence has not MISSED
anything at 12:05. Its archive is old because it was off, not because it is broken.
Without that, enabling the whole fleet at once produced seventeen rows of pure
history - and an alarm that fires on "no chance yet" is how you learn to ignore the
alarm.

An entry may also declare `expect: {"must_not_contain": [...]}`, and the check reads the
artifact's text. Freshness is not the whole truth: `Repo-Auto-Commit` rewrote its ledger
every run while every record in it said `commit_but_push_failed`. A file can be new and
be a record of failure at the same time, and a mtime check cannot tell those apart.

`--discover` is the honest way to grow the registry: it snapshots the trees the
fleet writes into, runs the job's own script, and diffs. The registry is then built
from observation rather than from guessing where a script writes - guessing was
wrong for 10 of 15 candidates on the first attempt.

**But discovery is a LEAD, not a verdict.** Other processes write while it runs, so
the touched set mixes the job's own artifacts with ambient noise. Measured
2026-10-10 on `longterm-memory-indexer`: 11 files changed, of which
`memory/longterm_episodes.jsonl` and `memory/embed_cache.json` are plainly its own
and `logs/agent.log`, `memory/si/*.json` and `scripts/training/lora_out/*` belong to
something else. Read the list and decide which entries belong to the job - the same
rule as every other scan in this fleet: it narrows, the reasoning confirms.

`--control N` cuts most of that noise by adding the missing context: it sits idle for
N seconds BEFORE running the job and records what changed on its own. Whatever changes
with nobody acting is ambient; everything else is closer to the job's own. On eight
candidates, only four were owned by a single job - the other four appeared in two to
four jobs' sets, and assigning those would have been a guess dressed as a measurement.

`--discover-exact` replaces the diff entirely and is the method to prefer: it runs the
script under an audit hook and records what was asked of the OS, across the whole process
tree. Measured on `rsi-objective-gate`, the diff reported 78 touched files and the hook
reported one, `memory/benchmarks.json`.

A job may legitimately produce nothing (a growth log with no news that day). That is
why an entry declares `max_age_minutes` rather than requiring freshness: the
invariant is "touched within this window", not "changed on every run".
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

HOME = Path(__file__).resolve().parent.parent
JOBS = HOME / "cron" / "jobs.json"
REGISTRY = HOME / "cron" / "artifacts.json"

# Trees the fleet actually writes into. `reports/` at the top of HOME is the live
# one; the copies under openamer-agent/ and repo-tmp/ are read for discovery only,
# because a job writing into a copy is itself a finding.
#
# `cron/output/` is in here because the scheduler archives every run's stdout there,
# one directory per job - which makes it the universal "this job ran" artifact, and
# for an analysis organ (metacognition) it is the ONLY artifact: that script reads
# sessions, prints, and writes nothing else.
WATCH_ROOTS = ["reports", "memory", "darwin", "logs", ".system-snapshot",
               "scripts/training", "cron/output"]
SKIP = ("__pycache__", ".git", "node_modules", ".venv", "venv")


def load(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def snapshot() -> dict[str, float]:
    """path -> mtime for every file under the watched trees."""
    out: dict[str, float] = {}
    for root in WATCH_ROOTS:
        base = HOME / root
        if not base.is_dir():
            continue
        for p in base.rglob("*"):
            if not p.is_file() or any(s in p.parts for s in SKIP):
                continue
            try:
                out[str(p.relative_to(HOME))] = p.stat().st_mtime
            except OSError:
                continue
    return out


def job_by_name(name: str) -> dict | None:
    for j in load(JOBS, {}).get("jobs", []):
        if str(j.get("name")) == name:
            return j
    return None


def _job_enabled(job_id: str) -> bool | None:
    """True/False for a known job, None when jobs.json does not know the id.

    A PAUSED job cannot produce a fresh artifact, so an old one is not debt - it
    is the expected state. Measured 2026-10-18: 27 of 83 declarations were
    reported STALE and every one belonged to a job the curator paused on
    2026-10-14 (all at 10:22-10:23). The hourly check exited 1 on that, which is
    an alarm that says nothing an operator can act on - the same "learn to ignore
    the alarm" failure the `since` window above was added to prevent.
    Unknown ids stay judged: a declaration naming a job that no longer exists is
    a real inconsistency worth seeing.
    """
    for j in load(JOBS, {}).get("jobs", []):
        if str(j.get("id")) == job_id:
            return bool(j.get("enabled"))
    return None


def _cron_period_minutes(expr: str) -> int:
    """Roughest possible period from a 5-field cron expression.

    Only the ORDER OF MAGNITUDE matters: the window is doubled afterwards, so being
    off by a factor of two is harmless and being off by a hundred is not. Anything
    unrecognised falls back to daily.
    """
    parts = expr.split()
    if len(parts) != 5:
        return 1440
    minute, hour, dom, month, dow = parts
    if dow != "*":
        return 10080                       # weekly
    if dom != "*" or month != "*":
        return 43200                       # monthly
    # The MINUTE field decides first: `*/15 * * * *` runs every 15 minutes, and testing
    # `hour == "*"` before this returned 60 for it - caught by the test, not by reading.
    if minute.startswith("*/"):
        try:
            return max(int(minute[2:]), 1)
        except ValueError:
            return 1440
    if hour.startswith("*/"):
        try:
            return max(int(hour[2:]) * 60, 60)
        except ValueError:
            return 1440
    if hour == "*":
        return 60                          # hourly
    return 1440                            # daily


def interval_minutes(job: dict) -> int:
    """The job's cadence, read from its SCHEDULE - never from the gap between runs.

    The gap is a trap. After a long pause `next_run_at - last_run_at` measures the
    PAUSE, not the cadence, so it exceeds any sane ceiling and falls back to daily.
    Measured 2026-10-10: that gave `asi-capability-audit` (cron `0 9 * * 1`, weekly) a
    48h window, so it was reported STALE while it was simply waiting for Monday -
    fourteen false alarms, all from one wrong denominator.
    """
    sched = job.get("schedule")
    if isinstance(sched, dict):
        if sched.get("kind") == "interval":
            try:
                minutes = int(sched.get("minutes") or 0)
                if minutes > 0:
                    return minutes
            except (TypeError, ValueError):
                pass
        expr = str(sched.get("expr") or "")
        if expr:
            return _cron_period_minutes(expr)
    return 1440


def sync(registry: dict) -> int:
    """Declare every active job that has no entry yet, and refresh the generated ones.

    The artifact is `cron/output/<id>` - the scheduler's own stdout archive, which
    gets a file per run even when the script prints nothing (measured 2026-10-10 on
    `_cron_snapshot.py`, silent on success, 181 B archived). That is a WEAKER claim
    than a produced artifact: it proves the job executed, not that it did its job.
    Entries say which with `kind`, so a reader is never left guessing which of the
    two facts a green row stands for.

    `kind: "ran"` entries are generated, so their window is recomputed on every sync -
    a wrong denominator is a property of this function, not of the job. Hand-declared
    `produced` entries keep the window they were given.

    Filling the gap is the point. Before this, 7 of 84 active jobs were declared, and
    "this job did something" was unverifiable for the other 77 - which is the honest
    statement, not a comfortable one.
    """
    added = refreshed = 0
    for job in load(JOBS, {}).get("jobs", []):
        if not job.get("enabled"):
            continue
        jid = str(job.get("id") or "")
        if not jid:
            continue
        window = max(2 * interval_minutes(job) + 60, 120)
        entry = registry.get(jid)
        if isinstance(entry, dict) and entry.get("kind") == "ran":
            if entry.get("max_age_minutes") != window:
                entry["max_age_minutes"] = window
                refreshed += 1
            if not entry.get("since"):
                entry["since"] = _now_iso()      # start judging from now, not from history
                refreshed += 1
            continue
        if jid in entries(registry):
            continue
        registry[jid] = {
            "label": job.get("name"),
            "artifact": f"cron/output/{jid}",
            "max_age_minutes": window,
            "kind": "ran",
            "since": _now_iso(),
            "evidence": "generated by --sync: not individually measured. The scheduler's "
                        "stdout archive is the universal 'this job ran' artifact; it proves "
                        "execution, not that the job did its work. Refine with --discover.",
        }
        added += 1

    # An entry keyed by anything other than a job id is never matched by the loop
    # above, so `--sync` adds a SECOND entry for the same job - a duplicate that
    # looks like coverage. Caught for real on 2026-10-10: two hand-written entries
    # were keyed by job NAME, and the sync produced 83 entries for 81 active jobs.
    # Report them instead of quietly working around them.
    known = {str(j.get("id")) for j in load(JOBS, {}).get("jobs", [])}
    orphans = [k for k in entries(registry) if k not in known]
    if orphans:
        print(f"[sync] WARNING - {len(orphans)} entry key(s) are not job ids and will never "
              f"match a job: {', '.join(sorted(orphans))}")
        print("[sync] re-key them to the job's `id` (jobs.json uses `id`, not `job_id`)")
    return added, refreshed


DISCOVERY_LOG = HOME / "cron" / "artifact-discovery.jsonl"
DISCOVERY_LOCK = HOME / "cron" / ".artifact-discovery.lock"


def discover_all(limit: int, control_seconds: int = 0, exact: bool = False) -> int:
    """Run `--discover` over the still-weak (`ran`) entries, one line each.

    This is the honest way to close the gap: 70 of 81 active jobs declare only that
    they EXECUTED, and the only way to learn what one of them PRODUCES is to watch it
    work. Results are appended to `cron/artifact-discovery.jsonl` so the assigning can
    be done later, in bulk, and re-read - not held in one session's memory.

    It does NOT edit the registry. Which touched file belongs to the job is a judgement
    (the touched set always mixes in another process's writes), and a machine that
    guesses there would produce exactly the confident-but-wrong entries this whole
    exercise exists to avoid.

    **Locked, because two batches pick the same jobs.** The hourly cron and a manual run
    both read the log, both see the same queue, and both start at its head - so without a
    lock they measure the same five jobs twice and waste the hour. The lock is a file
    created exclusively; a stale one (older than the longest allowed batch) is reclaimed
    rather than left to block the organ forever.
    """
    try:
        fd = os.open(DISCOVERY_LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)
    except FileExistsError:
        try:
            age_min = (time.time() - DISCOVERY_LOCK.stat().st_mtime) / 60
        except OSError:
            age_min = 0
        if age_min < 90:
            print(f"[discover-all] another batch is running ({age_min:.0f} min in) - skipping")
            return 0
        print(f"[discover-all] reclaiming a stale lock ({age_min:.0f} min old)")
        DISCOVERY_LOCK.unlink(missing_ok=True)
        return discover_all(limit, control_seconds, exact)
    except OSError as e:
        print(f"[discover-all] cannot lock: {e}")
        return 1

    try:
        return _discover_all_locked(limit, control_seconds, exact)
    finally:
        DISCOVERY_LOCK.unlink(missing_ok=True)


def _trace_exact(script: Path) -> tuple[int, list[str], str]:
    """Run a script under the audit hook; return (rc, writes, output) - HOME-relative paths.

    The hook covers the whole process tree (the destination is handed down through the
    environment and `_tracesite/sitecustomize.py` reinstalls it in every child), so a job
    that shells out to another script is traced too. Measured 2026-10-10: before child
    tracing, 4 of 10 declared artifacts came back unobservable.

    `output` is the script's own stdout+stderr, and it is NOT decoration: the first version
    of this discarded it, so `Repo-Auto-Commit` reported "wrote nothing" with no way to see
    that it had printed a reason and returned early. A measurement that hides what the
    measured thing said is the same blindness this whole file exists to remove.

    Output is JSONL - one write record per line, then a final `{"rc": N}`.
    """
    tracer = HOME / "scripts" / "_trace_writes.py"
    out = HOME / "cron" / f"_trace_{os.getpid()}.jsonl"
    out.unlink(missing_ok=True)
    try:
        run = subprocess.run([sys.executable, str(tracer), str(script), str(out)],
                             capture_output=True, cwd=str(HOME), timeout=900, check=False)
        lines = out.read_text(encoding="utf-8", errors="replace").splitlines()
        output = (run.stdout or b"").decode("utf-8", "replace") + \
                 (run.stderr or b"").decode("utf-8", "replace")
    except (subprocess.TimeoutExpired, OSError):
        return -1, [], ""
    finally:
        out.unlink(missing_ok=True)

    rc = 0
    seen: set[str] = set()
    for line in lines:
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if "rc" in row:
            rc = int(row["rc"])
            continue
        write = str(row.get("w") or "")
        if not write:
            continue
        try:
            seen.add(str(Path(write).relative_to(HOME)))
        except ValueError:
            continue                     # outside OPENAMER_HOME: not an artifact here
    return rc, sorted(seen), " ".join(output.split())


def discover_exact(name: str) -> int:
    """Record every file a job's script OPENS FOR WRITING - a fact, not an inference.

    `--discover` watches the trees and diffs; that measured poorly on 55 jobs (Darwin's
    continuous churn dominates every window). This asks the script instead, so the answer
    is what was requested of the OS rather than a guess about what changed while it ran.
    The hook covers the process tree, so a wrapper's child script is traced too.
    """
    job = job_by_name(name)
    if not job:
        print(f"no job named {name!r}")
        return 1
    script = _script_path(job)
    if script is None:
        print(f"{name} has no usable script (an LLM job writes no artifact)")
        return 1

    print(f"[exact] {name}: running {job.get('script')} under an audit hook ...")
    rc, writes, output = _trace_exact(script)
    if rc == -1:
        print("[exact] the tracer produced nothing after 900s or could not write")
        return 1

    print(f"[exact] rc={rc}  wrote {len(writes)} file(s) - exact, no environment noise")
    for w in writes[:25]:
        print(f"    {w}")
    if not writes:
        print("    (nothing opened for writing - it may hand the work to a non-Python child)")
    if output:
        print(f"    it said: {output[:200]}")
    return 0


def verify_produced(limit: int = 0) -> int:
    """Check that a `produced` job actually writes the artifact it declares.

    The gap this closes: `--discover-all` only walks the weak `ran` entries, so a
    hand-declared `produced` entry was never re-measured by anything. One was already
    wrong when this was written - `swarm-intelligence-cycle` declared `darwin/swarm.json`
    and the audit hook showed it writes `memory/swarm/swarm_state.json`. A declaration
    nothing checks is a claim, not a fact, and this file exists because of exactly that.

    Reports mismatches; does NOT edit the registry. Which file to substitute is a
    judgement (a job can write several), and the point is to surface the wrong ones.
    """
    registry = load(REGISTRY, {})
    by_id = {str(j.get("id")): j for j in load(JOBS, {}).get("jobs", []) if j.get("enabled")}
    todo = [(jid, spec) for jid, spec in sorted(entries(registry).items())
            if spec.get("kind", "produced") == "produced" and jid in by_id]
    todo = todo[:limit] if limit > 0 else todo

    print(f"[verify-produced] checking {len(todo)} declared artifact(s) against what the "
          f"script actually writes")
    bad = unobserved = 0
    for jid, spec in todo:
        script = _script_path(by_id[jid])
        if script is None:
            print(f"  NO-SCRIPT   {spec.get('label', jid)}")
            continue
        rc, writes, output = _trace_exact(script)
        declared = str(spec["artifact"]).replace("/", "\\")
        hit = any(w.replace("/", "\\") == declared or w.replace("/", "\\").startswith(
            declared.rstrip("\\") + "\\") for w in writes)
        note = "" if rc == 0 else f"  (rc={rc})"

        if hit:
            print(f"  OK          {str(spec.get('label'))[:34]:36s} {declared}{note}")
        elif not writes:
            # INCONCLUSIVE, not wrong. Python children ARE traced (the destination is handed
            # down through the environment), so zero writes now means the work went to a
            # NON-Python child - a .cmd, a shell script, another interpreter - or the job
            # genuinely writes nothing. Reporting that as a bad declaration would "fix" a
            # correct entry on the strength of a limitation of the measurement.
            # Measured 2026-10-10: child tracing took this from 4 jobs to 1.
            unobserved += 1
            print(f"  UNOBSERVED  {str(spec.get('label'))[:34]:36s} {declared}{note}")
            if output:
                # What the job said, when it said anything. Its absence was the whole
                # reason `Repo-Auto-Commit` looked like a mystery instead of an early exit.
                print(f"              it said: {output[:180]}")
        else:
            bad += 1
            print(f"  MISMATCH    {str(spec.get('label'))[:34]:36s} declared {declared}{note}")
            print(f"              it wrote instead: {', '.join(writes[:4])}")
    print(f"[verify-produced] {len(todo) - bad - unobserved} confirmed, {bad} mismatched, "
          f"{unobserved} unobservable (child process)")
    return 1 if bad else 0


def _discover_all_locked(limit: int, control_seconds: int, exact: bool = False) -> int:
    registry = load(REGISTRY, {})
    by_id = {str(j.get("id")): j for j in load(JOBS, {}).get("jobs", []) if j.get("enabled")}
    # Resumable: skip what has already been measured the way we now measure.
    #
    # "Measured" means `method == "exact"`. A diff-based record cannot tell a job's writes
    # from its neighbours' - 78 touched files for `rsi-objective-gate` against one real
    # one - so those come round again. This is deliberately a re-measure, not a migration:
    # the earlier pass produced entries in the registry, and one of them
    # (`swarm-intelligence-cycle` -> `darwin/swarm.json`) was already found to be the wrong
    # file by the exact method. A cheaper "only do the new ones" rule would leave that lie
    # in place.
    wanted = "exact" if exact else "diff"
    already = set()
    if DISCOVERY_LOG.exists():
        for line in DISCOVERY_LOG.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if row.get("method") == wanted or (not exact and int(row.get("control_seconds") or 0) > 0):
                already.add(str(row.get("job_id")))
    todo = [jid for jid, spec in entries(registry).items()
            if spec.get("kind", "produced") == "ran" and jid in by_id and jid not in already]
    todo = todo[:limit] if limit > 0 else todo
    print(f"[discover-all] {len(todo)} job(s) to run ({len(already)} already recorded)")

    done = 0
    for jid in todo:
        job = by_id[jid]
        script = _script_path(job)
        if script is None:
            continue
        rc, touched, ambient = _run_and_diff(script, control_seconds)
        own = [x for x in touched if x not in ambient]
        method = "diff"
        if exact:
            rc, own, output = _trace_exact(script)
            touched, ambient, method = list(own), [], "exact"

        record = {"job_id": jid, "label": job.get("name"), "script": job.get("script"),
                  "rc": rc, "touched": touched, "ambient": ambient, "own": own,
                  "output": output, "control_seconds": control_seconds, "method": method}
        with DISCOVERY_LOG.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")

        print(f"  rc={rc:<4} {str(job.get('name'))[:34]:36s} "
              f"[{method:5s}] eigen {len(own):>3}")
        for x in own[:6]:
            print(f"        {x}")
        done += 1
    print(f"[discover-all] {done} job(s) recorded in {DISCOVERY_LOG.name}")
    return 0


def entries(registry: dict) -> dict:
    """Declared jobs only. Keys starting with '_' are notes, not entries.

    The registry carries `_note` / `_why` strings for a human reader, and treating
    every top-level value as a spec made the checker crash on its own documentation
    (caught 2026-10-10 by running it rather than by reading it).
    """
    return {k: v for k, v in registry.items()
            if not k.startswith("_") and isinstance(v, dict)}


def _now_iso() -> str:
    """Local ISO timestamp, naive - the same frame `last_run_at` is written in."""
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def _heartbeat_freshness(job_id: str) -> float | None:
    """Freshness of a native-heartbeat-owned job, or None when the job is not owned.

    A job handed to the ASI heartbeat has its cron entry retired, so the scheduler
    stops writing ``cron/output/<id>`` — the archive freezes, and judging the job by
    that file reports STALE forever. Measured 2026-10-11: 16 such rows, every id
    listed in ``memory/heartbeat-own.enabled``, while the engine had run the matching
    script minutes earlier (``cron/output/0ccce21c5738`` 3.0h old vs the engine's
    ``cron_mesh_daemon.py`` run 0.05h ago). The executor's own state is the right
    witness: map the job to its script and read that script's last run out of
    ``memory/asi_heartbeat.json``.
    """
    try:
        owned = {
            ln.strip()
            for ln in (HOME / "memory" / "heartbeat-own.enabled")
            .read_text(encoding="utf-8", errors="replace")
            .splitlines()
            if ln.strip() and not ln.strip().startswith("#")
        }
    except OSError:
        return None
    if not owned:
        return None

    job = next(
        (j for j in (load(JOBS, {}).get("jobs") or []) if str(j.get("id")) == job_id),
        None,
    )
    if job is None:
        return None
    if job_id not in owned and str(job.get("name") or "") not in owned:
        return None
    base = str(job.get("script") or "").replace("\\", "/").rsplit("/", 1)[-1]
    if not base:
        return None

    state = load(HOME / "memory" / "asi_heartbeat.json", {}) or {}
    for sub in (state.get("subsystems") or {}).values():
        for script, ts in (sub.get("scripts") or {}).items():
            if ts and script.replace("\\", "/").rsplit("/", 1)[-1] == base:
                return float(ts)
    return None


_STATE = HOME / "logs" / "artifact-debt-check.state.json"


def _machine_downtime_minutes() -> float:
    """How long this machine was away since the previous check ran.

    The check is scheduled hourly. If its OWN previous run is far older than
    that, the machine was asleep or switched off — and then every artifact is
    "old" without a single job being broken. Measured 2026-11-19: a 15.3h
    standby produced five STALE rows for jobs that had simply not been given a
    chance to run. An alarm that fires when the machine was off teaches you to
    ignore the alarm, which is the one thing this registry must not do.

    The 90-minute grace covers scheduler jitter; only the excess counts as
    downtime.
    """
    try:
        prev = json.loads(_STATE.read_text(encoding="utf-8"))
        last = float(prev.get("last_run") or 0)
    except (OSError, ValueError, json.JSONDecodeError):
        return 0.0
    if not last:
        return 0.0
    gap_min = (time.time() - last) / 60
    return max(0.0, gap_min - 90.0)


def _record_own_run() -> None:
    try:
        _STATE.parent.mkdir(parents=True, exist_ok=True)
        _STATE.write_text(json.dumps({"last_run": time.time()}), encoding="utf-8")
    except OSError:
        pass


def check(registry: dict, skipped: "list[str] | None" = None,
          downtime_min: float = 0.0) -> list[str]:
    """Return one line per job whose artifact is missing or older than declared.

    Declarations whose job is paused are skipped (and recorded in `skipped` when
    the caller passes a list): the job is off, so an old artifact is the expected
    state, not debt. A declaration is kept, not deleted, because it becomes
    binding again the moment the job is resumed.

    An entry carrying `since` is not judged until a full window has elapsed since it
    was declared. A job enabled at noon with a six-hour cadence has not MISSED
    anything at 12:05 - its archive is old because it was off, not because it is
    broken. Measured 2026-10-10: without this, enabling the fleet produced 17 rows
    that were all history, and an alarm that fires on "no chance yet" is how you
    learn to ignore the alarm.
    """
    problems = []
    now = time.time()
    for job_id, spec in sorted(entries(registry).items()):
        if _job_enabled(job_id) is False:
            if skipped is not None:
                skipped.append(spec.get("label", job_id))
            continue
        art = HOME / spec["artifact"]
        limit = spec.get("max_age_minutes", 1440)
        since = spec.get("since")
        if since:
            try:
                watched_min = (now - time.mktime(time.strptime(since, "%Y-%m-%dT%H:%M:%S"))) / 60
                if watched_min < limit:
                    continue
            except ValueError:
                pass
        hb_ts = _heartbeat_freshness(job_id)
        if hb_ts is not None:
            # Native-heartbeat-owned job: the cron archive is frozen because the
            # scheduler is no longer the executor. Judge the engine's own state.
            # Only awake time counts: a standby is not a dead job.
            age_min = max(0.0, (now - hb_ts) / 60 - downtime_min)
            if age_min > limit:
                problems.append(f"STALE    {spec.get('label', job_id):38s} {spec['artifact']} "
                                f"({age_min / 60:.1f}h > {limit / 60:.1f}h) [heartbeat]")
            problems.extend(_content_problems(spec, job_id, art))
            continue
        if not art.exists():
            problems.append(f"MISSING  {spec.get('label', job_id):38s} {spec['artifact']}")
            continue
        newest = art.stat().st_mtime
        if art.is_dir():
            kids = [p.stat().st_mtime for p in art.rglob("*") if p.is_file()]
            if not kids:
                problems.append(f"EMPTY    {spec.get('label', job_id):38s} {spec['artifact']}/")
                continue
            newest = max(kids)
        age_min = max(0.0, (now - newest) / 60 - downtime_min)
        if age_min > limit:
            problems.append(f"STALE    {spec.get('label', job_id):38s} {spec['artifact']} "
                            f"({age_min / 60:.1f}h > {limit / 60:.1f}h)")
        problems.extend(_content_problems(spec, job_id, art))
    return problems


def _content_problems(spec: dict, job_id: str, art: Path) -> list[str]:
    """A fresh artifact can still say the organ failed.

    Measured 2026-10-10: `Repo-Auto-Commit` rewrote `memory/repo-autocommit.json` every
    run - never stale for a second - while every record inside it read
    `commit_but_push_failed`. Its commits had not reached GitHub for hours and the
    freshness check was perfectly happy, because a file can be new AND be a record of
    failure. An entry declares what must not appear in it.
    """
    patterns = (spec.get("expect") or {}).get("must_not_contain") or []
    if not patterns or not art.is_file():
        return []
    try:
        text = art.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    hits = [p for p in patterns if p in text]
    if not hits:
        return []
    found = ", ".join(repr(h) for h in hits)
    return [(f"CONTENT  {spec.get('label', job_id):38s} {spec['artifact']} "
             f"contains {found} - fresh, and it says it failed")]


def _script_path(job: dict) -> Path | None:
    """Where the job's script lives, or None when it has none / it is missing.

    Shared by `discover` and `discover_all`: both need it, and a second copy is how the
    two would drift apart.
    """
    script = str(job.get("script") or "")
    if not script:
        return None
    p = Path(script.replace("\\", "/"))
    if not p.is_absolute():
        p = HOME / "scripts" / script
    return p if p.is_file() else None


def _run_and_diff(script: Path, control_seconds: int = 0) -> tuple[int, list[str], list[str]]:
    """Run a job's script and report what it touched - with an ambient control.

    Returns (rc, touched, ambient).

    The problem this solves, measured 2026-10-10: `--discover` watched the file trees
    while the script ran, but the fleet runs eleven other processes at the same time, so
    the touched set was the job's writes MIXED WITH everyone else's. Of eight candidate
    artifacts only four belonged to one job - the other four appeared in two to four
    jobs' sets, which makes them shared, not owned, and assigning them would have been a
    guess dressed as a measurement. That is exactly the failure this whole exercise
    exists to prevent.

    `control_seconds > 0` takes a baseline FIRST: sit idle for that long and record what
    changed on its own. Those files are ambient. What the job touched minus what changed
    while nobody was doing anything is a far better answer to "what does this job write".
    It is the same two-sample logic as the `since` window: measure the world, then measure
    the thing, and keep the difference.
    """
    if control_seconds > 0:
        base = snapshot()
        time.sleep(control_seconds)
        ambient = sorted(x for x, m in snapshot().items() if base.get(x) != m)
    else:
        ambient = []

    before = snapshot()
    try:
        rc = subprocess.run([sys.executable, str(script)], capture_output=True, timeout=900,
                            cwd=str(HOME), check=False).returncode
    except subprocess.TimeoutExpired:
        rc = -1
    after = snapshot()

    # A file that did not exist before counts as touched: before.get() is None, so it
    # differs from every real mtime. No separate "added" list, and no set() on the way
    # out - `after` is already a dict.
    touched = sorted(x for x, m in after.items() if before.get(x) != m)
    return rc, touched, ambient


def discover(name: str, control_seconds: int = 0) -> int:
    job = job_by_name(name)
    if not job:
        print(f"no job named {name!r}")
        return 1
    script = _script_path(job)
    if script is None:
        print(f"{name} has no usable script (an LLM job writes no artifact)")
        return 1

    print(f"[discover] {name}: running {job.get('script')} ...")
    rc, touched, ambient = _run_and_diff(script, control_seconds)
    if rc == -1:
        print("[discover] timed out after 900s - no artifact report")
        return 1

    own = [x for x in touched if x not in ambient]
    print(f"[discover] rc={rc}  touched {len(touched)}  ambient {len(ambient)}  "
          f"own {len(own)} file(s)")
    for path in own[:20]:
        print(f"    {path}")
    if ambient:
        print(f"    -- and {len(ambient)} changed with nobody acting (ambient, not this job's)")
    if not own:
        print("    (nothing attributable to this job under the watched trees)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--registry", default=str(REGISTRY))
    ap.add_argument("--discover", default="", help="run this job's script and report what it wrote")
    ap.add_argument("--discover-exact", default="",
                    help="run this job's script under an audit hook and report its own writes "
                         "(exact attribution; covers the whole process tree)")
    ap.add_argument("--discover-all", action="store_true",
                    help="run every still-weak (`ran`) job's script and log what it touched")
    ap.add_argument("--limit", type=int, default=0,
                    help="with --discover-all: how many jobs to run this time (0 = all)")
    ap.add_argument("--exact", action="store_true",
                    help="with --discover-all: use the audit hook instead of the tree diff "
                         "(exact attribution across the process tree)")
    ap.add_argument("--control", type=int, default=0,
                    help="seconds of idle baseline taken before each run; files that change "
                         "with nobody acting are ambient, not the job's")
    ap.add_argument("--verify-produced", action="store_true",
                    help="check every `produced` declaration against what its script "
                         "actually writes (audit hook); reports mismatches, edits nothing")
    ap.add_argument("--sync", action="store_true",
                    help="declare every active job that has no entry yet (writes the registry)")
    ap.add_argument("--list", action="store_true", help="print the registry and exit")
    ap.add_argument("--verbose", action="store_true",
                    help="also report declarations that were skipped because the job is paused")
    args = ap.parse_args()

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass

    if args.discover:
        return discover(args.discover, args.control)

    if args.discover_exact:
        return discover_exact(args.discover_exact)

    if args.verify_produced:
        return verify_produced()

    if args.discover_all:
        # 45 s of baseline by default: enough to catch the fleet's own churn, short
        # enough that five jobs an hour still fit in an hour.
        return discover_all(args.limit, args.control or 45, args.exact)

    registry_path = Path(args.registry)
    registry = load(registry_path, {})

    if args.sync:
        added, refreshed = sync(registry)
        registry_path.write_text(json.dumps(registry, indent=2, ensure_ascii=False) + "\n",
                                 encoding="utf-8")
        total = len(entries(registry))
        print(f"[sync] declared {added} new, refreshed {refreshed} window(s); {total} of "
              f"{len([j for j in load(JOBS, {}).get('jobs', []) if j.get('enabled')])} active "
              f"jobs now carry an artifact")
        return 0

    if not registry:
        print(f"no registry at {args.registry} - nothing declared, which is the finding")
        return 1
    if args.list:
        for job_id, spec in sorted(entries(registry).items(), key=lambda kv: kv[1].get("label") or ""):
            kind = spec.get("kind", "produced")
            print(f"  {kind:9s} {(spec.get('label') or job_id)[:34]:36s} "
                  f"{spec['artifact']:44s} max {spec.get('max_age_minutes', 1440):>5} min")
        return 0

    skipped: list[str] = []
    down = _machine_downtime_minutes()
    problems = check(registry, skipped, downtime_min=down)
    _record_own_run()
    if not problems:
        if down >= 60 and args.verbose:
            print(f"machine was away for ~{down / 60:.1f}h since the last check; "
                  "artifact ages were measured against awake time")
        if skipped and args.verbose:
            print(f"{len(skipped)} declaration(s) skipped: their job is paused "
                  f"({len(registry)} declared, {len(registry) - len(skipped)} judged)")
        return 0                      # all judged artifacts are present and fresh
    print(f"{len(problems)} of {len(registry) - len(skipped)} judged declared artifacts "
          f"are not what the job promised:")
    for line in problems:
        print("  " + line)
    if skipped:
        print(f"  (+{len(skipped)} declaration(s) skipped: their job is paused)")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
