#!/usr/bin/env python3
"""Fill the translation gap in EVERY desktop locale, then rewrite the files.

The desktop locales were created with the PARTIAL pattern (see the
desktop-i18n-locale skill): only a handful of sections were translated and
everything else fell back to English through defineLocale(). This driver
translates the missing strings for every locale and regenerates each locale
file from the English source structure, so every locale has all 36 sections
instead of 8.

Locales that are already complete (en, de, zh) are left alone.

Usage:
    python i18n_complete_all_locales.py             # all locales
    python i18n_complete_all_locales.py fr de ja    # specific ones
    python i18n_complete_all_locales.py --write     # actually write the files
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
I18N = REPO / "apps" / "desktop" / "src" / "i18n"
SCRIPTS = REPO / "scripts"

SKIP = {
    "catalog.ts", "types.ts", "index.ts", "define-locale.ts", "plugin-i18n.ts",
    "runtime.ts", "languages.ts", "languages.test.ts", "runtime.test.ts",
}

# already complete — verified by the gap report
COMPLETE = {"en", "de", "zh"}


def locale_codes() -> list[str]:
    out = []
    for p in sorted(I18N.glob("*.ts")):
        if p.name in SKIP:
            continue
        out.append(p.stem)
    return out


def run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8',
                   errors='replace', cwd=str(REPO), **kw)


def translate(locale: str, workers: int) -> tuple[str, bool, str]:
    # 1) build the overlay (ternary words + special strings) for this locale
    r = run([
        sys.executable, str(SCRIPTS / "i18n_translate_overlays.py"), locale,
    ])
    if r.returncode != 0:
        print(f"    overlay for {locale} failed: {r.stderr[-200:]}", file=sys.stderr)
    # 2) translate the rest with the model
    r = run([
        sys.executable, str(SCRIPTS / "i18n_translate_locale.py"), locale,
        "--workers", str(workers),
    ])
    ok = r.returncode == 0 and (REPO / "tmp" / f"i18n_{locale}_translations.json").exists()
    return locale, ok, (r.stdout[-300:] + r.stderr[-300:])


def write(locale: str) -> tuple[str, bool, str]:
    tr = REPO / "tmp" / f"i18n_{locale}_translations.json"
    if not tr.exists():
        return locale, False, "no translations file"
    r = run([
        "node", str(SCRIPTS / "i18n_write_locale.mjs"),
        str(I18N / f"{locale}.ts"), str(tr),
    ])
    return locale, r.returncode == 0, r.stderr[-300:]


def verify(locale: str) -> tuple[str, bool, str]:
    """Re-extract the written file and compare its leaf set to en.ts."""
    out = REPO / "tmp" / f"i18n_{locale}_verify.json"
    r = run([
        "node", str(SCRIPTS / "i18n_extract_locale.mjs"),
        str(I18N / f"{locale}.ts"), str(out),
    ])
    if r.returncode != 0:
        return locale, False, r.stderr[-200:]
    data = json.loads(out.read_text(encoding="utf-8"))
    n = len(data["leaves"])
    return locale, n > 2000, f"{n} leaves"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("locales", nargs="*")
    ap.add_argument("--write", action="store_true", help="rewrite the locale files")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--locale-workers", type=int, default=4)
    args = ap.parse_args()

    codes = args.locales or [c for c in locale_codes() if c not in COMPLETE]
    print(f"locales to complete: {len(codes)}")

    failures: list[tuple[str, str]] = []

    print("\n--- translating ---")
    with ThreadPoolExecutor(max_workers=args.locale_workers) as pool:
        futs = {pool.submit(translate, c, args.workers): c for c in codes}
        for fut in as_completed(futs):
            locale, ok, msg = fut.result()
            print(f"  {'OK  ' if ok else 'FAIL'} {locale} {'' if ok else msg[-200:]}")
            if not ok:
                failures.append((locale, msg[-200:]))

    if not args.write:
        print("\n(dry run — pass --write to regenerate the locale files)")
        return 1 if failures else 0

    print("\n--- writing ---")
    with ThreadPoolExecutor(max_workers=args.locale_workers) as pool:
        futs = {pool.submit(write, c): c for c in codes}
        for fut in as_completed(futs):
            locale, ok, msg = fut.result()
            print(f"  {'OK  ' if ok else 'FAIL'} {locale} {'' if ok else msg[-200:]}")
            if not ok:
                failures.append((locale, msg[-200:]))

    print("\n--- verifying ---")
    bad = []
    with ThreadPoolExecutor(max_workers=args.locale_workers) as pool:
        futs = {pool.submit(verify, c): c for c in codes}
        for fut in as_completed(futs):
            locale, ok, msg = fut.result()
            print(f"  {'OK  ' if ok else 'FAIL'} {locale} {msg}")
            if not ok:
                bad.append(locale)

    print(f"\nfailures: {len(failures)}  unverified: {len(bad)}")
    return 1 if failures or bad else 0


if __name__ == "__main__":
    sys.exit(main())
