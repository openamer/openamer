#!/usr/bin/env python3
"""Verify the bounty-factory stores are LF-only and the pipeline log is well-formed.

Run AFTER the appends (step 3 and step 4 of the run checklist). The three stores
each have their OWN EOL state and a CRLF-flipped file still RENDERS fine, so you
must MEASURE, not eyeball -- this script is that measurement. Local, read-only.

    python check_stores.py

Exit 0 = all clean (CRLF==0 on every store, every log line parses, run == 1-based
index). Exit 1 = at least one store failed; it prints which and how to fix.

NOTE (Run 22, 2026-10-11): invoke this with the NATIVE path, not "$HOME/..." --
native python resolves MSYS '/c/Users/...' to 'C:\\c\\Users\\...' and fails. See
the '$HOME' pitfall in SKILL.md.
"""
import json
import sys

LESSONS = r"C:/Users/damir/openamer-product/bounty-factory/lessons.md"
LOG = r"C:/Users/damir/openamer-product/memory/si/bounty_pipeline_log.jsonl"
CANON = (r"C:/Users/damir/AppData/Local/openamer-laptop/skills/monetarisierung/"
         r"bounty-report-craft/references/disclosed-report-patterns.md")


def main() -> int:
    bad = 0
    for name, path in (("lessons.md", LESSONS),
                       ("pipeline log", LOG),
                       ("canonical bank", CANON)):
        try:
            d = open(path, "rb").read()
        except FileNotFoundError:
            print(f"FAIL {name:14s} not found: {path}")
            bad += 1
            continue
        crlf, lf, n = d.count(b"\r\n"), d.count(b"\n"), len(d)
        ok = crlf == 0
        print(f"{'OK  ' if ok else 'FAIL'} {name:14s} CRLF={crlf} LF={lf} bytes={n}")
        if not ok:
            bad += 1

    # JSONL: every line parses, run == 1-based index.
    try:
        raw = open(LOG, encoding="utf-8").read()
    except FileNotFoundError:
        raw = ""
    lines = [ln for ln in raw.replace("\r\n", "\n").split("\n") if ln.strip()]
    for i, ln in enumerate(lines, 1):
        try:
            o = json.loads(ln)
        except json.JSONDecodeError as e:
            print(f"FAIL log line {i}: {e}")
            bad += 1
            continue
        if o.get("run") != i:
            print(f"FAIL log line {i}: run={o.get('run')} != {i}")
            bad += 1
    last = json.loads(lines[-1]).get("run") if lines else "-"
    print(f"log lines={len(lines)} max_run={last}")

    if bad:
        print(f"{bad} problem(s) -- normalise CRLF in a BYTES pass: "
              f"d.replace(b'\\r\\n', b'\\n'); never re-join on '\\n'")
        return 1
    print("ALL CLEAN")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
