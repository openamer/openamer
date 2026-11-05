#!/usr/bin/env python3
"""Verify a desktop locale file against the English source.

A locale is "complete" only when all of these hold:

1. it parses as TypeScript (no syntax errors),
2. it has exactly the same leaf set as en.ts (same paths, same count),
3. every string that was translated still carries the same ${…}
   placeholders as the English source,
4. no string contains a broken brand name ("OpenAmeric", "OpenAmerAI" …),
5. no string contains a leftover translation marker.

Usage:
    python i18n_verify_locales.py            # all locales
    python i18n_verify_locales.py fr de      # specific locales
    python i18n_verify_locales.py --json     # machine-readable output
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
I18N = REPO / "apps" / "desktop" / "src" / "i18n"
SCRIPTS = REPO / "scripts"

sys.path.insert(0, str(SCRIPTS))
from i18n_translate_locale import find_placeholders  # noqa: E402

SKIP = {
    "catalog.ts", "types.ts", "index.ts", "define-locale.ts", "plugin-i18n.ts",
    "runtime.ts", "languages.ts",
}

# Words that must never appear in a translation.
BRAND_BROKEN = ["OpenAmeric", "OpenAmerAI", "OpenAmeriC", "OpenAmer Inc", "OpenAmerLLM"]
MARKER = "\uE000"


def extract(locale: str) -> dict:
    out = REPO / "tmp" / f"i18n_verify_{locale}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(
        ["node", str(SCRIPTS / "i18n_extract_locale.mjs"), str(I18N / f"{locale}.ts"), str(out)],
        capture_output=True, text=True, cwd=str(REPO),
        encoding='utf-8',
        errors='replace',
    )
    if r.returncode != 0:
        raise SystemExit(f"extract failed for {locale}: {r.stderr[-400:]}")
    return json.loads(out.read_text(encoding="utf-8"))


def parse_errors(locale: str) -> list[str]:
    r = subprocess.run(
        ["node", str(SCRIPTS / "_dbg_diag.mjs"), str(I18N / f"{locale}.ts")],
        capture_output=True, text=True, cwd=str(REPO),
        encoding='utf-8',
        errors='replace',
    )
    out = []
    for line in r.stdout.splitlines():
        if line.strip().startswith("line "):
            out.append(line.strip())
    return out


def verify(locale: str, en: dict) -> dict:
    data = extract(locale)
    leaves = data["leaves"]
    paths = {l["path"] for l in leaves}
    en_paths = {l["path"] for l in en["leaves"]}

    en_text = {l["path"]: l["text"] for l in en["leaves"]}
    tgt_text = {l["path"]: l["text"] for l in leaves}

    missing = sorted(en_paths - paths)
    extra = sorted(paths - en_paths)

    # placeholder integrity
    broken_ph = []
    for p, t in tgt_text.items():
        src = en_text.get(p)
        if src is None or not isinstance(t, str):
            continue
        if [x for _, _, x in find_placeholders(src)] != [x for _, _, x in find_placeholders(t)]:
            broken_ph.append(p)

    # brand + marker
    brand_hits = []
    for p, t in tgt_text.items():
        if not isinstance(t, str):
            continue
        for bad in BRAND_BROKEN:
            if bad in t:
                brand_hits.append((p, bad))
        if MARKER in t:
            brand_hits.append((p, "marker"))

    # how much is actually translated (text differs from English)
    translatable = [p for p in en_text if p in tgt_text and isinstance(tgt_text[p], str)]
    translated = sum(1 for p in translatable if tgt_text[p] != en_text[p])
    untranslated = len(translatable) - translated

    return {
        "locale": locale,
        "leaves": len(leaves),
        "en_leaves": len(en_paths),
        "missing_sections": missing,
        "extra": extra,
        "broken_placeholders": broken_ph,
        "brand": brand_hits,
        "translated": translated,
        "untranslated": untranslated,
        "total_strings": len(translatable),
        "parse_errors": parse_errors(locale),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("locales", nargs="*")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    en = extract("en")
    codes = args.locales or [
        p.stem for p in sorted(I18N.glob("*.ts")) if p.name not in SKIP
    ]

    results = []
    for loc in codes:
        try:
            results.append(verify(loc, en))
        except SystemExit as exc:
            print(f"FAIL {loc}: {exc}", file=sys.stderr)
            results.append({"locale": loc, "fatal": str(exc)})

    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=1))
        return 0

    bad = 0
    print(f"{'locale':10} {'leaves':>7} {'strings':>8} {'translated':>10} {'untr.':>6} "
          f"{'missing':>7} {'badPH':>6} {'brand':>6} {'parseErr':>9}")
    for r in results:
        if "fatal" in r:
            print(f"{r['locale']:10} FATAL {r['fatal'][:60]}")
            bad += 1
            continue
        ok = (not r["missing_sections"] and not r["extra"] and not r["broken_placeholders"]
              and not r["brand"] and not r["parse_errors"])
        if not ok:
            bad += 1
        print(f"{r['locale']:10} {r['leaves']:>7} {r['total_strings']:>8} {r['translated']:>10} "
              f"{r['untranslated']:>6} {len(r['missing_sections']):>7} "
              f"{len(r['broken_placeholders']):>6} {len(r['brand']):>6} {len(r['parse_errors']):>9}")
        for key in ("missing_sections", "extra", "broken_placeholders"):
            if r[key]:
                print(f"    {key}: {r[key][:6]}")
        if r["brand"]:
            print(f"    brand: {r['brand'][:6]}")
        if r["parse_errors"]:
            print(f"    parse: {r['parse_errors'][:3]}")
    print(f"\n{bad} locale(s) with problems out of {len(results)}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
