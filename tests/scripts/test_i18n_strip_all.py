"""`catalog.test.ts` and `languages.ts` live next to the catalogs but are not locales.

Measured 2026-11-17: a glob over `*.ts` reported 39 "catalogs with foreign-script
values" instead of 36, and two of them were helper files that must never be
rewritten by a translation cleanup. The parser is stubbed here so the test
covers the selection rule itself, not the TypeScript reader.
"""
from __future__ import annotations

import importlib.util
import pathlib
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "i18n_strip_all.py"


@pytest.fixture(scope="module")
def mod():
    sys.path.insert(0, str(REPO / "scripts"))
    spec = importlib.util.spec_from_file_location("i18n_strip_all", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def stubbed(mod, tmp_path, monkeypatch):
    for name in ("xx", "yy", "catalog.test", "languages"):
        (tmp_path / f"{name}.ts").write_text(name, encoding="utf-8")
    monkeypatch.setattr(mod, "I18N", tmp_path)
    monkeypatch.setattr(mod, "locales", lambda: ["xx", "yy"])
    monkeypatch.setattr(mod, "values", lambda text: {"k": text})
    monkeypatch.setattr(mod, "expected_script", lambda loc, text: frozenset({"Latin"}))
    monkeypatch.setattr(
        mod, "foreign_values",
        lambda vals, expected: [("脏", {"CJK": 1})] if "yy" in "".join(vals.values()) else [])
    return mod


def test_helper_files_are_not_treated_as_locales(stubbed):
    dirty = dict(stubbed.dirty_locales())
    assert "catalog.test" not in dirty
    assert "languages" not in dirty
    assert dirty == {"yy": 1}


def test_clean_locale_is_absent(stubbed):
    assert "xx" not in dict(stubbed.dirty_locales())


def test_missing_catalog_is_skipped(stubbed, monkeypatch):
    monkeypatch.setattr(stubbed, "locales", lambda: ["xx", "zz"])
    assert "zz" not in dict(stubbed.dirty_locales())
