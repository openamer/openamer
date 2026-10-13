#!/usr/bin/env python3
"""verdict_report.py — verdict-first reports with delta vs prior (AEON fleet-control).

Problem: our cron reports lead with detail. A reader (Damir, or the next cron
job) has to read to the end to learn whether anything is wrong. AEON's
fleet-control rule: LEAD with the verdict, then the delta vs the previous run,
then the single next action.

This tool:
  stamp <report.md> --verdict OK|WARN|FAIL [--next "..."] [--note "..."]
      Prepends a verdict header (replacing an existing one), appends the
      verdict to reports/_verdict_history.jsonl, and prints the delta vs the
      previous verdict for that report.
  scan
      Lists reports/*.md that carry no verdict header (candidates to fix).
  history [<name>]
      Shows recorded verdicts.

Exit 0 always. Idempotent: re-stamping replaces, never stacks.
"""
import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

OA_HOME = Path(r"C:\Users\damir\AppData\Local\openamer-laptop")
REPORTS = OA_HOME / "reports"
HIST = REPORTS / "_verdict_history.jsonl"
MARK = "<!-- verdict-first -->"
VALID = ("OK", "WARN", "FAIL")
ICON = {"OK": "✅", "WARN": "⚠️", "FAIL": "❌"}


def strip_existing(text):
    """Remove a prior verdict block so re-stamping is idempotent."""
    if MARK not in text:
        return text
    i = text.index(MARK)
    j = text.find("\n---\n", i)
    if j == -1:
        return text[i:].split("\n", 1)[-1]
    return text[:i] + text[j + 5:]


def last_verdict(name):
    if not HIST.exists():
        return None
    found = None
    for line in HIST.read_text(encoding="utf-8", errors="ignore").splitlines():
        try:
            r = json.loads(line)
        except Exception:
            continue
        if r.get("report") == name:
            found = r
    return found


def append_hist(rec):
    REPORTS.mkdir(parents=True, exist_ok=True)
    with HIST.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def rank(v):
    return {"OK": 0, "WARN": 1, "FAIL": 2}.get(v, -1)


def delta_line(cur, prev):
    if not prev:
        return "delta: first recorded verdict"
    p = prev.get("verdict")
    if p == cur:
        return f"delta: unchanged ({cur} since {prev.get('at','?')[:16]})"
    arrow = "->"
    if rank(cur) < rank(p):
        return f"delta: IMPROVED {p} {arrow} {cur} (since {prev.get('at','?')[:16]})"
    return f"delta: REGRESSED {p} {arrow} {cur} (since {prev.get('at','?')[:16]})"


def resolve(path):
    """Bare name -> reports/<name>; also accept reports/x.md, OA_HOME-relative,
    or an absolute path. First existing candidate wins."""
    p = Path(path)
    if p.is_absolute():
        return p
    cands = [REPORTS / p.name, OA_HOME / path, Path(path), Path.cwd() / path]
    for c in cands:
        if c.exists():
            return c
    return REPORTS / p.name


def cmd_stamp(path, verdict, nxt, note):
    p = resolve(path)
    if not p.exists():
        print(f"not found: {path} (tried {p})")
        return 1
    if verdict not in VALID:
        print(f"bad verdict '{verdict}', valid: {VALID}")
        return 1

    text = strip_existing(p.read_text(encoding="utf-8", errors="ignore")).lstrip("\n")
    prev = last_verdict(p.name)
    when = datetime.now(timezone.utc).isoformat(timespec="seconds")
    head = [
        MARK,
        f"## {ICON[verdict]} VERDICT: {verdict}",
        "",
        f"- **{delta_line(verdict, prev)}**",
        f"- next action: {nxt or 'none'}",
        f"- stamped: {when}" + (f" | {note}" if note else ""),
        "",
        "---",
        "",
    ]
    p.write_text("\n".join(head) + text, encoding="utf-8")
    append_hist({"report": p.name, "verdict": verdict, "at": when,
                 "next": nxt or "", "note": note or ""})
    print(f"STAMPED {p.name}: {verdict} | {delta_line(verdict, prev)}")
    return 0


def cmd_scan():
    if not REPORTS.exists():
        print("no reports dir")
        return 0
    missing, ok = [], []
    for f in sorted(REPORTS.glob("*.md")):
        if f.name.startswith("_") or f.stat().st_size == 0:
            continue
        try:
            t = f.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        (ok if MARK in t else missing).append(f.name)
    print(f"verdict-first coverage: {len(ok)}/{len(ok) + len(missing)}")
    if missing:
        print("missing verdict header:")
        for m in missing:
            print(f"  - {m}")
    return 0


def cmd_history(name=None):
    if not HIST.exists():
        print("no verdict history yet")
        return 0
    rows = []
    for line in HIST.read_text(encoding="utf-8", errors="ignore").splitlines():
        try:
            r = json.loads(line)
        except Exception:
            continue
        if name and r.get("report") != name:
            continue
        rows.append(r)
    for r in rows[-40:]:
        print(f"{r.get('at','?'):<20} {r.get('verdict','?'):<5} {r.get('report','?'):<34} "
              f"next: {str(r.get('next',''))[:40]}")
    return 0


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", nargs="?", default="scan")
    ap.add_argument("path", nargs="?")
    ap.add_argument("--verdict", default="OK")
    ap.add_argument("--next", dest="nxt", default="")
    ap.add_argument("--note", default="")
    a = ap.parse_args(argv)
    if a.cmd == "stamp" and a.path:
        return cmd_stamp(a.path, a.verdict, a.nxt, a.note)
    if a.cmd == "scan":
        return cmd_scan()
    if a.cmd == "history":
        return cmd_history(a.path)
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
