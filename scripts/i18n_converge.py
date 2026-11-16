#!/usr/bin/env python3
"""Converge every desktop locale to full translation, one budgeted pass at a time.

This is the "never stop until 100%" loop, built on the existing pieces instead of
a new translator:

    measure -> (translate the worst locale) -> deliver cache -> normalize -> measure

Every pass is bounded by a time budget so it can run from cron without pinning
the machine: each language gets a slice, the ledger records where the pass
stopped, and the next pass resumes with the worst locale again. Progress is
monotonic because the translator only ADDS to the cache and delivery only writes
from a cache that was just measured.

    python scripts/i18n_converge.py --budget-minutes 25
    python scripts/i18n_converge.py --budget-minutes 5 --only vo,sn,ie
    python scripts/i18n_converge.py --report          # no work, just the table

Ledger: $OPENAMER_HOME/reports/i18n-converge-ledger.jsonl
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import pathlib
import subprocess
import sys
import time

REPO = pathlib.Path(__file__).resolve().parent.parent
SCRIPTS = REPO / "scripts"
sys.path.insert(0, str(SCRIPTS))

from i18n_deliver_locales import extract, measure  # noqa: E402

PY = sys.executable
TARGET = 0.999
HOME = pathlib.Path(os.environ.get(
    "OPENAMER_HOME",
    str(pathlib.Path.home() / "AppData" / "Local" / "openamer-laptop"),
))
LEDGER = HOME / "reports" / "i18n-converge-ledger.jsonl"


def run(args: list[str], timeout: float) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, text=True, cwd=str(REPO),
                          encoding="utf-8", errors="replace", timeout=max(30, timeout))


def normalize(locale: str) -> None:
    """Re-apply the two catalog rules the caches can violate."""
    run([PY, str(SCRIPTS / "i18n_fix_plural_double_word.py"), "--apply"], 240)
    run([PY, str(SCRIPTS / "i18n_fix_aria_hotkeys.py"), "--apply"], 120)


def deliver(locale: str) -> bool:
    r = run([PY, str(SCRIPTS / "i18n_deliver_locales.py"), "--deliver", "--only", locale], 240)
    return r.returncode == 0


def translate(locale: str, seconds: float) -> bool:
    """Fill the cache for one locale within the remaining budget."""
    try:
        r = run([PY, str(SCRIPTS / "i18n_translate_locale.py"), locale,
                 "--workers", "3", "--batch-size", "20"], seconds)
    except subprocess.TimeoutExpired:
        return False
    return r.returncode == 0


def ledger(row: dict) -> None:
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    row["ts"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    with LEDGER.open("a", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--budget-minutes", type=float, default=25.0)
    ap.add_argument("--only", default="")
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--json", default="")
    args = ap.parse_args()

    en = extract("en")
    if en is None:
        print("cannot extract en.ts", file=sys.stderr)
        return 2

    wanted = [s for s in args.only.split(",") if s]
    rows = []
    for locale in (wanted or sorted(p.stem for p in (REPO / "apps/desktop/src/i18n").glob("*.ts")
                                    if p.stem not in {"catalog", "types", "index", "languages",
                                                      "context", "runtime", "plugin-i18n",
                                                      "define-locale", "en"}
                                    and not p.stem.endswith(".test"))):
        row = measure(locale, en)
        if row:
            rows.append(row)
    rows.sort(key=lambda r: r["share"])

    pending = [r for r in rows if r["share"] < TARGET]
    done = len(rows) - len(pending)
    print(f"start: {done}/{len(rows)} at target, {len(pending)} pending, "
          f"worst {pending[0]['locale']}:{pending[0]['share']*100:.1f}%" if pending
          else f"start: {done}/{len(rows)} at target - nothing to do")

    if not args.report and pending:
        deadline = time.monotonic() + args.budget_minutes * 60
        for row in pending:
            remaining = deadline - time.monotonic()
            if remaining < 60:
                print("budget exhausted; next pass continues")
                break
            locale = row["locale"]
            before = row["share"]
            slice_s = min(remaining * 0.8, 12 * 60)
            translated = translate(locale, slice_s)
            delivered = deliver(locale)
            normalize(locale)
            after_row = measure(locale, en)
            after = after_row["share"] if after_row else before
            ledger({"locale": locale, "before": before, "after": after,
                    "translated": translated, "delivered": delivered,
                    "budget_s": round(slice_s)})
            print(f"  {locale:>8} {before*100:5.1f}% -> {after*100:5.1f}%"
                  f"{'  (cap reached)' if after < TARGET else '  DONE'}")

    final = [measure(r["locale"], en) for r in rows]
    final = [r for r in final if r]
    shares = [r["share"] for r in final]
    at_target = sum(1 for s in shares if s >= TARGET)
    below50 = sum(1 for s in shares if s < 0.5)
    print(f"final: {at_target}/{len(final)} at >=99.9%   below50={below50}   "
          f"min={min(shares)*100:.1f}%   median={sorted(shares)[len(shares)//2]*100:.1f}%")
    if args.json:
        out = pathlib.Path(args.json)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({"locales": final}, indent=1, ensure_ascii=False), encoding="utf-8")
        print(f"json -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
