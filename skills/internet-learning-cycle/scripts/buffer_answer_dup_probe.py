#!/usr/bin/env python
"""Buffer-health probe: response-level duplicates + refusal attribution.

Read-only. Answers two questions the cron line "[internet-learn] ... rejected"
does not:

  1. Is the buffer SATURATED, and how much of it is redundant?
     (groups rows by the ASSISTANT text — buffer_store._is_duplicate only
      compares the (u, a) TUPLE, so the same answer under a different question
      is accepted; see references/buffer-saturation-duplicates.md)
  2. What killed the recent cycles — `junk` (a gate regressed, triage it) or
     `duplicate` (saturation, do NOT loosen a gate)?

Usage:
    python scripts/buffer_answer_dup_probe.py [--buf PATH] [--audit PATH] [--tail N]

Defaults point at the live AppData install. Pure stdlib, no imports from the
training package (so it keeps working while the autopilot rewrites it).
"""
import argparse
import collections
import json
import os
import time

HOME = r"C:/Users/damir/AppData/Local/openamer-laptop"
DEF_BUF = HOME + "/scripts/training/online_buffer.jsonl"
DEF_AUDIT = HOME + "/scripts/training/buffer_junk.jsonl"
MAX_BUF = int(os.environ.get("OPENAMER_BUFFER_MAX", "300"))


def _rows(path):
    out = []
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(json.loads(line))
                except Exception:
                    continue
    except FileNotFoundError:
        print("MISSING: %s" % path)
    return out


def probe_buffer(path, max_buf):
    rows = _rows(path)
    if not rows:
        return
    print("buffer rows: %d  (MAX_BUF=%d%s)" % (
        len(rows), max_buf, ", SATURATED" if len(rows) >= max_buf else ""))
    try:
        print("mtime: %s" % time.ctime(os.path.getmtime(path)))
    except OSError:
        pass

    by_ans = collections.defaultdict(list)
    for i, r in enumerate(rows):
        by_ans[r.get("a", "")].append((i, r.get("u", "")))

    rep = {a: v for a, v in by_ans.items() if len(v) > 1}
    extra = sum(len(v) - 1 for v in rep.values())
    print("distinct answers: %d | repeated >=2x: %d | redundant rows: %d (%.1f%%)"
          % (len(by_ans), len(rep), extra, 100.0 * extra / max(1, len(rows))))

    print("\n-- repeated answers (newest first) --")
    for a, v in sorted(rep.items(), key=lambda kv: -max(i for i, _ in kv[1]))[:15]:
        print("copies=%d last_row=%d len=%d" % (len(v), max(i for i, _ in v) + 1, len(a)))
        print("   a: %s" % a[:110].replace("\n", " "))
        for i, u in v:
            print("   row %d u=%s" % (i + 1, u[:80].replace("\n", " ")))


def probe_audit(path, tail_n):
    rows = _rows(path)
    if not rows:
        return
    reasons = collections.Counter(r.get("reason", "?") for r in rows[-tail_n:])
    print("\nrefusal reasons in last %d rows of %s:" % (min(tail_n, len(rows)), path))
    for reason, n in reasons.most_common():
        verdict = ("gate regressed -> references/rejection-triage.md"
                   if reason == "junk" else
                   "saturation -> do NOT loosen a gate"
                   if reason == "duplicate" else "?")
        print("   %-12s %3d   %s" % (reason, n, verdict))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--buf", default=DEF_BUF)
    ap.add_argument("--audit", default=DEF_AUDIT)
    ap.add_argument("--tail", type=int, default=40)
    a = ap.parse_args()
    probe_buffer(a.buf, MAX_BUF)
    probe_audit(a.audit, a.tail)


if __name__ == "__main__":
    main()
