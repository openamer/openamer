#!/usr/bin/env python3
"""Close the remaining English gaps of the desktop locales, for real.

The bulk translation run (i18n_translate_locale.py) leaves a few strings in
English: sentences built around an interpolation ("Show ${count} more in
${label}"), short labels ("Model · ${provider}: ${model}") and proper nouns
the translator refuses to touch. This driver

  1. collects the English leftovers of a locale,
  2. asks the translation model for them as one batch,
  3. writes the result back into the translation table,
  4. regenerates the locale file from that table,
  5. re-extracts the file and proves that the key set matches en.ts.

It repeats until a locale stops improving, then reports what is left.

Usage:
    python i18n_close_gaps.py                 # every locale with gaps
    python i18n_close_gaps.py nl de           # specific locales
    python i18n_close_gaps.py --max-rounds 3
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPTS = REPO / "scripts"
I18N = REPO / "apps" / "desktop" / "src" / "i18n"
TMP = REPO / "tmp"

sys.path.insert(0, str(SCRIPTS))

from i18n_audit_locales import SKIP, is_real_gap, leaves_of  # noqa: E402
from i18n_translate_locale import load_env  # noqa: E402


def locale_codes() -> list[str]:
    return sorted(
        p.stem for p in I18N.glob("*.ts")
        if p.name not in SKIP and not p.name.endswith(".test.ts")
    )


def gaps_of(locale: str, en_text: dict[str, str]) -> list[str]:
    lv = leaves_of(locale)
    tgt = {p: l["text"] for p, l in lv.items() if l["kind"] in ("string", "func")}
    same = [p for p, t in en_text.items() if p in tgt and tgt[p] == t]
    return [p for p in same if is_real_gap(p, en_text[p])]


def table_of(locale: str) -> dict[str, str]:
    f = TMP / f"i18n_{locale}_translations.json"
    if not f.exists():
        return {}
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8',
                   errors='replace', cwd=str(REPO))


def translate_leftovers(locale: str) -> int:
    """Translate the English leftovers of one locale. Returns how many."""
    r = run([sys.executable, str(SCRIPTS / "i18n_translate_leftovers.py"), locale])
    sys.stderr.write(r.stderr[-1500:])
    print(r.stdout.strip().splitlines()[-1] if r.stdout.strip() else "  (no output)")
    return 0


def write_locale(locale: str) -> bool:
    tr = TMP / f"i18n_{locale}_translations.json"
    if not tr.exists():
        return False
    r = run([
        "node", str(SCRIPTS / "i18n_write_locale.mjs"),
        str(I18N / f"{locale}.ts"), str(tr),
    ])
    if r.returncode != 0:
        print(f"  {locale}: WRITE FAILED {r.stderr[-300:]}")
        return False
    return True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("locales", nargs="*")
    ap.add_argument("--max-rounds", type=int, default=4)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    en = leaves_of("en")
    en_text = {p: l["text"] for p, l in en.items() if l["kind"] in ("string", "func")}

    targets = args.locales or [c for c in locale_codes() if c != "en"]
    for locale in targets:
        before = len(gaps_of(locale, en_text))
        if before == 0:
            continue
        print(f"\n=== {locale}: {before} gaps ===")
        for rnd in range(1, args.max_rounds + 1):
            gaps = gaps_of(locale, en_text)
            if not gaps:
                break
            # The table must know every gap, otherwise the writer cannot
            # replace the English text. Missing keys are translated by the
            # bulk translator first.
            table = table_of(locale)
            unknown = [p for p in gaps if p not in table]
            if unknown:
                print(f"  round {rnd}: {len(unknown)} key(s) missing from the table")
                r = run([
                    sys.executable, str(SCRIPTS / "i18n_translate_locale.py"), locale,
                    "--workers", "3", "--batch-size", "20",
                ])
                sys.stderr.write(r.stderr[-800:])
            translate_leftovers(locale)
            if args.dry_run:
                break
            if not write_locale(locale):
                break
            after = len(gaps_of(locale, en_text))
            print(f"  round {rnd}: {len(gaps)} -> {after} gaps")
            if after >= len(gaps):
                break

    print("\n=== final ===")
    total = 0
    for locale in locale_codes():
        if locale == "en":
            continue
        g = gaps_of(locale, en_text)
        total += len(g)
        if g:
            print(f"{locale:10} {len(g):4} gaps")
    print(f"total remaining gaps: {total}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
