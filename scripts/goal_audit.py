#!/usr/bin/env python3
"""Audit the strategic goals for the thing every goal needs: a way to die.

Measured 2026-11-18 on this install: 5 goals, 26 milestones, and **15 milestones
had already been reverted at least once** — `asi_capability` had 6 of 6. Progress
sat at 0.0-0.5 while every milestone carried `verify_evidence`, so the system was
verifying diligently and moving nowhere. Nothing in the store could express "stop
this goal" — there was no kill criterion field at all.

A goal without a kill criterion is not ambition, it is a treadmill: the verifier
reverts a claim, the next tick re-promotes it, and the count of cycles grows
while the state stays the same. This audit names that pattern per goal:

    TREADMILL     a milestone was promoted and then reverted (a cycle)
    STALLED       no verify_ts newer than --stale-days
    NO_KILL       the goal declares no `kill_if` (the structural finding)
    ON_TRACK      verified milestones exist, none of the above

    python scripts/goal_audit.py                 # table + reports/goal-audit.json
    python scripts/goal_audit.py --json          # machine-readable only
    python scripts/goal_audit.py --stale-days 7

Exit 1 when any goal is TREADMILL or STALLED (so a cron can act on it), 0 when
every goal is ON_TRACK or only structurally NO_KILL.

Adopting a kill criterion is one edit in `memory/strategic_goals.json`:

    "kill_if": {"text": "no milestone promoted in 30 days",
                "review_by": "2026-12-18"}

The audit reads `kill_if.text` and dates; it never invents the threshold.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

HOME = Path(os.environ.get("OPENAMER_HOME")
            or (Path.home() / "AppData" / "Local" / "openamer-laptop"))
STORE = HOME / "memory" / "strategic_goals.json"
REPORT = HOME / "reports" / "goal-audit.json"


def parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


def now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def audit_goal(goal: dict, stale_days: float) -> dict:
    ms = goal.get("milestones") or []
    verified = [m for m in ms if m.get("verified")]
    reverted = [m for m in ms if m.get("reverted_at")]

    # The store keeps only the LAST revert per milestone, so counting reverts per
    # id can never exceed 1 — the first version of this audit therefore reported
    # "0 hard findings" while the raw data showed 6 of 6 milestones reverted in
    # asi_capability. The signal that exists is the CYCLE: a milestone that was
    # promoted (promoted_by set) AND later reverted, and a goal whose share of
    # reverted milestones is at least half.
    cycles = [m["id"] for m in ms if m.get("promoted_by") and m.get("reverted_at")]
    revert_share = (len(reverted) / len(ms)) if ms else 0.0
    treadmill = cycles if (cycles or revert_share >= 0.5) else []

    stamps = [parse_ts(m.get("verify_ts")) for m in ms]
    stamps = [s for s in stamps if s]
    last_verify = max(stamps) if stamps else parse_ts(goal.get("created"))
    staleness_days = (now() - last_verify).days if last_verify else None

    created = parse_ts(goal.get("created"))
    target = parse_ts(goal.get("target_date"))
    days_left = (target - now()).days if target else None
    progress = goal.get("progress")
    pace = None
    if isinstance(progress, (int, float)) and days_left and days_left > 0:
        pace = round((1.0 - progress) / days_left, 4)  # progress points per day needed
    age_days = (now() - created).days if created else None

    kill = goal.get("kill_if") or {}
    kill_text = (kill.get("text") or "").strip()
    kill_review = parse_ts(kill.get("review_by"))
    kill_overdue = bool(kill_review and kill_review < now())

    verdicts = []
    if treadmill:
        verdicts.append("TREADMILL")
    if staleness_days is not None and staleness_days > stale_days:
        verdicts.append("STALLED")
    if not kill_text:
        verdicts.append("NO_KILL")
    if kill_overdue:
        verdicts.append("KILL_REVIEW_OVERDUE")
    if not verdicts:
        verdicts.append("ON_TRACK")

    suggestion = ""
    if "TREADMILL" in verdicts:
        worst = treadmill[0]
        text = next((m["text"] for m in ms if m["id"] == worst), worst)
        suggestion = (f'kill_if: "milestone {worst} ({text[:60]}) promoted and reverted '
                      f'again without a new approach"')
    elif "STALLED" in verdicts:
        suggestion = (f'kill_if: "no milestone promoted in {int(stale_days) + 1} days"')

    return {
        "id": goal.get("id"),
        "status": goal.get("status"),
        "progress": progress,
        "milestones": len(ms),
        "verified": len(verified),
        "reverted": len(reverted),
        "reverted_share": round(revert_share, 2),
        "treadmill_milestones": treadmill,
        "age_days": age_days,
        "days_left": days_left,
        "required_points_per_day": pace,
        "last_verify": last_verify.isoformat() if last_verify else None,
        "staleness_days": staleness_days,
        "kill_if": kill_text or None,
        "kill_suggestion": suggestion,
        "verdicts": verdicts,
    }


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Audit strategic goals for kill criteria and treadmills.")
    ap.add_argument("--stale-days", type=float, default=14.0)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    if not STORE.exists():
        raise SystemExit(f"no goal store at {STORE}")
    data = json.loads(STORE.read_text(encoding="utf-8"))
    goals = data.get("goals") or []
    rows = [audit_goal(g, args.stale_days) for g in goals]

    hard = [r for r in rows if "TREADMILL" in r["verdicts"] or "STALLED" in r["verdicts"]]
    payload = {
        "ts": now().isoformat(),
        "store": str(STORE),
        "stale_days": args.stale_days,
        "goals": len(rows),
        "hard_findings": len(hard),
        "without_kill_criterion": sum(1 for r in rows if "NO_KILL" in r["verdicts"]),
        "rows": rows,
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(payload, indent=1, ensure_ascii=False), encoding="utf-8")

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=1))
    else:
        print(f"goal audit — {payload['goals']} goal(s), {payload['hard_findings']} hard finding(s), "
              f"{payload['without_kill_criterion']} without a kill criterion")
        print(f"  {'goal':<18} {'prog':>5} {'ms':>3} {'ver':>3} {'rev':>3} {'stale':>5}  verdicts")
        for r in rows:
            print(f"  {r['id']:<18} {str(r['progress']):>5} {r['milestones']:>3} "
                  f"{r['verified']:>3} {r['reverted']:>3} {str(r['staleness_days']):>5}  "
                  f"{','.join(r['verdicts'])}")
        for r in rows:
            if r["kill_suggestion"]:
                print(f"  -> {r['id']}: {r['kill_suggestion']}")
        print(f"  wrote {REPORT}")
    return 1 if hard else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
