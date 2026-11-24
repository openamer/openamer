#!/usr/bin/env python
"""Post-cycle evidence collector for the internet learning cycle.

Cron-safe: run as a FILE, never as `python -c` or a heredoc (both are blocked).

    python <OPENAMER_HOME>/skills/internet-learning-cycle/scripts/verify_cycle_evidence.py
    python .../verify_cycle_evidence.py --tail 5      # more log rows
    python .../verify_cycle_evidence.py --base C:/Users/damir/AppData/Local/openamer-laptop

It answers the three questions the cron report needs, with real numbers:

  1. WHAT  did the last cycles claim?  -> internet_learn_log.jsonl tail (`result` is
     the FULL string; stdout truncates to 80 chars).
  2. WHERE did it go?                  -> online_buffer.jsonl tail, keys `u` / `a`
     (lowercase! a probe reading d['U'] dies with KeyError: 'U').
  3. IS the store intact?              -> every row parses and carries both keys.

The integrity count is the point: MAX_BUF=300 pins the buffer at 300 rows, so a row
COUNT tells you nothing about recency or health. `ok=300 bad=0` tells you no writer
wrote a malformed row. An `ok` well under the line count means a corrupt append.

Exit 0 when the store is intact, 1 when any row fails to parse (so it can gate a
cron chain). Health of :8081 is reported but never fatal -- a dead tool server makes
the cycle reject, which is a separate finding for the `internet-learner-stall-fix`
skill, not a store problem.
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.request

DEFAULT_BASE = "C:/Users/damir/AppData/Local/openamer-laptop"


def read_tail(path, n):
    """Last n non-empty lines. newline='' -- CRLF jsonl reads need it."""
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8", errors="replace", newline="") as f:
        lines = [ln for ln in (raw.strip() for raw in f) if ln]
    return lines[-n:]


def tool_server_health(timeout=10):
    try:
        with urllib.request.urlopen(
            "http://localhost:8081/health", timeout=timeout
        ) as r:
            return json.loads(r.read().decode("utf-8", "replace"))
    except (urllib.error.URLError, OSError, ValueError) as e:
        return {"status": "DOWN", "error": str(e)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=DEFAULT_BASE)
    ap.add_argument("--tail", type=int, default=3, help="log rows to show")
    args = ap.parse_args()
    base = args.base.rstrip("/")
    tr = base + "/scripts/training"

    print("=== tool_server :8081 ===")
    print(tool_server_health())

    print(f"\n=== internet_learn_log.jsonl (last {args.tail}) ===")
    rows = read_tail(tr + "/internet_learn_log.jsonl", args.tail)
    if rows is None:
        print("  MISSING:", tr + "/internet_learn_log.jsonl")
    else:
        for ln in rows:
            try:
                d = json.loads(ln)
            except ValueError:
                print("  UNPARSEABLE ROW:", ln[:120])
                continue
            print(f"  {d.get('ts','?')} {d.get('source','?')} "
                  f"[{d.get('elapsed_s','?')}s] {d.get('result','?')}")

    print("\n=== online_buffer.jsonl integrity ===")
    buf = tr + "/online_buffer.jsonl"
    lines = read_tail(buf, 10 ** 9)
    if lines is None:
        print("  MISSING:", buf)
        return 1
    ok = bad = 0
    for ln in lines:
        try:
            d = json.loads(ln)
            assert "u" in d and "a" in d
            ok += 1
        except (ValueError, AssertionError):
            bad += 1
    print(f"  lines={len(lines)} ok={ok} bad={bad}")

    if lines:
        d = json.loads(lines[-1])
        a = str(d.get("a", ""))
        print("\n=== buffer tail (the stored pair) ===")
        print("  u:", str(d.get("u", ""))[:200])
        print("  a:", a[:300])
        print(f"  a length: {len(a)} chars")
        # Depth tells, from references/cycle-evidence-reporting.md:
        if a[:8].lower() == "abstract":
            print("  TELL: opens with 'Abstract' -> abstract stub, shallow path won")
        elif a[:3] in ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"):
            print("  TELL: opens with a weekday -> news/SERP snippet shape")
        if len(a) < 260:
            print("  TELL: short answer vs a full-question `u` -> check "
                  "references/cycle-evidence-reporting.md before reporting 'learned'")

    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
