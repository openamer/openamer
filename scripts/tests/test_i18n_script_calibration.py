"""The script calibration must read each locale's own writing system.

Two hand-written tables failed before this existed:

* a table of script ranges flagged 46,046 values because Tajik, Tatar, Uyghur and
  Traditional Chinese write in scripts it did not list;
* the corrected table flagged Telugu, Kannada and Malayalam because their ranges
  were still missing, and anything alphabetic outside the table fell through to
  "Latin".

Unicode names the script of every letter, so there is nothing to maintain. And
the locale names its own scripts: a value written in a writing system that
appears nowhere else in its file is the outlier — which is what a mistranslation
looks like.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))

import i18n_script_calibration as cal  # noqa: E402


@pytest.mark.parametrize("text,expected", [
    ("file", "Latin"),
    ("файл", "Cyrillic"),
    ("ملف", "Arabic"),
    ("文件", "Han"),
    ("ファイル", "Kana"),
    ("구성", "Hangul"),
    ("ఫైల్", "Telugu"),        # the script the second table missed
    ("ಕಡತ", "Kannada"),        # and the third
    ("ഫയൽ", "Malayalam"),
    ("ਫਾਈਲ", "Gurmukhi"),
    ("ไฟล์", "Thai"),
])
def test_script_is_read_from_the_character(text, expected):
    assert cal.script_of(text) == expected


def test_punctuation_and_digits_do_not_decide_the_script():
    assert cal.script_of("1,234 — 56.7%") == "none"
    # a template's variable NAME is Latin text and does count
    assert cal.script_of("${count}") == "Latin"


def test_a_cyrillic_locale_legitimises_its_own_script():
    """Tajik/Tatar/Torbeski are Cyrillic: their values must never be 'outliers'."""
    values = ["файл"] * 50 + ["file"] * 2
    allowed = cal.locale_scripts(values)
    assert "Cyrillic" in allowed
    assert cal.is_outlier("Транскрипсияи овоз ҳанӯз даст нест.", allowed) is False


def test_a_latin_locale_rejects_a_foreign_script():
    values = ["fitxer"] * 50 + ["arxiu"] * 5
    allowed = cal.locale_scripts(values)
    assert cal.is_outlier("后端 v1.2.3", allowed) is True
    assert cal.is_outlier("구성", allowed) is True
    assert cal.is_outlier("OpenAmer ꃅꏢ v1", allowed) is True   # two Yi letters


def test_a_leaked_string_cannot_legitimise_itself():
    """Two stray Chinese values in 2000 Aragonese ones are outliers, not a script."""
    values = ["fitxer"] * 2000 + ["后端", "구성"]
    allowed = cal.locale_scripts(values)
    assert "Han" not in allowed
    assert cal.is_outlier("后端 v1", allowed) is True


def test_mixed_catalogs_keep_both_scripts():
    """Japanese is Kana + Han; a 2% share is enough to be legitimate."""
    values = ["ファイル"] * 60 + ["文件"] * 40
    allowed = cal.locale_scripts(values)
    assert {"Kana", "Han"} <= allowed


def test_a_single_foreign_letter_is_a_name_not_a_mistranslation():
    allowed = {"Latin"}
    assert cal.is_outlier("OK", allowed) is False
    assert cal.is_outlier("42", allowed) is False
    assert cal.is_outlier("Konto 中", allowed) is False
