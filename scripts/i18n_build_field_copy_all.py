#!/usr/bin/env python3
"""Generate the localized field copy for many locales, in parallel.

The serial run takes ~4 s per locale because of the model round-trip. With
six locales in flight the whole set finishes in roughly a third of the time.
"""
from __future__ import annotations

import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts" / "i18n_build_field_copy.py"
OUT_DIR = REPO / "apps" / "desktop" / "src" / "i18n" / "field-copy"


def one(locale: str) -> tuple[str, bool, str]:
    r = subprocess.run(
        [sys.executable, str(SCRIPT), locale],
        capture_output=True, text=True, cwd=str(REPO),
        encoding='utf-8',
        errors='replace',
    )
    ok = (OUT_DIR / f"{locale}.ts").exists()
    msg = (r.stdout or "")[-160:] + (r.stderr or "")[-160:]
    return locale, ok, msg


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: python i18n_build_field_copy_all.py <locale> [locale ...]")
        return 1
    locales = sys.argv[1:]
    workers = 2
    fails = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs = {pool.submit(one, loc): loc for loc in locales}
        for fut in as_completed(futs):
            loc, ok, msg = fut.result()
            print(f"  {'OK  ' if ok else 'FAIL'} {loc}")
            if not ok:
                fails.append(loc)
    print(f"\ndone: {len(locales) - len(fails)}/{len(locales)}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
