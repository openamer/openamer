#!/usr/bin/env python3
"""Fill the translation gap of every locale that is still incomplete.

The locales are processed in parallel: each one runs the translator with
its own worker pool, and several locales run at the same time. The
translation cache (tmp/i18n_<locale>_translations.json) makes a rerun cheap
— only the missing strings are translated.
"""
from __future__ import annotations

import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPTS = REPO / "scripts"
TMP = REPO / "tmp"

TARGET = 2400  # a locale with at least this many strings is considered done


def count(locale: str) -> int:
    f = TMP / f"i18n_{locale}_translations.json"
    if not f.exists():
        return 0
    try:
        return len(json.loads(f.read_text(encoding="utf-8")))
    except (json.JSONDecodeError, OSError):
        return 0


def one(locale: str, workers: int) -> tuple[str, int, bool]:
    r = subprocess.run(
        [sys.executable, str(SCRIPTS / "i18n_translate_locale.py"), locale,
         "--workers", str(workers), "--batch-size", "20"],
        capture_output=True, text=True, cwd=str(REPO),
        encoding='utf-8',
        errors='replace',
    )
    n = count(locale)
    return locale, n, r.returncode == 0 and n >= TARGET


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: python i18n_fill_locales.py <locale> [locale ...]")
        return 1
    locales = sys.argv[1:]
    # Two locales at a time, three requests each. With six locales in
    # flight every backend answered 429 and nothing was translated.
    locale_workers = 2
    per_locale = 3
    done = []
    todo = []
    with ThreadPoolExecutor(max_workers=locale_workers) as pool:
        futs = {pool.submit(one, loc, per_locale): loc for loc in locales}
        for fut in as_completed(futs):
            loc, n, ok = fut.result()
            print(f"  {'OK  ' if ok else 'PART'} {loc}: {n} strings", flush=True)
            (done if ok else todo).append(loc)
    print(f"\ncomplete: {len(done)}   still incomplete: {len(todo)}")
    if todo:
        print("incomplete:", " ".join(todo))
    return 0


if __name__ == "__main__":
    sys.exit(main())
