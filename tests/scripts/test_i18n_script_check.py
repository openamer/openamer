"""Tests for scripts/i18n_script_check.py.

The tool exists because the converge loop called catalogs "complete" while they
carried another language's script. These tests pin the three judgements that
made it wrong before:

  * punctuation and digits inside a script block are NOT that script
  * Han + Kana are one family (Japanese mixes them)
  * a Latin-script locale expects Latin, even when its committed catalog is
    already contaminated (Navajo had Cherokee + Hangul)
"""
from __future__ import annotations

import importlib.util
import pathlib
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "i18n_script_check.py"


@pytest.fixture(scope="module")
def mod():
    spec = importlib.util.spec_from_file_location("i18n_script_check", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules["i18n_script_check"] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_letter_script_ignores_punctuation_and_digits(mod):
    # Arabic comma U+060C and Arabic-Indic digit ٣ sit inside the Arabic block
    # but are not Arabic language content.
    assert mod.letter_script("\u060c") is None
    assert mod.letter_script("\u0663") is None
    assert mod.letter_script("3") is None
    assert mod.script_of("\u060c") == "Arabic"


def test_letter_script_only_letters(mod):
    assert mod.letter_script("ж") == "Cyrillic"
    assert mod.letter_script("ب") == "Arabic"
    assert mod.letter_script("ก") == "Thai"
    assert mod.letter_script("a") is None


def test_han_and_kana_are_one_family(mod):
    assert mod.letter_script("漢") == "CJK"
    assert mod.letter_script("か") == "CJK"
    assert mod.letter_script("カ") == "CJK"
    # Japanese is not a foreign-script catalog
    assert mod.expected_script("ja", "") == "CJK"


def test_latin_locale_expects_latin(mod):
    # ku/nv/mh had contaminated baselines; the map must win over the baseline.
    assert mod.expected_script("nv", "\u13a0" * 400) is None
    assert mod.expected_script("mh", "б" * 400) is None


def test_non_latin_locale_expects_its_script(mod):
    assert mod.expected_script("ab", "") == "Cyrillic"
    assert mod.expected_script("dz", "") == "Tibetan"
    assert mod.expected_script("dv", "") == "Thaana"
    assert mod.expected_script("kn", "") == "Kannada"


def test_foreign_values_flags_wrong_script(mod):
    texts = [
        "${name} 삭제하시겠습니까?",          # Korean in a Devanagari catalog
        "${label} के लिए क्रिया",             # correct
        "OpenAmer Desktop v${version}",       # Latin is always tolerated
    ]
    bad = mod.foreign_values(texts, "Devanagari")
    assert len(bad) == 1
    assert bad[0][1] == {"Hangul": 8}


def test_foreign_values_tolerates_short_borrowings(mod):
    # Two stray letters are a loanword, not a language switch.
    assert mod.foreign_values(["ok 漢"], "Cyrillic") == []


def test_baseline_fallback_needs_dominance(mod):
    # Fragmented baseline (no single script >=90%) must not define an expectation.
    fragmented = '"' + "\u13a0\u13a1" * 10 + "б" * 10 + "\u0d15\u0d16" * 10 + '"'
    assert mod.expected_script("zz-unknown", fragmented) is None
