"""Self-critique — an adversarial audit of my own claims about myself.

Not a second self-model: a machine that looks for the ways THIS system quietly
lies to itself. Every check here exists because it actually happened on
2026-11-06, and in each case the lie was invisible until someone compared what
was ASKED with what was PRODUCED:

  * `native_map` pointed at package paths that could not exist, so four
    "native" subsystems silently ran as subprocesses — and `cognition` ran a
    script that does not exist at all.
  * the heartbeat persisted only timestamps, so an organ failing on every tick
    looked identical to a healthy one.
  * the desire engine named goals with home-relative paths; the executor's
    resolver matches absolute paths only, so the goal could never produce the
    artifact its own verify checked (43 of the last 60 failures).
  * `si_learner.py` belonged to no subsystem, so the lessons the executor
    prompted itself with were three weeks old.
  * three subsystems were reporting `ok` while their own state file froze.

The honest boundary is printed with every run: a check that cannot measure says
SKIPPED, never "fine". Silence is not a verdict.

Pure stdlib, no network, no LLM. Every finding carries the file and value it came
from, so a reader can reproduce it instead of trusting the tool.
"""

from __future__ import annotations

import datetime
import json
from pathlib import Path
from typing import Any

CRITICAL = "critical"
WARNING = "warning"
INFO = "info"

ZOMBIE_GOAL_MINUTES = 120


def _home() -> Path:
    import os

    env = os.environ.get("OPENAMER_HOME", "").strip()
    if env:
        return Path(env)
    base = Path.home() / "AppData" / "Local"
    for cand in (base / "openamer", base / "openamer-laptop"):
        if (cand / "memory").is_dir():
            return cand
    return base / "openamer"


HOME = _home()


def _read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _age_minutes(path: Path) -> float | None:
    try:
        return (datetime.datetime.now().timestamp() - path.stat().st_mtime) / 60.0
    except Exception:
        return None


def finding(severity: str, kind: str, subject: str, detail: str, evidence: str) -> dict:
    return {"severity": severity, "kind": kind, "subject": subject,
            "detail": detail, "evidence": evidence}


# ---------------------------------------------------------------------------
# 1. Dead organs: nothing runs this file any more
# ---------------------------------------------------------------------------

def check_dead_organs(home: Path) -> tuple[list[dict], str | None]:
    """A retired cron job whose script no subsystem picked up is a dead organ.

    This is how three organs were found today — by accident. A sweep is the
    method. Retirement is supposed to hand a loop over to the heartbeat (see
    `_reconcile_scripts`); if the handoff was never wired, the organ simply stops
    and every other surface still reports healthy.
    """
    jobs = _read_json(home / "cron" / "jobs.json", None)
    state = _read_json(home / "memory" / "asi_heartbeat.json", None)
    if jobs is None or state is None:
        return [], "cron/jobs.json or memory/asi_heartbeat.json unreadable"
    jobs = jobs if isinstance(jobs, list) else jobs.get("jobs", [])
    if not isinstance(state, dict) or not isinstance(state.get("subsystems"), dict):
        return [], "asi_heartbeat.json has no subsystems block"

    owned = set()
    for sub in state["subsystems"].values():
        if isinstance(sub, dict):
            for script in (sub.get("scripts") or {}):
                owned.add(Path(str(script)).name)

    out = []
    for job in jobs:
        if not isinstance(job, dict):
            continue
        script = str(job.get("script") or "").strip()
        if not script or job.get("enabled", True):
            continue
        name = Path(script.split()[0]).name
        if name in owned:
            continue
        out.append(finding(
            WARNING, "dead-organ", str(job.get("name") or name),
            f"cron job is disabled and no heartbeat subsystem owns {name} â€” "
            f"nothing runs it (retired-and-unreviewed: either hand it over to a "
            f"subsystem or record why it is obsolete)",
            f"cron/jobs.json: enabled=false, script={script}",
        ))
    return out, None


# ---------------------------------------------------------------------------
# 2. Silent failures: an organ that failed on its last tick
# ---------------------------------------------------------------------------

def check_silent_failures(home: Path) -> tuple[list[dict], str | None]:
    state = _read_json(home / "memory" / "asi_heartbeat.json", None)
    if not isinstance(state, dict) or not isinstance(state.get("subsystems"), dict):
        return [], "asi_heartbeat.json has no subsystems block"
    out = []
    for name, sub in state["subsystems"].items():
        if not isinstance(sub, dict):
            continue
        last = sub.get("last_result") or {}
        fails = sub.get("consecutive_failures") or 0
        if isinstance(last, dict) and last.get("ok") is False:
            out.append(finding(
                CRITICAL, "silent-failure", str(name),
                f"last tick failed ({last.get('script')}): {str(last.get('detail'))[:120]}",
                "memory/asi_heartbeat.json: last_result.ok=false",
            ))
        elif fails:
            out.append(finding(
                WARNING, "repeated-failure", str(name),
                f"{fails} consecutive failed ticks",
                "memory/asi_heartbeat.json: consecutive_failures",
            ))
    return out, None


# ---------------------------------------------------------------------------
# 3. Cron jobs that are red right now
# ---------------------------------------------------------------------------

def check_failing_crons(home: Path) -> tuple[list[dict], str | None]:
    jobs = _read_json(home / "cron" / "jobs.json", None)
    if jobs is None:
        return [], "cron/jobs.json unreadable"
    jobs = jobs if isinstance(jobs, list) else jobs.get("jobs", [])
    out = []
    for job in jobs:
        if not isinstance(job, dict) or not job.get("enabled", True):
            continue
        if str(job.get("last_status")) != "error":
            continue
        err = str(job.get("last_error") or "").strip().splitlines()
        out.append(finding(
            CRITICAL, "failing-cron", str(job.get("name")),
            (err[0][:140] if err else "last_status=error"),
            "cron/jobs.json: last_status=error",
        ))
    return out, None


# ---------------------------------------------------------------------------
# 4. Zombie goals: accepted by the executor, never finished
# ---------------------------------------------------------------------------

def check_zombie_goals(home: Path) -> tuple[list[dict], str | None]:
    goals = _read_json(home / "memory" / "si" / "goals.json", None)
    if goals is None:
        return [], "memory/si/goals.json unreadable"
    if not isinstance(goals, list):
        return [], "goals.json is not a list"
    now = datetime.datetime.now(datetime.timezone.utc)
    out = []
    for goal in goals:
        if not isinstance(goal, dict) or goal.get("status") != "active":
            continue
        created = str(goal.get("created") or "")
        try:
            ts = datetime.datetime.fromisoformat(created)
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=datetime.timezone.utc)
        except Exception:
            continue
        age = (now - ts).total_seconds() / 60.0
        if age > ZOMBIE_GOAL_MINUTES:
            out.append(finding(
                WARNING, "zombie-goal", str(goal.get("id")),
                f"active for {age:.0f} min: {str(goal.get('desc'))[:90]}",
                f"memory/si/goals.json: created={created}",
            ))
    return out, None


# ---------------------------------------------------------------------------
# 5. Stale evidence: a file whose whole job is to be fresh
# ---------------------------------------------------------------------------

# path fragment -> (max age minutes, why it must be fresh)
STALENESS_RULES = {
    "memory/si/lessons.json": (180, "the executor prompts itself with these; stale "
                                   "lessons train it on obsolete failure modes"),
    "memory/self_model/desires.json": (90, "the will cycle writes every 30 min"),
    "memory/asi_heartbeat.json": (30, "the heartbeat ticks at least every 15 min"),
    "logs/suite-verdict.json": (60 * 24 * 14, "evidence for DIR-05"),
}


def check_stale_evidence(home: Path) -> tuple[list[dict], str | None]:
    out = []
    missing = []
    for rel, (max_age, why) in STALENESS_RULES.items():
        path = home / rel
        age = _age_minutes(path)
        if age is None:
            missing.append(rel)
            continue
        if age > max_age:
            out.append(finding(
                CRITICAL, "stale-evidence", rel,
                f"{age / 60:.1f} h old (limit {max_age / 60:.1f} h) — {why}",
                f"{path} mtime",
            ))
    note = None
    if missing:
        note = "no file yet: " + ", ".join(missing)
    return out, note


# ---------------------------------------------------------------------------
# 6. Contradictions in the self-model: reported vs freshly counted
# ---------------------------------------------------------------------------

def check_self_model_contradictions(home: Path) -> tuple[list[dict], str | None]:
    state = _read_json(home / "memory" / "self_model" / "current_state.json", None)
    if not isinstance(state, dict) or not state:
        return [], "current_state.json unreadable"
    checks: list[tuple[str, int, int, str]] = []

    reported = state.get("memory_episodes")
    fresh = sum(1 for _ in _iter_lines(home / "memory" / "longterm_episodes.jsonl"))
    if isinstance(reported, int) and fresh:
        checks.append(("memory_episodes", reported, fresh,
                       "memory/longterm_episodes.jsonl"))

    reported_wm = state.get("world_model_edges", state.get("world_model_lines"))
    fresh_wm = sum(1 for _ in _iter_lines(home / "memory" / "world_model.jsonl"))
    if isinstance(reported_wm, int) and fresh_wm:
        checks.append(("world_model_edges", reported_wm, fresh_wm,
                       "memory/world_model.jsonl"))

    reported_tools = state.get("tools")
    names = state.get("tool_names")
    if isinstance(reported_tools, int) and isinstance(names, list) and names:
        checks.append(("tools", reported_tools, len(names),
                       "current_state.json:tool_names"))

    if not checks:
        return [], "no cross-checkable count in the self-model"
    out = []
    for field, said, counted, source in checks:
        drift = abs(said - counted)
        if drift == 0:
            continue
        # A count that grew after the self-model's last hourly run is LAG, not a
        # lie: 873 vs 874 was the world model gaining one edge in between. Calling
        # that a contradiction would train the reader to ignore the report. Only a
        # drift larger than both a small absolute slack and 1 % is a finding.
        lagging = drift <= max(5, counted * 0.01)
        out.append(finding(
            INFO if lagging else WARNING,
            "self-model-lagging" if lagging else "self-model-contradiction",
            field,
            f"reports {said}, the source has {counted} (drift {drift}"
            + (", consistent with refresh order)" if lagging else ")"),
            source,
        ))
    return out, None


def _iter_lines(path: Path):
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            yield from fh
    except Exception:
        return


CHECKS = (
    ("dead organs", check_dead_organs),
    ("silent failures", check_silent_failures),
    ("failing crons", check_failing_crons),
    ("zombie goals", check_zombie_goals),
    ("stale evidence", check_stale_evidence),
    ("self-model contradictions", check_self_model_contradictions),
)


def audit(home: Path | None = None) -> dict:
    """Run every check. Returns findings, the skipped list, and a verdict."""
    home = home or HOME
    findings: list[dict] = []
    skipped: list[dict] = []
    ran = 0
    for label, check in CHECKS:
        try:
            got, note = check(home)
        except Exception as exc:  # a broken check is a skip, never a pass
            skipped.append({"check": label, "reason": f"raised: {exc}"})
            continue
        if note:
            # A check that could not read its source did NOT run; counting it
            # would let a broken environment look like full coverage.
            skipped.append({"check": label, "reason": note})
            continue
        findings.extend(got)
        ran += 1

    order = {CRITICAL: 0, WARNING: 1, INFO: 2}
    findings.sort(key=lambda f: (order.get(f["severity"], 3), f["kind"], f["subject"]))
    counts = {sev: sum(1 for f in findings if f["severity"] == sev)
              for sev in (CRITICAL, WARNING, INFO)}
    return {
        "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "home": str(home),
        "checks_ran": ran,
        "checks_total": len(CHECKS),
        "skipped": skipped,
        "counts": counts,
        "findings": findings,
        "verdict": "critical" if counts[CRITICAL] else
                   ("warning" if counts[WARNING] else "clean"),
    }


def render(report: dict) -> str:
    """Human-readable report. Silence is never success: skips are printed."""
    lines = []
    c = report["counts"]
    lines.append(f"Self-critique — {report['ts'][:19]}")
    lines.append(f"  {report['checks_ran']}/{report['checks_total']} checks ran | "
                 f"{c[CRITICAL]} critical, {c[WARNING]} warning, {c[INFO]} info")
    if not report["findings"]:
        lines.append("  no findings")
    for f in report["findings"]:
        mark = {CRITICAL: "!!", WARNING: " !", INFO: "  "}.get(f["severity"], "  ")
        lines.append(f"{mark} [{f['kind']}] {f['subject']}: {f['detail']}")
        lines.append(f"       evidence: {f['evidence']}")
    for s in report["skipped"]:
        lines.append(f"?? [{s['check']}] SKIPPED — {s['reason']}")
    lines.append(f"  verdict: {report['verdict']}")
    return "\n".join(lines)