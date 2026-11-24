#!/usr/bin/env python3
"""Append ONE run record to the bounty-factory pipeline log.

Correct path (verified 2026-10-04): the live history lives beside BOUNTY_FACTORY.md
under openamer-product/ — NOT under AppData/Local/openamer-laptop/memory/si/.

Usage:
  python append_run_log.py --run 5 --tg "RESTARTED then alive (/debug ok)" \
      --graded 0 --lessons 2 --range "9-10" \
      --sources "#3694007 HackerOne Painless ES script exec $7,000 (CVSS 8.8)" \
                "#3622877 Cloudflare request-inspection-bypass $1,500" \
      --notes "no new .md practice reports; H1 direct scrape blocked, used archive"

Schema per line (one JSONL object per RUN, not three per run):
  {"ts","run","training_ground","new_reports_graded","lessons_added",
   "lesson_range","sources":[...],"notes"}

Before appending, run the consistency check the SKILL mandates: read the log,
take max(run), count the '## <date> — Run N' blocks in lessons.md. lessons.md
runs AHEAD of the log routinely — backfill any missing runs first (mark
notes:"BACKFILLED <date>"), then append the current run. See SKILL.md step 4.
"""
import argparse
import datetime
import json
import os
import sys

LOG = r"C:/Users/damir/openamer-product/memory/si/bounty_pipeline_log.jsonl"
LESSONS = r"C:/Users/damir/openamer-product/bounty-factory/lessons.md"


def last_run(path):
    if not os.path.exists(path):
        return None
    n = None
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                n = json.loads(line).get("run", n)
            except json.JSONDecodeError:
                continue
    return n


def lessons_runs(path):
    """Count '## ... Run N' blocks; returns the highest N seen (heuristic)."""
    if not os.path.exists(path):
        return 0
    hi = 0
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.startswith("## ") and "Run" in line:
                try:
                    hi = max(hi, int(line.rsplit("Run", 1)[1].split()[0]))
                except (ValueError, IndexError):
                    pass
    return hi


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", type=int, required=True)
    ap.add_argument("--tg", default="")
    ap.add_argument("--graded", type=int, default=0)
    ap.add_argument("--lessons", type=int, default=0)
    ap.add_argument("--range", dest="rng", default="")
    ap.add_argument("--sources", nargs="*", default=[])
    ap.add_argument("--notes", default="")
    ap.add_argument("--force", action="store_true",
                    help="append even if run <= last logged run (default: warn+abort)")
    a = ap.parse_args()

    lr, rr = last_run(LOG), lessons_runs(LESSONS)
    if lr is not None and rr and rr > lr:
        print(f"WARN: lessons.md is at Run {rr} but log ends at Run {lr} "
              f"-> backfill runs {lr+1}..{rr} first (see SKILL.md step 4).",
              file=sys.stderr)
    if lr is not None and a.run <= lr and not a.force:
        print(f"ABORT: run {a.run} <= last logged run {lr}. Use --force to override.",
              file=sys.stderr)
        sys.exit(2)

    rec = {
        "ts": datetime.date.today().isoformat(),
        "run": a.run,
        "training_ground": a.tg,
        "new_reports_graded": a.graded,
        "lessons_added": a.lessons,
        "lesson_range": a.rng,
        "sources": a.sources,
        "notes": a.notes,
    }
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    # newline="" stops Windows text-mode from translating LF into CRLF (file is LF-only).
    with open(LOG, "a", encoding="utf-8", newline="") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"appended run {a.run} -> {LOG}")


if __name__ == "__main__":
    main()
