#!/usr/bin/env python3
"""Force-translate the strings a locale still has in English.

The translation cache stores the English fallback for every string the
model could not translate (rate limits, refusals). On the next run the
cache looks "complete", so those strings are never retried and the locale
stays partly English.

This script drops the English entries from the cache and re-translates
them, then reports the real coverage — the number of strings that differ
from the English source.
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


def en_text() -> dict[str, str]:
    en = json.loads((TMP / "i18n_en.json").read_text(encoding="utf-8"))
    return {l["path"]: l["text"] for l in en["leaves"] if l["kind"] in ("string", "func")}


def coverage(locale: str, en: dict[str, str]) -> int:
    f = TMP / f"i18n_{locale}_translations.json"
    if not f.exists():
        return 0
    d = json.loads(f.read_text(encoding="utf-8"))
    return sum(1 for k, v in en.items() if k in d and d[k] != v)


def purge_english(locale: str, en: dict[str, str]) -> int:
    """Remove the English fallbacks from the cache so they get retried."""
    f = TMP / f"i18n_{locale}_translations.json"
    if not f.exists():
        return 0
    d = json.loads(f.read_text(encoding="utf-8"))
    removed = 0
    for k, v in list(d.items()):
        if k in en and v == en[k]:
            del d[k]
            removed += 1
    f.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    return removed


def one(locale: str, workers: int, en: dict[str, str]) -> tuple[str, int, int]:
    purge_english(locale, en)
    r = subprocess.run(
        [sys.executable, str(SCRIPTS / "i18n_translate_locale.py"), locale,
         "--workers", str(workers), "--batch-size", "20"],
        capture_output=True, text=True, cwd=str(REPO),
        encoding='utf-8',
        errors='replace',
    )
    return locale, coverage(locale, en), r.returncode


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: python i18n_retranslate.py <locale> [locale ...]")
        return 1
    locales = sys.argv[1:]
    en = en_text()
    # Two locales at a time — six in flight made every backend answer 429.
    with ThreadPoolExecutor(max_workers=2) as pool:
        futs = {pool.submit(one, loc, 4, en): loc for loc in locales}
        for fut in as_completed(futs):
            loc, cov, rc = fut.result()
            print(f"  {loc:9} {cov:5} / {len(en)} translated", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
