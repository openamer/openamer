"""The placeholder gate must reject a lost variable, not a translated word.

Measured 2026-11-18 on `main`: `scripts/i18n_verify_locales.py` compared the
placeholder strings of a locale against English with an exact list comparison.
Every plural in every language broke it, because translating
``${count === 1 ? 'item' : 'items'}`` necessarily rewrites the words inside the
ternary. The verifier reported **891 broken placeholders across 39 locales**
and zero of them were real, while `scripts/i18n_translate_locale.py`'s
`variables_in()` had the same defect: its docstring promised
``${count === 1 ? 'item' : 'items'} -> ['count']`` but the regex returned
``['count', 'item', 'items']``.

A gate that rejects correct work is worse than no gate — it teaches everyone
to ignore the gate. These tests pin the contract: variables survive, words and
order belong to the translator.
"""
from __future__ import annotations

import importlib.util
import pathlib
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parents[2]
TRANSLATE = REPO / "scripts" / "i18n_translate_locale.py"
VERIFY = REPO / "scripts" / "i18n_verify_locales.py"


def _load(name: str, path: pathlib.Path):
    sys.path.insert(0, str(REPO / "scripts"))
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def tr():
    return _load("i18n_translate_locale", TRANSLATE)


@pytest.fixture(scope="module")
def verifier():
    return _load("i18n_verify_locales", VERIFY)


# --- variables_in: code only, never the words a translator rewrites ---------

@pytest.mark.parametrize("placeholder,expected", [
    ("${count === 1 ? 'item' : 'items'}", ["count"]),
    ("${ms !== null ? ` in ${ms}ms` : ''}", ["ms", "ms"]),
    ("${count}", ["count"]),
    ("${a}${b}", ["a", "b"]),
    ("${typeof x === 'string' ? 'a' : 'b'}", ["x"]),
])
def test_variables_in_ignores_string_literals(tr, placeholder, expected):
    assert tr.variables_in(placeholder) == expected


# --- placeholders_intact: the contract the translator is held to ------------

def test_accepts_translated_plural(tr):
    assert tr.placeholders_intact(
        "${count} attachment${count === 1 ? '' : 's'}",
        "${count} ${count === 1 ? 'Anhang' : 'Anhänge'}",
    )


def test_accepts_reordered_interpolations(tr):
    # Japanese and Korean put the object before the verb.
    assert tr.placeholders_intact("${action} ${command}", "${command} を${action}")
    assert tr.placeholders_intact(
        "Show ${count} more in ${label}",
        "在 ${label} 中再显示 ${count} 项",
    )


def test_rejects_renamed_variable(tr):
    assert not tr.placeholders_intact("${count} items", "${anzahl} Artikel")


def test_rejects_dropped_interpolation(tr):
    assert not tr.placeholders_intact("${count} items", "Artikel")
    assert not tr.placeholders_intact("${action} ${command}", "Befehl ${command}")


def test_rejects_added_interpolation(tr):
    assert not tr.placeholders_intact("Hello ${name}", "Hallo ${name} ${extra}")


# --- the verifier itself must report the same verdict ----------------------

def _leaf(path: str, text: str) -> dict:
    return {"path": path, "text": text}


def test_verifier_reports_no_broken_placeholder_for_a_translated_plural(verifier, monkeypatch):
    en = {"leaves": [
        _leaf("composer.attachments", "${count} attachment${count === 1 ? '' : 's'}"),
        _leaf("notifications.more", "${count} more ${count === 1 ? 'notification' : 'notifications'}"),
    ]}
    de = {"leaves": [
        _leaf("composer.attachments", "${count} ${count === 1 ? 'Anhang' : 'Anhänge'}"),
        _leaf("notifications.more", "${count} weitere ${count === 1 ? 'Benachrichtigung' : 'Benachrichtigungen'}"),
    ]}
    monkeypatch.setattr(verifier, "extract", lambda locale: de if locale == "de" else en)
    monkeypatch.setattr(verifier, "parse_errors", lambda locale: [])

    result = verifier.verify("de", en)
    assert result["broken_placeholders"] == []


def test_verifier_still_catches_a_genuinely_broken_plural(verifier, monkeypatch):
    en = {"leaves": [_leaf("composer.attachments", "${count} attachment${count === 1 ? '' : 's'}")]}
    de = {"leaves": [_leaf("composer.attachments", "${anzahl} ${count === 1 ? 'Anhang' : 'Anhänge'}")]}
    monkeypatch.setattr(verifier, "extract", lambda locale: de if locale == "de" else en)
    monkeypatch.setattr(verifier, "parse_errors", lambda locale: [])

    result = verifier.verify("de", en)
    assert result["broken_placeholders"] == ["composer.attachments"]
