#!/usr/bin/env python3
"""Rejection-rate triage table for the internet-learning cycle (READ-ONLY).

Implements section 1 of references/rejection-triage.md as one re-runnable
action, so the table does not have to be hand-written as a throwaway script
(which then lands in the end-of-run changed-path census as an unverified path
and has to be removed and proven removed -- see skill-change-verification.md
section 8).

Prints: per-DAY trend, per-HOUR last N hours (the fastest stall/no-stall call),
per-source totals plus their trailing rate, and the trailing-cycle rate.

Also prints the trailing NON-LEARN streak (rejects + `no insight`) against the
log's historical max, plus a separate `no insight` count. Note `pass%` counts a
`no insight` row as a pass, but such a cycle stored NOTHING; re-open a gate only
when the non-learn streak EXCEEDS the historical max (archive class 161).

Run as a FILE -- a cron session BLOCKS `python -c` and heredocs:

    python <OPENAMER_HOME>/skills/internet-learning-cycle/scripts/rejection_rate_table.py
    python .../rejection_rate_table.py --hours 24 --last 100
    python .../rejection_rate_table.py --log <path/to/internet_learn_log.jsonl>

Expected shape (live 21.09.26, from the hand-written version of this probe):

    hour            n  reject  pass%
    2026-09-21T07    12     10     17%
    2026-09-21T10     9      3     67%
    TOTAL 2250 reject 629
    last 60: 60 cycles, 36 rejected

Verdict (rejection-triage.md section 1): a rate swinging ~17%..~67% hour to
hour is ROTATION NOISE -- report it and stop. The stall signature is different
and unmistakable: 0% for consecutive hours, uniformly across ALL sources, with
the buffer pinned at its cap. Only that triggers the deep-dive in
internet-learner-stall-fix. Two consecutive --once rejections prove nothing.
"""
from __future__ import annotations

import argparse
import collections
import json
import os


def default_log() -> str:
    home = os.environ.get("OPENAMER_HOME") or os.path.join(
        os.path.expanduser("~"), "AppData", "Local", "openamer-laptop")
    return os.path.join(home, "scripts", "training", "internet_learn_log.jsonl")


def load_rows(path: str):
    """One JSON row per cycle; skip blank/unparsable lines rather than die."""
    rows = []
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except ValueError:
                continue
    return rows


def is_reject(row) -> bool:
    return "rejected" in (row.get("result") or "")


def is_no_insight(row) -> bool:
    """A cycle that found nothing storable -- NOT a pass.

    Measured 12.10.26: 11 of the last 50 cycles returned the literal
    "no insight". `pass%` below counts such a row as a pass, so it over-reports
    health; both counts are printed and the streak treats either as a non-learn.
    """
    return (row.get("result") or "").strip() == "no insight"


def rate(n: int, rej: int) -> str:
    if n <= 0:
        return "  n/a"
    return f"{100 * (n - rej) / n:4.0f}%"


def bucket(rows, keyfn):
    """OrderedDict[value] -> [cycles, rejects]; insertion order == chronological."""
    out = collections.OrderedDict()
    for r in rows:
        cell = out.setdefault(keyfn(r), [0, 0])
        cell[0] += 1
        if is_reject(r):
            cell[1] += 1
    return out


def main() -> int:
    ap = argparse.ArgumentParser(
        description="rejection-rate triage table for internet_learn_log.jsonl")
    ap.add_argument("--log", default=None, help="path to internet_learn_log.jsonl")
    ap.add_argument("--days", type=int, default=14, help="day buckets to show")
    ap.add_argument("--hours", type=int, default=14, help="hour buckets to show")
    ap.add_argument("--last", type=int, default=60, help="trailing cycles for the live rate")
    args = ap.parse_args()

    path = args.log or default_log()
    if not os.path.exists(path):
        print(f"log not found: {path}")
        return 2
    rows = load_rows(path)
    if not rows:
        print(f"no parsable rows in {path}")
        return 2

    total_rej = sum(1 for r in rows if is_reject(r))
    total_ni = sum(1 for r in rows if is_no_insight(r))
    tail = rows[-max(1, args.last):]
    tail_rej = sum(1 for r in tail if is_reject(r))
    tail_ni = sum(1 for r in tail if is_no_insight(r))

    # Trailing non-learn streak vs the all-time max. Policy (learner archive
    # class 161): attribute first; re-open a gate ONLY when the streak EXCEEDS
    # the historical max. 12.10.26 sample: trailing 10 vs max 14 -> no action.
    streaks, cur = [], 0
    for r in rows:
        if is_reject(r) or is_no_insight(r):
            cur += 1
        else:
            if cur:
                streaks.append(cur)
            cur = 0
    trailing = cur
    if trailing:
        streaks.append(trailing)
        priors = streaks[:-1]
    else:
        priors = streaks
    hist_max = max(priors) if priors else 0

    print(f"log:  {path}")
    print(f"rows: {len(rows)}   rejected: {total_rej} ({rate(len(rows), total_rej).strip()} pass)"
          f"   no-insight: {total_ni}")
    print(f"last {len(tail)}: {tail_rej} rejected, {tail_ni} no-insight "
          f"({rate(len(tail), tail_rej).strip()} pass)")
    print(f"non-learn streak: trailing {trailing}   historical max {hist_max}")

    print("\nDAY             n  reject  pass%")
    days = list(bucket(rows, lambda r: (r.get("ts") or "")[:10]).items())
    for day, (n, rej) in days[-max(1, args.days):]:
        print(f"{day}  {n:5d}  {rej:6d}  {rate(n, rej)}")

    print("\nhour            n  reject  pass%")
    hours_all = list(bucket(rows, lambda r: (r.get("ts") or "")[:13]).items())
    shown = hours_all[-max(1, args.hours):]
    for hour, (n, rej) in shown:
        print(f"{hour}  {n:5d}  {rej:6d}  {rate(n, rej)}")

    print(f"\nsource                       n  reject  pass%   (trailing {len(tail)})")
    all_src = bucket(rows, lambda r: r.get("source") or "?")
    tail_src = bucket(tail, lambda r: r.get("source") or "?")
    for src in all_src:
        n, rej = all_src[src]
        tn, trej = tail_src.get(src, [0, 0])
        print(f"{src:<28} {n:5d}  {rej:6d}  {rate(n, rej)}   {tn:3d} cyc / {trej} rejected")

    if trailing > hist_max:
        print(f"\nVERDICT SHAPE: trailing non-learn streak {trailing} EXCEEDS the "
              f"historical max {hist_max} -> attribute it before any gate edit "
              f"(section 2); a NEW record needs a root cause, not a patch.")
    stalled = bool(shown) and all(v[1] == v[0] for v in shown)
    if stalled:
        print("\nVERDICT SHAPE: 0% pass in EVERY shown hour -> stall signature. "
              "Check the buffer cap, then internet-learner-stall-fix.")
    else:
        print("\nVERDICT SHAPE: rate varies across hours -> rotation noise. "
              "Report the rate and stop; do NOT edit a gate on one rejection.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
