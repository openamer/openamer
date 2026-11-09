"""Tests for the desktop locale generators.

Two generators share en.ts as their source of truth:

  * extract_locale_literals.js -- AST extraction (a regex parser was tried first
    and silently mis-nested 281 of 2219 keys, which tsc only caught after a
    35-minute translation run)
  * fill_desktop_locales.py    -- translation + module rendering

These tests pin the extraction contract and the rendering round-trip, so a
generator change cannot quietly corrupt 185 catalogs again.
"""
from __future__ import annotations

import importlib.util
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
I18N = REPO / "apps" / "desktop" / "src" / "i18n"
EN = I18N / "en.ts"
LANGS = REPO / "locales" / "_languages.json"


@pytest.fixture(scope="module")
def fill():
    spec = importlib.util.spec_from_file_location(
        "fill_desktop", REPO / "scripts" / "fill_desktop_locales.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def en_literals(fill) -> dict[str, str]:
    return fill.parse_en()


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_ast_extraction_finds_the_real_catalog(fill, en_literals):
    """The AST parse must see every static literal, not a regex approximation."""
    assert len(en_literals) >= 2000, f"only {len(en_literals)} literals extracted"
    assert en_literals["common.apply"] == "Apply"
    assert en_literals["common.save"] == "Save"


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_extraction_skips_templated_strings(en_literals):
    """Values containing ${...} must NOT be in the map -- they carry expressions."""
    templated = [k for k, v in en_literals.items() if "${" in v]
    assert not templated, f"templated values leaked into translation: {templated[:3]}"


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_every_key_is_a_dotted_path(en_literals):
    # Keys legitimately carry dashes and slashes: `every-15-minutes`,
    # `commandDescs./help`. Only the separator structure matters here.
    bad = [k for k in en_literals if not re.fullmatch(r"[^\s.]+(?:\.[^\s.]+)*", k)]
    assert not bad, f"malformed keys: {bad[:5]}"


def test_render_quotes_non_identifier_keys(fill):
    """`/help` and `every-15-minutes` must be emitted quoted or the module is invalid TS."""
    out = fill.render(fill.unflatten({"composer.commandDescs./help": "x",
                                      "cron.labels.every-15-minutes": "y",
                                      "normal.key": "z"}))
    assert "'/help':" in out, out
    assert "'every-15-minutes':" in out, out
    assert "normal: {" in out or "key:" in out, out


def test_render_roundtrip_preserves_keys(fill, en_literals):
    """unflatten -> render -> parse must give back the same key set."""
    sample = dict(list(en_literals.items())[:40])
    rendered = fill.render(fill.unflatten(sample))
    body = "const x = {\n" + rendered + "\n}\n"
    recovered = fill.parse_literals(body)
    assert set(recovered) == set(sample)
    assert recovered["common.apply"] if "common.apply" in sample else True


def test_render_escapes_apostrophes(fill):
    out = fill.render(fill.unflatten({"x.name": "Avañe'ẽ"}))
    assert "\\'" in out, out


def test_every_declared_language_has_a_desktop_module():
    names = json.loads(LANGS.read_text(encoding="utf-8"))
    missing = [c for c in names if not (I18N / f"{c}.ts").is_file()]
    assert not missing, f"no desktop module for: {missing[:10]}"


def test_picker_lists_every_declared_language():
    """The picker must carry exactly the declared set -- no gap, no alias noise."""
    names = json.loads(LANGS.read_text(encoding="utf-8"))
    src = (I18N / "languages.ts").read_text(encoding="utf-8")
    # Only the LOCALE_OPTIONS array; LOCALE_ALIASES also has `id: 'xx'` pairs.
    start = src.index("export const LOCALE_OPTIONS = [")
    end = src.index("] as const satisfies", start)
    ids = re.findall(r"^\s*id: '([^']+)'", src[start:end], re.M)
    assert len(ids) == len(names), f"picker has {len(ids)} entries, expected {len(names)}"
    assert set(ids) == set(names)
    assert len(ids) == len(set(ids)), "duplicate locale in the picker"
