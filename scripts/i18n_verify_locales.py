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
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
I18N = REPO / "apps" / "desktop" / "src" / "i18n"
SCRIPTS = REPO / "scripts"

sys.path.insert(0, str(SCRIPTS))
from i18n_translate_locale import placeholders_intact  # noqa: E402

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


# Writing systems a locale MUST use. Only non-Latin ones are listed: for a
# Latin-script target, Latin text is expected input and a wrong-language fill
# cannot be told apart from a correct one without a language model, so no rule
# is honest there. For these the check is unambiguous — and it is the check that
# was missing when ps.ts (Pashto) shipped Romanian sentences and ae.ts
# (Avestan) shipped Azerbaijani ones.
NON_LATIN_SCRIPT = {
    "ar": r"[\u0600-\u06FF\u0750-\u077F]",
    "fa": r"[\u0600-\u06FF\u0750-\u077F]",
    "ps": r"[\u0600-\u06FF\u0750-\u077F]",
    "ur": r"[\u0600-\u06FF\u0750-\u077F]",
    "he": r"[\u0590-\u05FF]",
    "yi": r"[\u0590-\u05FF]",
    "ru": r"[\u0400-\u04FF]",
    "uk": r"[\u0400-\u04FF]",
    "bg": r"[\u0400-\u04FF]",
    "sr": r"[\u0400-\u04FF]",
    "mk": r"[\u0400-\u04FF]",
    "el": r"[\u0370-\u03FF]",
    "hi": r"[\u0900-\u097F]",
    "mr": r"[\u0900-\u097F]",
    "ne": r"[\u0900-\u097F]",
    "th": r"[\u0E00-\u0E7F]",
    "ko": r"[\uAC00-\uD7AF\u1100-\u11FF]",
    "zh": r"[\u4E00-\u9FFF]",
    "ja": r"[\u3040-\u30FF\u4E00-\u9FFF]",
}


def wrong_script(locale: str, tgt_text: dict, en_text: dict) -> list[str]:
    """Values that were 'translated' into a different writing system entirely.

    Only counts values that actually differ from English: an untranslated
    fallback string is legitimately Latin and must not be flagged. Four or more
    letters is the threshold — codes, URLs and numbers carry no script.
    """
    pattern = NON_LATIN_SCRIPT.get(locale)
    if not pattern:
        return []
    rx = re.compile(pattern)
    bad = []
    for path, text in tgt_text.items():
        if not isinstance(text, str) or text == en_text.get(path):
            continue
        if len([c for c in text if c.isalpha()]) < 4:
            continue
        if not rx.search(text):
            bad.append(path)
    return bad


def verify(locale: str, en: dict) -> dict:
    data = extract(locale)
    leaves = data["leaves"]
    paths = {l["path"] for l in leaves}
    en_paths = {l["path"] for l in en["leaves"]}

    en_text = {l["path"]: l["text"] for l in en["leaves"]}
    tgt_text = {l["path"]: l["text"] for l in leaves}

    missing = sorted(en_paths - paths)
    extra = sorted(paths - en_paths)

    # placeholder integrity — compare VARIABLES, not the words inside a
    # ternary: translating `${count === 1 ? 'item' : 'items'}` into another
    # language necessarily rewrites 'item'/'items', and an exact string
    # comparison reads that correct translation as a dropped placeholder.
    broken_ph = []
    for p, t in tgt_text.items():
        src = en_text.get(p)
        if src is None or not isinstance(t, str):
            continue
        if not placeholders_intact(src, t):
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
        "wrong_script": wrong_script(locale, tgt_text, en_text),
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
