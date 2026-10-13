#!/usr/bin/env python3
"""Repair online_buffer.jsonl: glued records and blank separator lines.

Symptom 1 (seen live 15.09.2026): two JSON objects concatenated as ..."}{...
on one line. json.loads() then fails with "Extra data", and every loader that
skips bad lines silently drops BOTH records -> a real learning is lost.

Symptom 2 (seen live 21.09.2026): the store carried a blank line between EVERY
record (151 blank rows / 157 records, 300 CRLF for 300 logical rows). Any reader
that calls json.loads() on every physical line dies on the empty string, so
knowledge_to_action.find_latest_insight() aborted the whole cycle with
"Expecting value: line 2 column 1: line 1 column 1 (char 0)" and no experiment
ever ran. A separator is not a record; the store should be clean JSONL.

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
    """Line indices that carry a glued record boundary."""
    return [i for i, l in enumerate(raw.splitlines()) if GLUE in l]


def scan_blanks(raw):
    """Line indices that are empty/whitespace-only — separators, not records."""
    return [i for i, l in enumerate(raw.splitlines()) if not l.strip()]


def _parse(raw):
    """(records, unparsable) for the non-blank lines of a raw buffer string."""
    records, bad = [], 0
    for l in raw.splitlines():
        if not l.strip():
            continue
        try:
            records.append(json.loads(l))
        except Exception:
            bad += 1
    return records, bad


def main():
    fix = "--fix" in sys.argv
    raw = open(BUF, "rb").read().decode("utf-8")
    glued = scan(raw)
    blanks = scan_blanks(raw)
    records, bad = _parse(raw)

    print(f"records={len(records)} unparsable={bad} "
          f"glued_lines={glued} blank_lines={len(blanks)}")
    if not glued and not blanks and not bad:
        print("OK: nothing to repair")
        return 0
    if not fix:
        print("run again with --fix to repair")
        return 1

    bak = BUF + ".bak-" + time.strftime("%Y%m%d_%H%M%S")
    shutil.copy2(BUF, bak)

    fixed = raw.replace(GLUE, '}' + "\r\n" + '{"')
    # drop blank separator lines, keeping one CRLF per surviving record
    lines = [l for l in fixed.splitlines() if l.strip()]
    out_records, out_bad = _parse("\n".join(lines))

    # Refuse to write an empty result: an empty read is a bug, not an intent.
    # Checked AFTER the repair transform, because a glued buffer parses to zero
    # records yet is exactly what we are here to fix.
    if not out_records:
        print(f"REFUSING to rewrite: still no record parses — read bug, not a repair "
              f"(backup={bak})")
        return 3

    open(BUF, "wb").write(("\r\n".join(lines) + "\r\n").encode("utf-8"))

    raw2 = open(BUF, "rb").read().decode("utf-8")
    records2, bad2 = _parse(raw2)
    blanks2 = len(scan_blanks(raw2))
    print(f"backup={bak}")
    print(f"after: records={len(records2)} unparsable={bad2} blank_lines={blanks2}")
    if len(records2) != len(out_records):
        print("MISMATCH: record count changed — the backup is authoritative")
        return 2
    return 0 if (bad2 == 0 and blanks2 == 0) else 2


if __name__ == "__main__":
    sys.exit(main())
