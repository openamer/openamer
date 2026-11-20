"""Brand names are not vocabulary - the converge pass must restore them.

Measured 2026-11-20, 22:28 converge run: the model translated brand names in 17
catalogs (72 values). The shipped UI read `Onenigheid` for Discord in Afrikaans,
`Slap` for Slack and `Cikan` for Telegram in Bambara. The English source is the
anchor: when `en[path]` is itself a brand, the value at that path must be that
brand.

The repair is a pure function so the rule can be tested without node or a
catalog on disk; `strip_brand_names_in_catalog` only adds the write.
"""
from __future__ import annotations

import importlib.util
import pathlib
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "i18n_deliver_locales.py"


@pytest.fixture(scope="module")
def mod():
    sys.path.insert(0, str(REPO / "scripts"))
    spec = importlib.util.spec_from_file_location("i18n_deliver_locales", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_translated_brand_is_restored(mod):
    """The exact measured damage: Afrikaans and Bambara catalogs."""
    en = {"settings.channels.discord": "Discord",
          "settings.channels.slack": "Slack",
          "settings.channels.telegram": "Telegram"}
    cur = {"settings.channels.discord": "Onenigheid",
           "settings.channels.slack": "Slap",
           "settings.channels.telegram": "Cikan"}

    assert mod.brand_fixes(cur, en) == {
        "settings.channels.discord": "Discord",
        "settings.channels.slack": "Slack",
        "settings.channels.telegram": "Telegram",
    }


def test_correct_brand_is_left_alone(mod):
    en = {"a.discord": "Discord", "a.slack": "Slack"}
    cur = {"a.discord": "Discord", "a.slack": "Slack"}

    assert mod.brand_fixes(cur, en) == {}


def test_canonical_spelling_wins_over_case(mod):
    """A locale that lowercased the brand is still wrong - restore the spelling."""
    en = {"a.github": "GitHub"}
    cur = {"a.github": "github"}

    assert mod.brand_fixes(cur, en) == {"a.github": "GitHub"}


def test_ordinary_word_is_not_treated_as_a_brand(mod):
    """`signal` is only a brand when the ENGLISH value is the brand.

    Anchoring on the key name alone would rewrite real copy: `signal` in
    `errors.noSignal` is a word, not the messenger.
    """
    en = {"errors.noSignal": "No signal",
          "errors.weakSignal": "Weak signal"}
    cur = {"errors.noSignal": "Kein Signal",
           "errors.weakSignal": "Schwaches Signal"}

    assert mod.brand_fixes(cur, en) == {}


def test_missing_english_path_is_skipped(mod):
    """A path the English catalog does not have cannot be judged."""
    en = {}
    cur = {"a.discord": "Onenigheid"}

    assert mod.brand_fixes(cur, en) == {}


def test_empty_english_value_is_skipped(mod):
    en = {"a.discord": "   "}
    cur = {"a.discord": "Onenigheid"}

    assert mod.brand_fixes(cur, en) == {}


def test_repair_is_idempotent(mod):
    """Running the pass twice must not report work the second time."""
    en = {"a.slack": "Slack"}
    cur = {"a.slack": "Slap"}

    first = mod.brand_fixes(cur, en)
    assert first == {"a.slack": "Slack"}
    assert mod.brand_fixes({**cur, **first}, en) == {}
