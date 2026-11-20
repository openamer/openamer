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
import importlib.util
import json
import os
import pathlib
import subprocess
import sys
import time

REPO = pathlib.Path(__file__).resolve().parent.parent
SCRIPTS = REPO / "scripts"
sys.path.insert(0, str(SCRIPTS))

from i18n_deliver_locales import (extract, measure, strip_brand_names_in_catalog,
                                  strip_foreign_in_catalog)  # noqa: E402

PY = sys.executable
TARGET = 0.999
BATCH_SIZE = 12             # models consistently return full arrays for <= 12; larger batches
                            # return empty or wrong-length arrays (measured 2026-11-17 on ik/ps/ve)
WORKERS = 4                 # fewer workers = more headroom per model; total concurrency ~same
SECONDS_PER_BATCH = 35      # remeasured at BATCH_SIZE 12: ~12 strings in 25-35 s (~20-30/min/worker)
SLICE_SECONDS = 12 * 60     # one locale per slice, so one slot can advance two locales
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


def strict(locale: str) -> tuple[bool, str]:
    """Close the last few real gaps that the batch translator leaves English.

    The batch pass deliberately does not push: a short word answered in English
    stays English. Without this step the loop sits at 98-99% forever (measured
    2026-11-16: `sk 98.3% -> 98.4%`, `se 96.9% -> 97.3%`). Cheap when there is
    nothing to do: it measures first and returns immediately.
    """
    r = run([PY, str(SCRIPTS / "i18n_strict_fill.py"), locale], 420)
    return r.returncode == 0, ("" if r.returncode == 0 else r.stderr.strip()[-160:])


def deliver(locale: str) -> tuple[bool, str]:
    """Deliver a locale from its cache -- but never across writing systems.

    Measured 2026-11-17: the translator answered several locales in the wrong
    script entirely (Arabic in Dzongkha, Korean in Bhojpuri, Cyrillic in Cree).
    Coverage went UP, so every earlier gate called it progress. A snapshot
    before/after delivery makes the switch visible: if the catalog gained
    foreign-script strings the previous file is restored and the delivery counts
    as failed, so the next pass translates again instead of keeping garbage.

    Returns (ok, reason). Measured 2026-11-17 on `ve`: the delivery was refused
    silently (`delivered: false`, empty reason) while the cache held 50.8 % real
    translations against a 41.4 % catalog. Two 12-minute passes were lost with no
    trace of why, so the reason is now carried out to the ledger.
    """
    target = REPO / "apps" / "desktop" / "src" / "i18n" / f"{locale}.ts"
    before = target.read_bytes() if target.exists() else None
    r = run([PY, str(SCRIPTS / "i18n_deliver_locales.py"), "--deliver", "--only", locale], 240)
    if r.returncode != 0:
        detail = (r.stderr or r.stdout or "").strip().splitlines()
        return False, (detail[-1][:160] if detail else f"deliver exit {r.returncode}")
    ok, why = script_ok(locale, before, target)
    if not ok:
        if before is not None:
            target.write_bytes(before)
        print(f"  {locale:>8} delivery rejected: {why}", file=sys.stderr)
        return False, f"script-rejected: {why}"
    return True, ""


def script_mod():
    """Load the writing-system gate (scripts/i18n_script_check.py) by path."""
    path = SCRIPTS / "i18n_script_check.py"
    spec = importlib.util.spec_from_file_location("i18n_script_check", path)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("i18n_script_check", module)
    spec.loader.exec_module(module)
    return module


def script_ok(locale: str, before: bytes | None, target: pathlib.Path) -> tuple[bool, str]:
    """True when the delivery introduced no text from a foreign script."""
    mod = script_mod()
    if mod is None or before is None or not target.exists():
        return True, ""
    old = before.decode("utf-8", errors="replace")
    new = target.read_text(encoding="utf-8", errors="replace")
    expected = mod.expected_script(locale, old)
    was = len(mod.foreign_values(mod.values(old), expected))
    bad = mod.foreign_values(mod.values(new), expected)
    if len(bad) > was:
        hint = f" e.g. {bad[0][1]}" if bad else ""
        return False, f"foreign-script values {was} -> {len(bad)}{hint}"
    return True, ""


def script_gap_count(locale: str) -> int:
    """How many catalog values carry a foreign writing system right now.

    A catalog can be 100% "complete" by coverage and still be wrong: the converge
    loop once declared 6 locales finished while they held Arabic, Hangul or CJK
    text. Those never come back as pending on a coverage-only rule, so they would
    stay wrong forever. Counting them makes the selection honest.
    """
    mod = script_mod()
    target = REPO / "apps" / "desktop" / "src" / "i18n" / f"{locale}.ts"
    if mod is None or not target.exists():
        return 0
    text = target.read_text(encoding="utf-8", errors="replace")
    expected = mod.expected_script(locale, text)
    return len(mod.foreign_values(mod.values(text), expected))


def needs_work(row: dict) -> bool:
    """A locale is pending when it misses strings OR speaks a foreign script."""
    return (row.get("real_gaps", 1) > 0) or (row.get("script_gaps", 0) > 0)


def translate(locale: str, seconds: float) -> tuple[bool, str]:
    """Fill the cache for one locale, bounded by BATCH COUNT, not by a kill.

    i18n_translate_locale.py writes its cache once, at the end. Killing it on a
    timeout throws away every batch it completed - measured 2026-11-16 on the
    first cron pass: `sn` and `ie` came out at exactly their starting coverage
    with `translated: false`, because a 12-minute slice killed runs that needed
    ~35. So the slice is a `--limit <batches>` count: the child finishes and
    writes its own cache.
    """
    batches = max(4, int(seconds // SECONDS_PER_BATCH))
    cmd = [PY, str(SCRIPTS / "i18n_translate_locale.py"), locale,
           "--workers", str(WORKERS), "--batch-size", str(BATCH_SIZE), "--limit", str(batches)]
    try:
        r = run(cmd, batches * SECONDS_PER_BATCH * 3 + 120)
    except subprocess.TimeoutExpired:
        return False, "timeout"
    return r.returncode == 0, ("" if r.returncode == 0 else r.stderr.strip()[-160:])


def ledger(row: dict) -> None:
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    row["ts"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    with LEDGER.open("a", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--budget-minutes", type=float, default=25.0)
    ap.add_argument("--only", default="")
    ap.add_argument("--order", choices=["worst", "nearest"], default="nearest",
                    help="nearest = close the almost-done locales first")
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--json", default="")
    ap.add_argument("--no-normalize", action="store_true",
                    help="skip the global catalog fixers; required when several converge "
                         "processes run in parallel, because those fixers rewrite every "
                         "catalog and would clobber a sibling process's delivery")
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
    # Order matters for what "progress" looks like. `nearest` closes the locales
    # that are almost done first - measured 2026-11-16: 60 locales sat at >=90%,
    # i.e. ~25-250 strings each, which is a few minutes of work per locale and
    # turns "0 locales complete" into a real number. `worst` is the old order.
    if args.order == "nearest":
        rows.sort(key=lambda r: (r["share"] < TARGET, -(r["share"])))
    else:
        rows.sort(key=lambda r: r["share"])

    for row in rows:
        row["script_gaps"] = script_gap_count(row["locale"])
    pending = [r for r in rows if needs_work(r)]
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
            slice_s = min(remaining * 0.8, SLICE_SECONDS)
            # One snapshot for the WHOLE pass: translate, strict, deliver and
            # normalize can each touch the catalog, so the writing-system rule is
            # enforced once at the end rather than on the delivery step alone.
            target = REPO / "apps" / "desktop" / "src" / "i18n" / f"{locale}.ts"
            snapshot = target.read_bytes() if target.exists() else None
            translated, reason = translate(locale, slice_s)
            strict_ok, strict_reason = strict(locale)
            delivered, deliver_reason = deliver(locale)
            if not delivered and deliver_reason:
                reason = f"{reason} deliver: {deliver_reason}".strip()
            if not args.no_normalize:
                normalize(locale)
            clean, why = script_ok(locale, snapshot, target)
            if not clean:
                # Second chance instead of throwing the pass away: the offending
                # values fall back to English and the rest of the delivery stays.
                # Measured 2026-11-17 on `ve`: one CJK string rejected ~1 000
                # good strings, twice, because strict_fill writes into the
                # catalog and never passes the cache filter.
                stripped = strip_foreign_in_catalog(locale, en)
                if stripped:
                    clean, why = script_ok(locale, snapshot, target)
                    if clean:
                        reason = f"{reason} stripped {stripped} foreign-script value(s)".strip()
                if not clean:
                    if snapshot is not None:
                        target.write_bytes(snapshot)
                    delivered = False
                    reason = f"{reason} script-rejected: {why}".strip()
            # Brand names are not vocabulary. The model translates them anyway
            # (measured 2026-11-20: 72 values in 17 catalogs, `Discord` ->
            # `Onenigheid`), so every pass ends with a deterministic repair.
            brands = strip_brand_names_in_catalog(locale, en)
            if brands:
                reason = f"{reason} restored {brands} brand name(s)".strip()
            after_row = measure(locale, en)
            after = after_row["share"] if after_row else before
            ledger({"locale": locale, "before": before, "after": after,
                    "translated": translated, "reason": reason,
                    "strict": strict_ok, "strict_reason": strict_reason,
                    "delivered": delivered, "budget_s": round(slice_s),
                    "script_gaps_before": row.get("script_gaps", 0),
                    "delta_pts": round((after - before) * 100, 2)})
            print(f"  {locale:>8} {before*100:5.1f}% -> {after*100:5.1f}%"
                  f"{'  (cap reached)' if after < TARGET else '  DONE'}"
                  f"{'  [' + reason + ']' if reason else ''}")

    final = [measure(r["locale"], en) for r in rows]
    final = [r for r in final if r]
    shares = [r["share"] for r in final]
    at_target = sum(1 for r in final if r.get("real_gaps", 1) == 0)
    script_dirty = [r["locale"] for r in final if script_gap_count(r["locale"]) > 0]
    below50 = sum(1 for s in shares if s < 0.5)
    print(f"final: {at_target}/{len(final)} complete (0 real gaps)   below50={below50}   "
          f"min={min(shares)*100:.1f}%   median={sorted(shares)[len(shares)//2]*100:.1f}%")
    if script_dirty:
        print(f"foreign script still present in {len(script_dirty)}: {','.join(sorted(script_dirty)[:20])}")
    if args.json:
        out = pathlib.Path(args.json)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({"locales": final}, indent=1, ensure_ascii=False), encoding="utf-8")
        print(f"json -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
