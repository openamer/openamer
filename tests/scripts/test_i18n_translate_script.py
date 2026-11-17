"""The translator must be told which writing system to use.

Measured 2026-11-17: a batch for `ps` (Pashto, Perso-Arabic) came back in
**Cyrillic**, and `ve` (Venda, Latin) came back in **CJK**. The delivery gate
rejected both, so those locales made zero progress while burning API calls. The
prompt only said "translate into Pashto"; naming the script removes the freedom
to answer in a neighbouring language's alphabet.
"""
from __future__ import annotations

import importlib.util
import pathlib
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "i18n_translate_locale.py"


@pytest.fixture(scope="module")
def mod():
    sys.path.insert(0, str(REPO / "scripts"))
    spec = importlib.util.spec_from_file_location("i18n_translate_locale", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules["i18n_translate_locale"] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_arabic_script_locale_names_the_script(mod):
    req = mod.script_requirement("ps")
    assert "Perso-Arabic" in req
    assert "other writing system" in req


def test_latin_locale_pins_the_latin_alphabet(mod):
    req = mod.script_requirement("ve")
    assert "Latin alphabet" in req


def test_bilingual_locale_names_both_scripts(mod):
    req = mod.script_requirement("ks")
    assert "Perso-Arabic" in req and "Devanagari" in req


def test_unknown_locale_gets_no_requirement(mod):
    assert mod.script_requirement("zz-not-a-locale") == ""


def test_foreign_ratio_flags_a_cyrillic_batch_for_pashto(mod):
    good = ["تنظیمات", "بندول"]
    bad = ["Настройки", "Закрыть"]
    assert mod.foreign_ratio(good, "ps") == 0.0
    assert mod.foreign_ratio(bad, "ps") == 1.0


def test_foreign_ratio_ignores_english_and_empty(mod):
    assert mod.foreign_ratio(["", "OpenAmer Desktop v1"], "ps") == 0.0


def test_delivery_drops_bad_cache_entries_instead_of_the_whole_locale(tmp_path):
    """13 transliterated words must not block 2 500 correct ones.

    Measured 2026-11-17: the `ps` cache held 2 521 Pashto values plus 13 that
    spelled "agent" with Cyrillic letters. The delivery gate rejected the whole
    catalog, so the locale stayed at 41.2% while burning translation calls.
    """
    import json

    sys.path.insert(0, str(REPO / "scripts"))
    spec = importlib.util.spec_from_file_location(
        "i18n_deliver_locales", REPO / "scripts" / "i18n_deliver_locales.py")
    deliver_mod = importlib.util.module_from_spec(spec)
    sys.modules["i18n_deliver_locales"] = deliver_mod
    assert spec.loader is not None
    spec.loader.exec_module(deliver_mod)

    deliver_mod.TMP = tmp_path
    cache = tmp_path / "i18n_ps_translations.json"
    cache.write_text(json.dumps({
        "a": "تنظیمات",                                    # good Pashto
        "b": "ستاسو حساب په агенټونو کشف کړئ،",            # Cyrillic contamination
        "c": "بندول",                                       # good Pashto
    }, ensure_ascii=False), encoding="utf-8")

    dropped = deliver_mod.drop_foreign_values("ps")
    assert dropped == 1
    kept = json.loads(cache.read_text(encoding="utf-8"))
    assert set(kept) == {"a", "c"}
    assert all("аген" not in v for v in kept.values())
