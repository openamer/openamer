#!/usr/bin/env python3
"""Remove hotkey markers from ARIA labels, in the catalogs AND in the caches.

A hotkey marker (`[e]`) belongs on a visible label. Inside an accessible name a
screen reader announces the brackets, so "Y[e] page précédente" is read as
"bracket e bracket page précédente".

Measured 2026-11-16: `ln` shipped exactly that, the catalogs were fixed - and
then the delivery step regenerated them from a cache that still carried the
broken strings. That is why this tool touches both sides:

  * tmp/i18n_<locale>_translations.json  (the source)
  * apps/desktop/src/i18n/<locale>.ts    (the artifact)

Only the brackets are removed; the letter and the words stay, so nothing is
invented and no text is lost.

    python scripts/i18n_fix_aria_hotkeys.py           # report only
    python scripts/i18n_fix_aria_hotkeys.py --apply   # write cache + catalogs
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

REPO = pathlib.Path(__file__).resolve().parent.parent
I18N = REPO / "apps" / "desktop" / "src" / "i18n"
TMP = REPO / "tmp"

ARIA_KEY = re.compile(r"([A-Za-z0-9_]*[Aa]ria[A-Za-z0-9_]*)\s*:\s*'((?:[^'\\]|\\.)*)'")
HOTKEY = re.compile(r"\[([A-Za-z0-9])\]")


def fix_value(value: str) -> str:
    return HOTKEY.sub(r"\1", value)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    catalog_hits: list[tuple[str, str, str, str]] = []
    for path in sorted(I18N.glob("*.ts")):
        if path.stem.endswith(".test") or path.stem in {"catalog", "types", "index"}:
            continue
        raw = path.read_bytes()
        text = raw.decode("utf-8", "replace")
        changed = text
        for m in ARIA_KEY.finditer(text):
            key, value = m.group(1), m.group(2)
            if not HOTKEY.search(value):
                continue
            catalog_hits.append((path.stem, key, value, fix_value(value)))
            changed = changed.replace(f"{key}: '{value}'", f"{key}: '{fix_value(value)}'")
        if args.apply and changed != text:
            out = changed.encode("utf-8")
            crlf, lone = raw.count(b"\r\n"), raw.count(b"\n") - raw.count(b"\r\n")
            if out.count(b"\r\n") != crlf or (out.count(b"\n") - out.count(b"\r\n")) != lone:
                print(f"ABORT {path.stem}: EOL census changed", file=sys.stderr)
                return 2
            path.write_bytes(out)

    cache_hits: list[tuple[str, str]] = []
    for cache in sorted(TMP.glob("i18n_*_translations.json")):
        try:
            data = json.loads(cache.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(data, dict):
            continue
        touched = False
        for key, value in list(data.items()):
            if "aria" not in key.lower() or not isinstance(value, str):
                continue
            if HOTKEY.search(value):
                data[key] = fix_value(value)
                cache_hits.append((cache.stem.replace("i18n_", "").replace("_translations", ""), key))
                touched = True
        if args.apply and touched:
            cache.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"catalog aria hotkeys: {len(catalog_hits)}   cache entries: {len(cache_hits)}   applied: {args.apply}")
    for loc, key, before, after in catalog_hits[:8]:
        print(f"  {loc}: {key}: '{before}' -> '{after}'")
    if cache_hits:
        print("  cache locales:", sorted({c for c, _ in cache_hits})[:12])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
