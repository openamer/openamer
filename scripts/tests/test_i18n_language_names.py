"""Every locale the app offers must have a name before the model sees it.

The translator did `LANGUAGE_NAMES.get(locale, locale)`, so a locale without a
name was sent as its raw ISO code: "Translate into tk". A model reading `tk` can
answer Turkmen, Tagalog or Tsonga, and it did — Khmer turned up inside Turkmen,
Korean inside Aragonese, Telugu inside Akan, Chinese inside Tongan and Yi.

Only 38 of 186 locales had a name. These tests keep that from silently
regressing: the list must cover every locale the picker offers, and a missing
name must abort the run instead of falling back to the code.
"""
from __future__ import annotations

import ast
import importlib.util
import re
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
LANGS = REPO / "apps" / "desktop" / "src" / "i18n" / "languages.ts"
TRANSLATOR = REPO / "scripts" / "i18n_translate_locale.py"


def _load():
    spec = importlib.util.spec_from_file_location("i18n_translate_locale", TRANSLATOR)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["i18n_translate_locale"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def translator():
    return _load()


def _picker_codes() -> list[str]:
    src = LANGS.read_text(encoding="utf-8")
    return re.findall(r"id:\s*'([\w-]+)'", src)


def test_every_picker_locale_has_a_prompt_name(translator):
    codes = _picker_codes()
    assert len(codes) > 150, f"only {len(codes)} locales parsed from languages.ts"
    missing = [c for c in codes if c not in translator.LANGUAGE_NAMES]
    assert not missing, (
        f"{len(missing)} locale(s) would be sent to the model as a bare code: "
        f"{missing[:12]}")


def test_the_cases_that_were_wrong_have_real_names(translator):
    """The locales that actually came back in the wrong language."""
    expected = {
        "tk": "Turkmen",      # came back in Khmer
        "an": "Aragonese",    # came back in Korean
        "ak": "Akan",         # came back in Telugu
        "to": "Tonga",        # came back in Chinese (languages.ts says Tonga)
        "ii": "Sichuan Yi",   # came back in Chinese
        "ps": "Pashto",       # came back in Romanian
        "mi": "Maori",        # came back in Polish
        "ae": "Avestan",      # came back in Azerbaijani
    }
    for code, name in expected.items():
        assert translator.LANGUAGE_NAMES.get(code) == name, (
            f"{code} is {translator.LANGUAGE_NAMES.get(code)!r}, expected {name!r}")


def test_no_name_is_ever_the_bare_code(translator):
    """A name equal to its own code is not a name."""
    same = [c for c, n in translator.LANGUAGE_NAMES.items() if c.lower() == n.lower()]
    # 'nb'/'no' style duplicates are fine; a code that IS the name is not.
    assert not [c for c in same if len(c) <= 3 and c == translator.LANGUAGE_NAMES[c]], same


def test_missing_name_aborts_instead_of_falling_back():
    """No call site may default to the bare code — checked on the AST, because
    the comment above that fix naturally quotes the old expression."""
    src = TRANSLATOR.read_text(encoding="utf-8")
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if (isinstance(func, ast.Attribute) and func.attr == "get"
                and isinstance(func.value, ast.Name)
                and func.value.id == "LANGUAGE_NAMES"
                and len(node.args) > 1):
            raise AssertionError(
                "LANGUAGE_NAMES.get(locale, <default>) is back: a locale without "
                "a name would be sent to the model as its ISO code again")
    assert "refusing to translate" in src
