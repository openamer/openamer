"""Calibrate the expected writing system per locale from the locale itself.

A hand-maintained list of script ranges is a liability twice over. The first
version flagged 46,046 values because Tajik, Tatar, Uyghur and Traditional
Chinese write in scripts it did not list; the second flagged Telugu, Kannada and
Malayalam because *their* ranges were missing and anything alphabetic outside
the table fell through to "Latin".

Unicode already knows the answer: every letter's name begins with its script
("TELUGU LETTER PHA", "ARABIC LETTER BEH", "CJK UNIFIED IDEOGRAPH-4E2D"). So the
script is read from the character itself, with no table to keep current.

And the *locale* answers the second question. Each catalog holds thousands of
values; the scripts those values use ARE the locale's scripts. A value written
in a script that appears nowhere else in its own file is the outlier — which is
exactly what a mistranslation looks like (Korean inside Aragonese, Han inside
Tongan).
"""
from __future__ import annotations

import unicodedata
from collections import Counter
from typing import Iterable

SCRIPT_RULES = 2  # bump when classification changes, so stale reports are visible

# Names that do not start with the script name we want to report.
_ALIAS = {
    "CJK": "Han",          # CJK UNIFIED IDEOGRAPH-4E2D
    "IDEOGRAPH": "Han",
    "HIRAGANA": "Kana",
    "KATAKANA": "Kana",
}

# Scripts Unicode knows by name. A character whose name contains none of these
# is treated as Latin — which is right for the overwhelming majority of
# characters in a UI catalog, and avoids inventing a "Modifier" or "Fullwidth"
# writing system out of MODIFIER LETTER APOSTROPHE (Navajo ʼ) or FULLWIDTH LATIN
# CAPITAL LETTER A. Both were counted as foreign scripts before this list
# existed: 600 false outliers in nv.ts, 253 in ja.ts.
_SCRIPTS = {
    "LATIN", "GREEK", "CYRILLIC", "ARMENIAN", "HEBREW", "ARABIC", "SYRIAC",
    "THAANA", "NKO", "DEVANAGARI", "BENGALI", "GURMUKHI", "GUJARATI", "ORIYA",
    "TAMIL", "TELUGU", "KANNADA", "MALAYALAM", "SINHALA", "THAI", "LAO",
    "TIBETAN", "MYANMAR", "GEORGIAN", "HANGUL", "ETHIOPIC", "CHEROKEE",
    "CANADIAN", "OGHAM", "RUNIC", "KHMER", "MONGOLIAN", "HIRAGANA",
    "KATAKANA", "BOPOMOFO", "YI", "AVESTAN", "CJK", "IDEOGRAPH", "COPTIC",
    "GOTHIC", "BRAILLE",
}


def script_counts(text: str) -> Counter[str]:
    """How many letters of each writing system a string contains."""
    counts: Counter[str] = Counter()
    for ch in text:
        if not ch.isalpha():
            continue
        name = unicodedata.name(ch, "")
        if not name:
            continue
        found = next((tok for tok in name.split() if tok in _SCRIPTS), None)
        counts[_ALIAS.get(found, found.title()) if found else "Latin"] += 1
    return counts


def script_of(text: str) -> str:
    """Dominant writing system of one string, ignoring punctuation and digits."""
    counts = script_counts(text)
    if not counts:
        return "none"
    return counts.most_common(1)[0][0]


def locale_scripts(values: Iterable[str], min_share: float = 0.02) -> set[str]:
    """Writing systems this locale actually uses.

    A script must appear in at least ``min_share`` of the values to count — that
    keeps a handful of leaked foreign strings from legitimising themselves,
    while still allowing genuinely mixed catalogs (Japanese Kana + Han).
    """
    counts: Counter[str] = Counter()
    total = 0
    for v in values:
        if not isinstance(v, str):
            continue
        s = script_of(v)
        if s == "none":
            continue
        counts[s] += 1
        total += 1
    if not total:
        return set()
    allowed = {s for s, c in counts.items() if c / total >= min_share}
    allowed.add(counts.most_common(1)[0][0])
    return allowed


def is_outlier(text: str, allowed: set[str], min_chars: int = 2) -> bool:
    """True when this value carries letters from a script its locale never uses.

    Any such run of ``min_chars`` letters decides it, not the dominant script:
    ``后端 v1.2.3`` is mostly Latin by count and still wrong, and so is
    ``OpenAmer ꃅꏢ v1``. One foreign letter is a product name; two in a row in a
    UI string is a mistranslation.
    """
    if not isinstance(text, str):
        return False
    return any(n >= min_chars and s not in allowed
               for s, n in script_counts(text).items())
