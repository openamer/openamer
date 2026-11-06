#!/usr/bin/env python3
"""Apply the overlay files to the translation tables and rewrite the locales.

The overlay holds the strings the model refuses to translate (a ternary, a
sentence built around an interpolation). The overlay is applied when the
translation table is built, but a table that already exists keeps its old
values. This script merges the overlay into the table and then regenerates
every locale file.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TMP = REPO / "tmp"
OVERLAYS = REPO / "scripts" / "i18n_overlays"


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: python i18n_apply_overlays.py <locale> [locale ...]")
        return 1
    en = json.loads((TMP / "i18n_en.json").read_text(encoding="utf-8"))
    en_text = {l["path"]: l["text"] for l in en["leaves"] if l["kind"] in ("string", "func")}
    applied = 0
    for locale in sys.argv[1:]:
        ov = OVERLAYS / f"{locale}.json"
        tbl = TMP / f"i18n_{locale}_translations.json"
        if not ov.exists() or not tbl.exists():
            continue
        overlay = json.loads(ov.read_text(encoding="utf-8"))
        table = json.loads(tbl.read_text(encoding="utf-8"))
        n = 0
        for k, v in overlay.items():
            if k in en_text and v and v.strip():
                table[k] = v
                n += 1
        tbl.write_text(json.dumps(table, ensure_ascii=False, indent=1),
                       encoding="utf-8", newline="\n")
        applied += n
        print(f"  {locale}: {n} overlay strings applied")
    print(f"\ntotal: {applied}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
