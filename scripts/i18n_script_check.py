#!/usr/bin/env python3
"""Fail a desktop locale that switched to a foreign writing system.

Why this exists
---------------
`i18n_converge.py` measures completeness as "the value differs from English".
That is a coverage metric, not a correctness metric: an Arabic sentence parked in
`nv.ts` (Navajo, Latin script) counts as fully translated, and so does Korean text
in `bh.ts` (Bhojpuri, Devanagari). Measured 2026-11-17 on this repo, 18 of the 28
locales the converge loop had just declared "complete" carried thousands of
characters from a script their language does not use — the UI would have shipped
in the wrong language while every dashboard said 100%.

The script identity of a locale is not a matter of taste, so we take it from the
catalog itself: the writing system a locale's committed (`HEAD`) catalog already
uses is the one it is allowed to use. A working-tree change may add, remove or
reword strings freely, but it may not introduce a third script.

Usage
    python scripts/i18n_script_check.py                # all locales, table
    python scripts/i18n_script_check.py --json out.json
    python scripts/i18n_script_check.py nv bo dz       # specific locales
    python scripts/i18n_script_check.py --strict       # exit 1 on ANY foreign value

Exit codes
    0  every locale stayed inside its own script (warnings allowed in non-strict)
    1  at least one locale introduced a foreign script
    2  setup problem (git or the i18n directory unavailable)

Deliberate limits: Latin is always tolerated inside any catalog (product names,
"OpenAmer", API, HTTP, version strings). CJK is NOT split into Han/Kana because
Japanese legitimately mixes them; `zh`/`ja` baselines handle that on their own.
"""
from __future__ import annotations

import argparse
import collections
import json
import pathlib
import re
import subprocess
import sys
import unicodedata

REPO = pathlib.Path(__file__).resolve().parent.parent
I18N = REPO / "apps" / "desktop" / "src" / "i18n"
SKIP = {
    "catalog", "types", "index", "languages", "context", "runtime",
    "plugin-i18n", "define-locale", "en",
}

# (start, end, script) — ordered, first hit wins.
BLOCKS: tuple[tuple[int, int, str], ...] = (
    (0x0400, 0x052F, "Cyrillic"),
    (0x0530, 0x058F, "Armenian"),
    (0x0590, 0x05FF, "Hebrew"),
    (0x0600, 0x06FF, "Arabic"), (0x0750, 0x077F, "Arabic"),
    (0xFB50, 0xFDFF, "Arabic"), (0xFE70, 0xFEFF, "Arabic"),
    (0x0700, 0x074F, "Syriac"),
    (0x0900, 0x097F, "Devanagari"),
    (0x0980, 0x09FF, "Bengali"),
    (0x0A00, 0x0A7F, "Gurmukhi"),
    (0x0A80, 0x0AFF, "Gujarati"),
    (0x0B00, 0x0B7F, "Oriya"),
    (0x0B80, 0x0BFF, "Tamil"),
    (0x0C00, 0x0C7F, "Telugu"),
    (0x0C80, 0x0CFF, "Kannada"),
    (0x0D00, 0x0D7F, "Malayalam"),
    (0x0D80, 0x0DFF, "Sinhala"),
    (0x0E00, 0x0E7F, "Thai"),
    (0x0E80, 0x0EFF, "Lao"),
    (0x0F00, 0x0FFF, "Tibetan"),
    (0x1000, 0x109F, "Myanmar"),
    (0x10A0, 0x10FF, "Georgian"),
    (0x1100, 0x11FF, "Hangul"),
    (0x1200, 0x137F, "Ethiopic"),
    (0x1380, 0x139F, "Ethiopic"),
    (0x2D80, 0x2DDF, "Ethiopic"),
    (0x13A0, 0x13FF, "Cherokee"),
    (0x1400, 0x167F, "CanadianAboriginal"),
    (0x18B0, 0x18FF, "CanadianAboriginal"),
    (0x1780, 0x17FF, "Khmer"),
    (0x0780, 0x07BF, "Thaana"),
    (0x07C0, 0x07FF, "NKo"),
    (0x1C50, 0x1C7F, "OlChiki"),
    (0x2C80, 0x2CFF, "Coptic"),
    (0x2D30, 0x2D7F, "Tifinagh"),
    (0xA000, 0xA48F, "Yi"),
    (0x3040, 0x30FF, "Kana"),
    (0x3130, 0x318F, "Hangul"), (0xAC00, 0xD7AF, "Hangul"),
    (0x3400, 0x4DBF, "Han"), (0x4E00, 0x9FFF, "Han"), (0xF900, 0xFAFF, "Han"),
)


def script_of(ch: str) -> str | None:
    o = ord(ch)
    for lo, hi, name in BLOCKS:
        if lo <= o <= hi:
            return "CJK" if name in ("Han", "Kana") else name
    return None


def letter_script(ch: str) -> str | None:
    """Script of a LETTER only.

    Punctuation and digits live inside script blocks without belonging to the
    language (the Arabic comma U+060C, Arabic-Indic digits, CJK digits). Counting
    them made Thaana text look "Arabic" and produced hundreds of false positives.
    """
    if not unicodedata.category(ch).startswith("L"):
        return None
    return script_of(ch)


# Authoritative writing system per locale. Kana+Han are one family ("CJK") because
# Japanese mixes them by design. A locale absent from both maps falls back to the
# committed baseline, but only when the baseline is unambiguous (>=90% of its
# non-Latin characters in one script) -- a polluted baseline must never define the
# expectation it is then measured against.
LOCALE_SCRIPT: dict[str, str] = {
    # Cyrillic
    "ab": "Cyrillic", "av": "Cyrillic", "ba": "Cyrillic", "be": "Cyrillic", "bg": "Cyrillic",
    "bua": "Cyrillic", "ce": "Cyrillic", "cv": "Cyrillic", "kk": "Cyrillic", "kv": "Cyrillic",
    "ky": "Cyrillic", "mk": "Cyrillic", "mn": "Cyrillic", "os": "Cyrillic", "ru": "Cyrillic",
    "sah": "Cyrillic", "sr": "Cyrillic", "tg": "Cyrillic", "torbeski": "Cyrillic", "tt": "Cyrillic",
    "udm": "Cyrillic", "uk": "Cyrillic", "xal": "Cyrillic",
    # Arabic script
    "ar": "Arabic", "ckb": "Arabic", "fa": "Arabic", "ks": "Arabic", "ps": "Arabic",
    "sd": "Arabic", "ug": "Arabic", "ur": "Arabic",
    # Other non-Latin alphabets
    "el": "Greek", "he": "Hebrew", "hy": "Armenian", "ka": "Georgian", "yi": "Hebrew",
    # Indic
    "as": "Bengali", "bh": "Devanagari", "bn": "Bengali", "brx": "Devanagari", "doi": "Devanagari",
    "dv": "Thaana", "gu": "Gujarati", "hi": "Devanagari", "hne": "Devanagari", "kn": "Kannada",
    "mai": "Devanagari", "ml": "Malayalam", "mni": "Bengali", "mr": "Devanagari", "ne": "Devanagari",
    "or": "Oriya", "pa": "Gurmukhi", "pi": "Gurmukhi", "sa": "Devanagari", "si": "Sinhala",
    "ta": "Tamil", "te": "Telugu",
    # South-East Asia / Himalaya
    "bo": "Tibetan", "dz": "Tibetan", "km": "Khmer", "lo": "Lao", "my": "Myanmar", "th": "Thai",
    # Africa / Americas
    "am": "Ethiopic", "chr": "Cherokee", "cr": "CanadianAboriginal", "ii": "Yi",
    "iu": "CanadianAboriginal", "nqo": "NKo", "oj": "CanadianAboriginal", "sat": "OlChiki",
    "ti": "Ethiopic",
    # CJK
    "ja": "CJK", "ko": "Hangul", "zh": "CJK", "zh-hant": "CJK",
}

# Latin-script languages whose committed baseline is already contaminated (that is
# the bug this tool exists for), so the baseline fallback would learn the wrong
# script. Listed explicitly instead.
LATIN_LOCALES: frozenset[str] = frozenset({
    "af", "ak", "an", "ay", "az", "bm", "bs", "ca", "cs", "cy", "da", "de", "ee", "en", "eo",
    "es", "et", "eu", "ff", "fi", "fj", "fo", "fr", "fy", "ga", "gd", "gl", "gn", "gv", "ha",
    "haw", "hr", "ht", "hu", "id", "ie", "ig", "io", "is", "it", "jv", "kg", "ki", "kj", "kl",
    "kr", "ku", "kw", "la", "lb", "lg", "li", "ln", "lt", "lu", "lv", "mg", "mh", "mi", "ms",
    "mt", "na", "nb", "nd", "nl", "nn", "no", "nr", "nso", "nv", "ny", "oc", "om", "pl", "pt",
    "qu", "rm", "rn", "ro", "rw", "sc", "sg", "sk", "sl", "sm", "sn", "so", "sq", "ss", "st",
    "su", "sv", "sw", "tk", "tl", "tn", "to", "tr", "ts", "tw", "uz", "ve", "vi", "vo", "wa",
    "wo", "xh", "yo", "za", "zu",
})


STRING_RE = re.compile(r"(?:'((?:\\.|[^'\\])*)'|`((?:\\.|[^`\\])*)`)")


def values(src: str) -> list[str]:
    out = []
    for m in STRING_RE.finditer(src):
        v = m.group(1) if m.group(1) is not None else (m.group(2) or "")
        out.append(v)
    return out


def script_counts(texts: list[str]) -> collections.Counter:
    c: collections.Counter = collections.Counter()
    for t in texts:
        for ch in t:
            s = letter_script(ch)
            if s:
                c[s] += 1
    return c


def expected_script(locale: str, committed: str) -> str | None:
    """The script this locale must use. None = Latin only."""
    if locale in LOCALE_SCRIPT:
        return LOCALE_SCRIPT[locale]
    if locale in LATIN_LOCALES:
        return None
    c = script_counts(values(committed))
    if not c:
        return None
    name, n = c.most_common(1)[0]
    total = sum(c.values())
    if n >= 500 and n / total >= 0.90:
        return name
    return None


def foreign_values(texts: list[str], expected: str | None, threshold: int = 3) -> list[tuple[str, dict[str, int]]]:
    bad = []
    for t in texts:
        per: collections.Counter = collections.Counter()
        for ch in t:
            s = letter_script(ch)
            if s and s != expected:
                per[s] += 1
        if sum(per.values()) >= threshold:
            bad.append((t, dict(per)))
    return bad


def head_text(path: pathlib.Path) -> str | None:
    rel = path.relative_to(REPO).as_posix()
    r = subprocess.run(["git", "show", f"HEAD:{rel}"], cwd=REPO,
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.stdout if r.returncode == 0 else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("locales", nargs="*")
    ap.add_argument("--json", default="")
    ap.add_argument("--strict", action="store_true",
                    help="exit 1 on any foreign value, not only above the 1%% ratio")
    ap.add_argument("--ratio", type=float, default=0.01,
                    help="share of foreign values that counts as FAIL (default 1%%)")
    args = ap.parse_args()

    if not I18N.is_dir():
        print(f"missing {I18N}", file=sys.stderr)
        return 2

    paths = sorted(p for p in I18N.glob("*.ts")
                   if p.stem not in SKIP and not p.stem.endswith(".test"))
    if args.locales:
        wanted = set(args.locales)
        paths = [p for p in paths if p.stem in wanted]
    if not paths:
        print("no locales to check", file=sys.stderr)
        return 2

    rows, failed = [], []
    for p in paths:
        loc = p.stem
        working = p.read_text(encoding="utf-8", errors="replace")
        base = head_text(p)
        if base is None:
            continue
        exp = expected_script(loc, base)
        texts = values(working)
        bad = foreign_values(texts, exp)
        total = len(texts) or 1
        ratio = len(bad) / total
        verdict = "OK"
        if bad and (args.strict or ratio > args.ratio):
            verdict = "FAIL"
            failed.append(loc)
        elif bad:
            verdict = "WARN"
        rows.append({
            "locale": loc,
            "expected": exp or "Latin",
            "values": len(texts),
            "foreign_values": len(bad),
            "ratio": round(ratio, 4),
            "verdict": verdict,
            "sample": [{"text": t[:80], "scripts": s} for t, s in bad[:3]],
        })

    rows.sort(key=lambda r: (-r["ratio"], r["locale"]))
    bad_rows = [r for r in rows if r["foreign_values"]]
    print(f"checked {len(rows)} locales | clean {len(rows) - len(bad_rows)} | "
          f"with foreign script {len(bad_rows)} | FAIL {len(failed)}")
    for r in bad_rows:
        print(f"  {r['locale']:>8}  exp={r['expected']:<19} "
              f"foreign={r['foreign_values']:>4}/{r['values']:<5} {r['ratio']*100:5.1f}%  {r['verdict']}")
        for s in r["sample"][:1]:
            print(f"            {s['scripts']} | {s['text']}")
    if args.json:
        out = pathlib.Path(args.json)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"json -> {out}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
