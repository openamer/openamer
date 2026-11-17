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
import urllib.error

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


def test_retry_after_header_is_honoured(mod):
    class Err(Exception):
        headers = {"Retry-After": "7"}

    assert mod._retry_after_seconds(Err()) == 7.0


def test_retry_after_absent_or_garbage_gives_none(mod):
    class Err(Exception):
        headers = {"Retry-After": "soon"}

    class NoHeaders(Exception):
        pass

    assert mod._retry_after_seconds(Err()) is None
    assert mod._retry_after_seconds(NoHeaders()) is None


def test_call_model_retries_a_429_then_succeeds(mod, monkeypatch):
    """A 429 is "come back later", not a failure.

    Measured 2026-11-17: with >2 parallel chains the free backends answer 429 and
    the batch was dropped, because `call_model` had no retry at all.
    """
    calls = {"n": 0}

    class FakeResp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return b'{"choices":[{"message":{"content":"[\'Hallo\']"}}]}'

    def fake_urlopen(req, timeout=0):
        calls["n"] += 1
        if calls["n"] == 1:
            raise urllib.error.HTTPError(req.full_url, 429, "Too Many Requests", {}, None)
        return FakeResp()

    monkeypatch.setattr(mod.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(mod.time, "sleep", lambda s: None)
    out = mod.call_model("http://x/v1", "m", "k", [{"role": "user", "content": "hi"}])
    assert calls["n"] == 2
    assert "Hallo" in out


def test_call_model_does_not_retry_a_400(mod, monkeypatch):
    calls = {"n": 0}

    def fake_urlopen(req, timeout=0):
        calls["n"] += 1
        raise urllib.error.HTTPError(req.full_url, 400, "Bad Request", {}, None)

    monkeypatch.setattr(mod.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(mod.time, "sleep", lambda s: None)
    with pytest.raises(urllib.error.HTTPError):
        mod.call_model("http://x/v1", "m", "k", [{"role": "user", "content": "hi"}])
    assert calls["n"] == 1


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
