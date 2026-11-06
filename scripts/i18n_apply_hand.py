#!/usr/bin/env python3
"""Apply the hand table to the translation tables and rewrite the locales.

The hand table (scripts/i18n_hand/<locale>.json) is the authority for the
~90 strings the translation model does not touch. It is merged into the
per-locale translation table, and the locale file is regenerated from that
table.

Why the table is authoritative: a hand-table entry that equals the English
source is a COGNATE — the word is the same in that language ("Name" in
German and Italian, "System" in German and Dutch). That is a correct
translation, not a gap. Only a human (or a table entry that differs from
the English) can tell the two apart — so the table decides, and the audit
reads the same table.

Usage:
    python i18n_apply_hand.py fr de ja
    python i18n_apply_hand.py --all
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
HAND = SCRIPTS / "i18n_hand"

SKIP = {
    "catalog", "types", "index", "define-locale", "plugin-i18n", "runtime",
    "languages",
}


def locale_codes() -> list[str]:
    return sorted(
        p.stem for p in I18N.glob("*.ts")
        if p.stem not in SKIP and not p.stem.endswith(".test")
    )


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("locales", nargs="*")
    ap.add_argument("--all", action="store_true")
    args = ap.parse_args()

    locales = args.locales or (locale_codes() if args.all else [])
    if not locales:
        print("usage: python i18n_apply_hand.py <locale> [...] | --all")
        return 1

    failed = []
    for locale in locales:
        hand = load_json(HAND / f"{locale}.json")
        if not hand:
            print(f"  {locale}: no hand table")
            continue
        table_path = TMP / f"i18n_{locale}_translations.json"
        table = load_json(table_path)
        if not table:
            print(f"  {locale}: no translation table")
            continue
        applied = 0
        for path, value in hand.items():
            if path in table and table[path] != value:
                applied += 1
            table[path] = value
        table_path.write_text(
            json.dumps(table, ensure_ascii=False, indent=1),
            encoding="utf-8", newline="\n",
        )
        r = subprocess.run(
            ["node", str(SCRIPTS / "i18n_write_locale.mjs"),
             str(I18N / f"{locale}.ts"), str(table_path)],
            capture_output=True, text=True, cwd=str(REPO),
            encoding='utf-8',
            errors='replace',
        )
        if r.returncode != 0:
            print(f"  {locale}: WRITE FAILED {r.stderr[-300:]}")
            failed.append(locale)
            continue
        print(f"  {locale}: {applied} changed, {len(hand)} hand entries applied")
    if failed:
        print("failed:", failed)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
