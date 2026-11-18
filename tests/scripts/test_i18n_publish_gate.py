"""Publishing a locale batch must be gated, and the gate must be testable.

Measured 2026-11-18: `scripts/i18n_converge.py` writes finished translations
into the working tree and never publishes them — 9,612 strings across 38
locales sat unpublished while users read English, and the gap refilled within
the hour. `scripts/i18n_publish.py` closes it, and this file pins the decision
that protects it: nothing reaches a branch that the verifier rejects.
"""
from __future__ import annotations

import importlib.util
import pathlib
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "i18n_publish.py"


@pytest.fixture(scope="module")
def mod():
    sys.path.insert(0, str(REPO / "scripts"))
    spec = importlib.util.spec_from_file_location("i18n_publish", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules["i18n_publish"] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _row(locale: str, **over) -> dict:
    base = {"locale": locale, "leaves": 2539, "en_leaves": 2539,
            "missing_sections": [], "extra": [], "broken_placeholders": [],
            "brand": [], "translated": 2000, "untranslated": 539,
            "total_strings": 2539, "parse_errors": []}
    base.update(over)
    return base


def test_a_clean_batch_is_publishable(mod):
    ok, why = mod.judge([_row("ii"), _row("nv")])
    assert ok and "2 locale(s)" in why


def test_a_broken_placeholder_blocks_the_batch(mod):
    ok, why = mod.judge([_row("de", broken_placeholders=["composer.attachments"])])
    assert not ok and "de" in why and "broken placeholders" in why


def test_a_broken_brand_blocks_the_batch(mod):
    ok, why = mod.judge([_row("fi", brand=[["updates.applyingBody", "OpenAmeric"]])])
    assert not ok and "brand" in why


def test_extra_or_missing_leaves_block_the_batch(mod):
    assert not mod.judge([_row("zh", extra=["messaging.platformIntro.telegram"])])[0]
    assert not mod.judge([_row("zh", missing_sections=["settings.title"])])[0]


def test_a_parse_error_blocks_the_batch(mod):
    assert not mod.judge([_row("ko", parse_errors=["line 12: unexpected token"])])[0]


def test_an_unjudgeable_locale_blocks_the_batch(mod):
    ok, why = mod.judge([{"locale": "catalog.test", "fatal": "extract failed"}])
    assert not ok and "catalog.test" in why
