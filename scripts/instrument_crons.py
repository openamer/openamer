#!/usr/bin/env python3
"""Cron entry points for the self-instruments — with the logic inside the product.

The three watchdogs started life as install-local scripts under
`$OPENAMER_HOME/scripts`, which put the decision they encode outside the test
suite: `npm run test` could not reach them, so their behaviour was only ever
demonstrated by hand. Measured 2026-11-18, the same "unverified" flag came back
twice for exactly that reason.

The split that fixes it: **decisions live here**, the runtime files are six-line
shims. `goal_digest`, `incident_digest` and `bench_report` are pure functions —
report dicts in, lines out — so they are unit-testable without a cron runner, a
network, or a live benchmark.

    python scripts/instrument_crons.py goal-audit
    python scripts/instrument_crons.py incident-classes
    python scripts/instrument_crons.py fresh-bench

Silence is the contract: an empty line list means "nothing new" and the cron
stays quiet (the `no_agent` rule: empty stdout sends nothing).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

HOME = Path(os.environ.get("OPENAMER_HOME")
            or (Path.home() / "AppData" / "Local" / "openamer-laptop"))
REPO = Path(os.environ.get("OPENAMER_REPO", Path.home() / "openamer-repo"))

HARD = ("TREADMILL", "STALLED", "KILL_REVIEW_OVERDUE")


# ── goal audit ─────────────────────────────────────────────────────────────

def goal_fingerprint(report: dict) -> dict:
    """The part of a goal report worth waking a human for: goal -> hard verdicts."""
    out = {}
    for row in report.get("rows", []):
        hard = sorted(v for v in row.get("verdicts", []) if v in HARD)
        if hard:
            out[row["id"]] = hard
    return out


def goal_digest(report: dict, previous: dict) -> tuple[list[str], dict]:
    """Speak when a hard verdict appears/changes/clears OR the structural gap moves.

    The gap count belongs to the state: without it, "5 goals declare no kill
    criterion" would only ever be mentioned as a footnote to some other news.
    """
    current = {"hard": goal_fingerprint(report),
               "no_kill": report.get("without_kill_criterion", 0)}
    prev_hard = previous.get("hard") or {}
    new = {k: v for k, v in current["hard"].items() if prev_hard.get(k) != v}
    cleared = sorted(k for k in prev_hard if k not in current["hard"])
    gap_moved = previous.get("no_kill") != current["no_kill"]
    if not new and not cleared and not gap_moved:
        return [], current

    rows = {r["id"]: r for r in report.get("rows", [])}
    lines = []
    if new:
        lines.append(f"goal audit: {len(new)} goal(s) need a decision")
        for gid, verdicts in new.items():
            row = rows.get(gid, {})
            lines.append(f"  {gid}: {','.join(verdicts)} — progress {row.get('progress')}, "
                         f"{row.get('reverted')}/{row.get('milestones')} milestones reverted")
            if row.get("kill_suggestion"):
                lines.append(f"    {row['kill_suggestion']}")
    if cleared:
        lines.append(f"goal audit: cleared {', '.join(cleared)}")
    lines.append(f"  {current['no_kill']}/{report.get('goals')} goals still "
                 f'declare no kill criterion — add "kill_if" to memory/strategic_goals.json')
    return lines, current


# ── incident classes ───────────────────────────────────────────────────────

def incident_digest(report: dict, previous: dict) -> tuple[list[str], dict]:
    counts = {k: v["count"] for k, v in (report.get("classes") or {}).items()}
    previous = previous.get("counts") or {}
    new_classes = [c for c in counts if c not in previous]
    unclassified = counts.get("unknown", 0)
    jumps = [f"{c}: {previous.get(c, 0)} -> {n}" for c, n in counts.items()
             if previous.get(c) and n >= max(3, previous[c] * 2)]
    if not new_classes and not unclassified and not jumps:
        return [], {"counts": counts}

    lines = [f"incident classes changed ({report.get('failures')} failures / 7 days)"]
    if new_classes:
        lines.append(f"  new class: {', '.join(new_classes)}")
        for cls in new_classes:
            rule = (report["classes"][cls] or {}).get("rule", "")
            if rule:
                lines.append(f"    rule: {rule}")
    if unclassified:
        sample = (report["classes"].get("unknown") or {}).get("sample", "")[:160]
        lines.append(f"  {unclassified} failure(s) fell through to 'unknown' — the taxonomy "
                     f"has a hole: {sample}")
    lines += [f"  jump: {j}" for j in jumps]
    return lines, {"counts": counts}


# ── fresh bench ────────────────────────────────────────────────────────────

def bench_report(report: dict) -> list[str]:
    """Always speaks: a weekly measurement with no number is not a measurement."""
    results = report.get("results") or []
    header = (f"fresh bench {report['ts'][:10]} — {report['items']} never-seen task(s), "
              f"seed {report['seed']}")
    lines, unreachable = [header], []
    for row in results:
        if row.get("model_error"):
            unreachable.append(f"{row['subject']}: MODEL ERROR ({row['model_error_reason'][:90]})")
            lines.append(f"  {row['subject']:<32} MODEL ERROR — not a score")
            continue
        lo, hi = row["ci95"]
        lines.append(f"  {row['subject']:<32} {row['resolved']}/{row['n']} "
                     f"{row['share'] * 100:5.1f}%  [{lo * 100:.1f}, {hi * 100:.1f}]")
    if report.get("ranking"):
        lines.append(f"  {report['ranking']}")
    if unreachable:
        lines.append("  unreachable: " + "; ".join(unreachable))
    return lines


# ── plumbing ───────────────────────────────────────────────────────────────

def _state(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=1), encoding="utf-8")


def _run(script: Path, *args: str, timeout: int = 3600) -> None:
    subprocess.run([sys.executable, str(script), *args], capture_output=True, text=True,
                   encoding="utf-8", errors="replace", timeout=timeout, check=False)


def main(mode: str) -> int:
    """Run one instrument, then print only what changed. Exit 0 in every case."""
    report_path = {"goal-audit": HOME / "reports" / "goal-audit.json",
                   "incident-classes": HOME / "reports" / "incident-classes.json",
                   "fresh-bench": HOME / "reports" / "fresh-bench-latest.json"}[mode]
    state_path = HOME / "memory" / "cron" / f"{mode}-state.json"
    script = REPO / "scripts" / {"goal-audit": "goal_audit.py",
                                 "incident-classes": "incident_classes.py",
                                 "fresh-bench": "fresh_bench.py"}[mode]
    if not script.is_file():
        print(f"{script.name} missing — instrument not installed", file=sys.stderr)
        return 0

    if mode == "goal-audit":
        _run(script)
    elif mode == "incident-classes":
        _run(script, "--days", "7")
    else:
        _run(script, "--items", os.environ.get("FRESH_BENCH_ITEMS", "6"),
             "--subjects", "local,ref")

    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        print(f"no readable report at {report_path}", file=sys.stderr)
        return 0

    if mode == "fresh-bench":
        lines = bench_report(report)
    else:
        digest = goal_digest if mode == "goal-audit" else incident_digest
        lines, current = digest(report, _state(state_path))
        _write(state_path, {"ts": report.get("ts"), **current})

    if lines:
        print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "goal-audit"))
