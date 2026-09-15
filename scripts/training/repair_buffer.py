#!/usr/bin/env python3
"""Repair online_buffer.jsonl records that were glued together without a newline.

Symptom (seen live 15.09.2026): two JSON objects concatenated as ..."}{...
on one line. json.loads() then fails with "Extra data", and every loader that
skips bad lines silently drops BOTH records -> a real learning is lost.

Usage:
    python repair_buffer.py            # report only
    python repair_buffer.py --fix      # backup + rewrite
"""
import json
import os
import shutil
import sys
import time

T = os.path.dirname(os.path.abspath(__file__))
BUF = os.path.join(T, "online_buffer.jsonl")

# A glued boundary is always  }  "  {  "  (end of one record, start of the next).
GLUE = '}{"'


def scan(raw):
    return [i for i, l in enumerate(raw.splitlines()) if GLUE in l]


def main():
    fix = "--fix" in sys.argv
    raw = open(BUF, "rb").read().decode("utf-8")
    glued = scan(raw)

    total = len([l for l in raw.splitlines() if l.strip()])
    bad = 0
    for l in raw.splitlines():
        if not l.strip():
            continue
        try:
            json.loads(l)
        except Exception:
            bad += 1

    print(f"records={total} unparsable={bad} glued_lines={glued}")
    if not glued:
        print("OK: nothing to repair")
        return 0
    if not fix:
        print("run again with --fix to repair")
        return 1

    bak = BUF + ".bak-" + time.strftime("%Y%m%d_%H%M%S")
    shutil.copy2(BUF, bak)
    fixed = raw.replace('}{"', '}' + "\r\n" + '{"')
    open(BUF, "wb").write(fixed.encode("utf-8"))

    raw2 = open(BUF, "rb").read().decode("utf-8")
    bad2 = 0
    for l in raw2.splitlines():
        if not l.strip():
            continue
        try:
            json.loads(l)
        except Exception:
            bad2 += 1
    print(f"backup={bak}")
    print(f"after: unparsable={bad2}")
    return 0 if bad2 == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
