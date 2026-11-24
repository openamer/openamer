#!/usr/bin/env python3
"""Reject-run significance test for the internet learning cycle.

Answers the cron question "is this reject streak a stall?" with a number instead
of an eyeball. Run it after any run of consecutive
`rejected, not trained (shallow + deep read both gated)` lines.

Usage (from OPENAMER_HOME):
    python scripts/training/reject_run_significance.py           # today
    python scripts/training/reject_run_significance.py 2026-10-13 # date prefix

Decision rule: P(longest run >= observed) > 0.1  =>  normal noise, do NOT touch
a gate, report only.  See
skills/internet-learning-cycle/references/reject-run-length-significance.md
"""
import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
HOME = os.path.abspath(os.path.join(HERE, os.pardir, os.pardir))
LOG = os.path.join(HOME, "scripts", "training", "internet_learn_log.jsonl")

REJECT_MARK = "rejected"


def load(prefix):
    rows = []
    with open(LOG, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except Exception:
                continue
            if str(r.get("ts", "")).startswith(prefix):
                rows.append(r)
    return rows


def longest_run(rows):
    best = cur = 0
    for r in rows:
        if REJECT_MARK in str(r.get("result", "")):
            cur += 1
            best = max(best, cur)
        else:
            cur = 0
    return best


def main():
    prefix = sys.argv[1] if len(sys.argv) > 1 else None
    if prefix is None:
        # derive today's date from the last row (no wall-clock dependency issues)
        all_rows = load("")
        if not all_rows:
            print("no rows in", LOG)
            return
        prefix = str(all_rows[-1].get("ts", ""))[:10]

    rows = load(prefix)
    n = len(rows)
    if n == 0:
        print(f"no cycles logged for prefix {prefix!r}")
        return
    rej = sum(1 for r in rows if REJECT_MARK in str(r.get("result", "")))
    p = rej / n
    obs = longest_run(rows)

    random.seed(0)
    trials = 20000
    runs = []
    for _ in range(trials):
        b = c = 0
        for _ in range(n):
            if random.random() < p:
                c += 1
                b = max(b, c)
            else:
                c = 0
        runs.append(b)
    runs.sort()
    pge = sum(1 for x in runs if x >= obs) / trials
    mean = sum(runs) / len(runs)

    print(f"window prefix      : {prefix}")
    print(f"cycles             : {n}  ({n - rej} accepted, {rej} rejected, p_reject={p:.3f})")
    print(f"observed longest run: {obs}")
    print(f"sim                  : mean={mean:.2f} median={runs[len(runs)//2]} P(run>={obs})={pge:.3f}")
    if pge > 0.1:
        print(f"VERDICT: NORMAL noise ({100 * pge:.0f}th percentile) — do NOT touch a gate.")
    else:
        print(f"VERDICT: ANOMALOUS ({100 * pge:.1f}th percentile) — investigate; "
              f"file in references/pending-candidates.md before any gate change.")


if __name__ == "__main__":
    main()
