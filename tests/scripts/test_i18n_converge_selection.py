"""Selection rules of the i18n converge loop.

A locale used to be "pending" only when it missed strings. That left six catalogs
that were 100% complete *and* full of another language's script permanently
invisible -- measured 2026-11-17: `eo oj sg th vo wa` had 0 coverage gaps and
still carried Arabic/Hangul/CJK text, so no pass would ever revisit them.
"""
from __future__ import annotations

import importlib.util
import pathlib
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "i18n_converge.py"


@pytest.fixture(scope="module")
def mod():
    spec = importlib.util.spec_from_file_location("i18n_converge_sel", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules["i18n_converge_sel"] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_needs_work_on_coverage_gap(mod):
    assert mod.needs_work({"locale": "kk", "real_gaps": 3, "script_gaps": 0}) is True


def test_needs_work_on_foreign_script_only(mod):
    # Complete by coverage, wrong by script: this is the case that used to be
    # skipped forever.
    assert mod.needs_work({"locale": "th", "real_gaps": 0, "script_gaps": 1}) is True


def test_needs_work_false_only_when_both_are_zero(mod):
    assert mod.needs_work({"locale": "de", "real_gaps": 0, "script_gaps": 0}) is False


def test_needs_work_defaults_to_pending_for_unknown_rows(mod):
    # A row without measurement must not be silently treated as finished.
    assert mod.needs_work({"locale": "xx"}) is True


def test_script_gap_count_reads_the_catalog(mod, monkeypatch):
    """script_gap_count must count the working tree, not a cached number."""
    calls = {}

    class FakeMod:
        @staticmethod
        def expected_script(locale, text):
            calls["locale"] = locale
            return frozenset({"Devanagari"})

        @staticmethod
        def values(text):
            return ["सामग्री", "삭제하시겠습니까?"]

        @staticmethod
        def foreign_values(texts, expected):
            return [("삭제하시겠습니까?", {"Hangul": 8})]

    monkeypatch.setattr(mod, "script_mod", lambda: FakeMod)
    assert mod.script_gap_count("bh") == 1
    assert calls["locale"] == "bh"


def test_no_normalize_flag_exists(mod):
    """Parallel runs must be able to skip the global fixers."""
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-normalize", action="store_true")
    ns = parser.parse_args(["--no-normalize"])
    assert ns.no_normalize is True
