#!/usr/bin/env python
"""Novelty-ledger audit: is the internet learner re-issuing its own queries?

Reads <OPENAMER_HOME>/scripts/training/.il_seen_queries -- one issued query per
line, appended by _remember_query() and trimmed to the last 800 -- and reports
line count, unique count, unique:total ratio, the repeat histogram, and a verdict.

WHY: the ratio is the cheapest "is the rotation exhausting?" signal. _novel_query()
consults only _recent_queries(n=60), so when total >> unique the avoid window is too
small for the re-issue rate: stale headlines resurface and cycles are refused as
`duplicate` after a full store -> deep_learn(k=2) -> deep_learn(k=6) excursion.

Read-only (opens the ledger read-only, writes nothing). Exits 0 either way, so
ASSERT ON THE TEXT, never on the exit code -- same contract as
gate_attribution_probe.py and known_helpers_audit.py.

Usage:
    python query_ledger_audit.py
    python query_ledger_audit.py --path <file> --top 10 --window 60
"""
import argparse
import collections
import os
import sys

DEFAULT_HOME = os.environ.get(
    "OPENAMER_HOME",
    os.path.join(os.path.expanduser("~"), "AppData", "Local", "openamer-laptop"),
)
DEFAULT_LEDGER = os.path.join(
    DEFAULT_HOME, "scripts", "training", ".il_seen_queries"
)


def read_lines(path):
    """Return the non-empty ledger lines (utf-8, errors replaced). [] if missing."""
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return [ln.strip() for ln in fh if ln.strip()]
    except FileNotFoundError:
        return []
    except OSError as exc:
        print("read error: %s: %s" % (type(exc).__name__, exc))
        return []


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--path", default=DEFAULT_LEDGER, help="ledger file")
    ap.add_argument("--top", type=int, default=10, help="repeat histogram size")
    ap.add_argument("--window", type=int, default=60,
                    help="_recent_queries() window the learner actually uses")
    args = ap.parse_args()

    lines = read_lines(args.path)
    print("ledger: %s" % args.path)
    if not lines:
        print("=> EMPTY or MISSING -- no ledger to audit.")
        print("   Nothing to conclude about exhaustion; check the path first.")
        return

    uniq = set(lines)
    ratio = len(uniq) / float(len(lines))
    print("lines: %d   unique: %d   unique:total = %.2f" % (len(lines), len(uniq), ratio))
    print("learner's avoid window: %d" % args.window)

    counts = collections.Counter(lines)
    print()
    print("most re-issued queries (top %d):" % args.top)
    for query, n in counts.most_common(args.top):
        print("  %3dx  %s" % (n, query[:100]))

    # How many of the last `window` entries were already issued earlier? The
    # learner de-dupes only against that window, so a high share here means the
    # next cycle is likely to re-propose something it just issued.
    recent = lines[-args.window:] if args.window > 0 else []
    earlier = set(lines[:max(0, len(lines) - len(recent))])
    seen_again = sum(1 for q in recent if q in earlier)
    share = (seen_again / float(len(recent))) if recent else 0.0
    print()
    print("of the last %d entries, %d were issued earlier too (%.0f%%)"
          % (len(recent), seen_again, 100 * share))

    print()
    if len(lines) < 100:
        print("=> TOO SMALL to judge (%d lines). Let the rotation run." % len(lines))
    elif ratio <= 0.5:
        print("=> LEDGER EXHAUSTION: only %d unique of %d. The avoid window is too"
              % (len(uniq), len(lines)))
        print("   small for the re-issue rate -> stale headlines resurface as")
        print("   `duplicate` rejects. Report it; do NOT patch _recent_queries()")
        print("   autonomously (it moves what reaches the gates).")
    elif ratio <= 0.8:
        print("=> MIXED: %d unique of %d. Rotation is working; a reject tail here is"
              % (len(uniq), len(lines)))
        print("   ordinary noise unless the per-hour rate shows consecutive 0%% hours.")
    else:
        print("=> HEALTHY: %d unique of %d -- the live-headline path is finding fresh"
              % (len(uniq), len(lines)))
        print("   queries. Rejections are rotation noise, not exhaustion.")


if __name__ == "__main__":
    sys.exit(main())
