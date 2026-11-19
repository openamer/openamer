"""The publish gate must refuse a locale filled in the wrong writing system.

Background: on 2026-11-19 the converge job was translating `ps.ts` (Pashto) into
Romanian ("Autentifică-te o singură dată în OpenAmer Cloud") and had already
filled `ae.ts` (Avestan) with Azerbaijani. Everything the gate looked at —
placeholders, brand, missing sections — passed, because none of it asks *what
language the text is in*. Coverage went up, the catalog became unusable.

`wrong_script` closes that hole for the unambiguous cases: a locale that must be
written in Arabic, Cyrillic, Hebrew, Devanagari, Thai, Hangul or CJK script.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))


def _load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, REPO / "scripts" / filename)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def verifier():
    return _load("i18n_verify_locales", "i18n_verify_locales.py")


@pytest.fixture(scope="module")
def publisher():
    return _load("i18n_publish", "i18n_publish.py")


EN = {"cloudDesc": "Sign in once to OpenAmer Cloud and pick from the agents on your account."}


def test_pashto_with_romanian_text_is_flagged(verifier):
    tgt = {"cloudDesc": "Autentifică-te o singură dată în OpenAmer Cloud și alege unul "
                        "dintre agenții din contul tău."}
    assert verifier.wrong_script("ps", tgt, EN) == ["cloudDesc"]


def test_avestan_is_a_documented_gap_of_this_gate(verifier):
    """Avestan is transliterated in Latin letters, so script cannot judge it.

    Deliberately NOT guessed here: claiming `ae` is fine when it holds
    Azerbaijani would be worse than admitting the check cannot see it. That
    locale is covered by scripts/i18n_language_guard.py, whose tests pin the
    marker-based detection.
    """
    tgt = {"cloudDesc": "Bu tətbiqə yüklənmiş UI genişləndirmələri quruluşla birlikdə paketlənmiş."}
    assert verifier.wrong_script("ae", tgt, EN) == []
    assert "ae" not in verifier.NON_LATIN_SCRIPT


def test_correct_pashto_passes(verifier):
    tgt = {"cloudDesc": "یو ځل د OpenAmer ورېځ ته ننوځئ او د خپل حساب ایجنټونه غوره کړئ."}
    assert verifier.wrong_script("ps", tgt, EN) == []


def test_untranslated_fallback_is_not_flagged(verifier):
    """English left in place is a legitimate fallback, not a mistranslation."""
    assert verifier.wrong_script("ps", dict(EN), EN) == []


def test_short_tokens_are_not_flagged(verifier):
    assert verifier.wrong_script("ps", {"ok": "OK", "n": "42"}, {"ok": "OK", "n": "42"}) == []


@pytest.mark.parametrize("locale", ["de", "fr", "ae", "az", "torbeski"])
def test_latin_locales_have_no_rule(verifier, locale):
    """No false confidence where the check cannot be honest."""
    assert locale not in verifier.NON_LATIN_SCRIPT


def test_gate_refuses_the_batch(publisher):
    rows = [{"locale": "ps", "wrong_script": ["cloudDesc", "cloudNeedsSignIn"]}]
    ok, why = publisher.judge(rows)
    assert ok is False
    assert "wrong writing system" in why


def test_gate_passes_a_clean_batch(publisher):
    ok, why = publisher.judge([{"locale": "ps", "wrong_script": []}])
    assert ok is True
