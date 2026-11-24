#!/usr/bin/env python3
"""Scan the mirrored HackerOne disclosure archive for a bounty-factory run (step 3).

Read-only. Fetches by-year/<YEAR>.md from the ajaysenr mirror, parses the table, and
prints everything step 3 needs so it is NOT hand-rolled in scratch cells each run:

  1. ROW COUNT (line 1) + an ADVANCED-vs-STATIC verdict against the previous scan
     (snapshot kept in the system temp dir, so consecutive runs see the delta).
  2. The N NEWEST rows by `Disclosed` date -- the materially FRESH rows to mine.
     Use this INSTEAD of trusting the id-grep when the archive advanced.
  3. The TOP-N rows annotated COVERED / --- by the `#?[0-9]{6,8}` id-grep over
     lessons.md + the canonical bank.
  4. For every top-N id, the matching SENTENCE from lessons.md, so "mined" is
     distinguishable from "mentioned as queued/held over" -- the id-grep is an
     UPPER bound on mined rows and CANNOT tell those two apart by itself.

Usage:
  python archive_scan.py --year 2026 [--top 26]
  python archive_scan.py --year 2026 --lessons <path> --bank <path>

Paths default to the canonical bounty-factory / skill-dir locations; override only
for a fork. Invoke with a NATIVE Windows path (see SKILL.md `$HOME` pitfall):
  python "C:/Users/damir/AppData/Local/openamer-laptop/skills/monetarisierung/bounty-report-craft/scripts/archive_scan.py" --year 2026

If the direct fetch fails, the curl route is the fallback:
  curl -sL -o "C:/Users/damir/AppData/Local/Temp/h1_2026.md" <url>
  python archive_scan.py --year 2026 --url "file:///C:/Users/damir/AppData/Local/Temp/h1_2026.md"
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import sys
import tempfile
import urllib.request

MIRROR = ("https://raw.githubusercontent.com/ajaysenr/HackerOne-Disclosed-Reports/"
          "main/by-year/{year}.md")
DEF_LESSONS = r"C:/Users/damir/openamer-product/bounty-factory/lessons.md"
DEF_BANK = (r"C:/Users/damir/AppData/Local/openamer-laptop/skills/monetarisierung/"
            "bounty-report-craft/references/disclosed-report-patterns.md")
SNAPSHOT = os.path.join(tempfile.gettempdir(), ".h1_archive_scan.json")

ROW_RE = re.compile(
    r"\|\s*\[(\d+)\]\(\.\./reports/\1\.md\)\s*\|(.*?)\|(.*?)\|(.*?)\|(.*?)\|(.*?)\|(.*?)\|")
ID_RE = re.compile(r"#?(\d{6,8})")


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "openamer-bounty-scan"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def parse(text: str):
    rows = []
    for ln in text.split("\n"):
        m = ROW_RE.match(ln)
        if m:
            rows.append(dict(
                id=m.group(1), title=m.group(2).strip(), prog=m.group(3).strip(),
                sev=m.group(4).strip(), bounty=m.group(5).strip(),
                votes=m.group(6).strip(), disc=m.group(7).strip()))
    return rows


def read(p: str) -> str:
    return open(p, encoding="utf-8", errors="replace").read() if os.path.exists(p) else ""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", default="2026")
    ap.add_argument("--top", type=int, default=26)
    ap.add_argument("--lessons", default=DEF_LESSONS)
    ap.add_argument("--bank", default=DEF_BANK)
    ap.add_argument("--url", default=None,
                    help="override the mirror URL; use file:///C:/... with a curl-fetched copy")
    a = ap.parse_args()

    url = a.url or MIRROR.format(year=a.year)
    if url.startswith("file://"):
        path = url[7:]
        if path.startswith("/") and re.match(r"^/[A-Za-z]:", path):
            path = path[1:]  # file:///C:/... -> C:/...
        text = open(path, encoding="utf-8", errors="replace").read()
    else:
        try:
            text = fetch(url)
        except Exception as e:  # noqa: BLE001
            print(f"ERROR fetching {url}: {e}\n  fallback: curl -sL -o "
                  f"\"C:/Users/damir/AppData/Local/Temp/h1_{a.year}.md\" {url}", file=sys.stderr)
            return 1

    rows = parse(text)
    tm = re.search(r"\((\d+)\s+total\)", text)
    total = int(tm.group(1)) if tm else len(rows)
    print(f"archive: {url}")
    print(f"row count (line 1): {total}   parsed rows: {len(rows)}")

    prev = None
    if os.path.exists(SNAPSHOT):
        try:
            prev = json.load(open(SNAPSHOT, encoding="utf-8"))
        except Exception:  # noqa: BLE001
            prev = None
    if prev and prev.get("total") is not None:
        delta = total - int(prev["total"])
        verdict = "ADVANCED" if delta > 0 else ("STATIC" if delta == 0 else "SHRANK?")
        print(f"vs snapshot {prev.get('date')}: {prev.get('total')} -> {total}  [{verdict}]")
    else:
        print("no snapshot yet -> cannot judge ADVANCED/STATIC this run; writing one")
    try:
        json.dump({"total": total, "date": datetime.date.today().isoformat()},
                  open(SNAPSHOT, "w", encoding="utf-8"))
    except Exception:  # noqa: BLE001
        pass

    n = min(8, len(rows))
    print(f"\n=== {n} newest by Disclosed (the FRESH material) ===")
    for r in sorted(rows, key=lambda r: r["disc"], reverse=True)[:n]:
        print(f'  {r["disc"]}  {r["id"]:>8}  {r["bounty"]:>9}  '
              f'{r["sev"][:18]:<18} {r["title"][:60]}')

    lessons, bank = read(a.lessons), read(a.bank)
    if not lessons:
        print(f"\nWARN: lessons.md not found at {a.lessons} -> covered set will under-count",
              file=sys.stderr)
    covered = set(ID_RE.findall(lessons)) | set(ID_RE.findall(bank))
    print(f"\ncovered-set size (id-grep, UPPER bound): {len(covered)}")
    print(f"\n=== top {a.top} rows: COVERED? + matching lessons.md sentence (mined vs queued) ===")
    for r in rows[:a.top]:
        mark = "COVERED" if r["id"] in covered else "  ---  "
        print(f'{mark} {r["id"]:>8} | {r["bounty"]:>9} | {r["sev"][:18]:<18} | '
              f'{r["disc"]} | {r["title"][:52]}')
        for snip in [m.group(0) for m in
                     re.finditer(r".{0,110}" + r["id"] + r".{0,110}", lessons, re.S)][:2]:
            print("        >", " ".join(snip.split())[:200])
    print("\nNB: 'COVERED' is an UPPER bound -- read the sentence: \"mined\" and "
          "\"mentioned as queued/held over\" both match the id-grep and mean opposite things.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
