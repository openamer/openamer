"""Tests for the desktop locale generators.

extract_locale_literals.js parses en.ts with the TypeScript compiler; a regex
parser was tried first and silently mis-nested 281 of 2219 keys, which tsc only
caught after a 35-minute translation run. fill_desktop_locales.py translates the
result and renders defineLocale overrides.

The path separator is a unit separator (\\x1f), not a dot: en.ts contains keys
that are themselves dotted (`'keybinds.openPanel'`), and joining paths with a dot
would turn one such key into two nested ones.
"""
from __future__ import annotations

import importlib.util
import json
import re
import shutil
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
I18N = REPO / "apps" / "desktop" / "src" / "i18n"
LANGS = REPO / "locales" / "_languages.json"

needs_node = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")


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


@needs_node
def test_ast_extraction_finds_the_real_catalog(fill, en_literals):
    assert len(en_literals) >= 2000, f"only {len(en_literals)} literals extracted"
    assert en_literals[f"common{fill.SEP}apply"] == "Apply"
    assert en_literals[f"common{fill.SEP}save"] == "Save"


@needs_node
def test_extraction_skips_templated_strings(en_literals):
    """A value with ${...} carries an expression; it must never be translated."""
    templated = [k for k, v in en_literals.items() if "${" in v]
    assert not templated, f"templated values leaked: {templated[:3]}"


@needs_node
def test_dotted_keys_stay_single_segments(fill, en_literals):
    """`'keybinds.openPanel'` is ONE key, not a nested path."""
    dotted = [k for k in en_literals if "." in k and fill.SEP in k]
    assert dotted, "expected at least one key with a literal dot"
    for key in dotted:
        # The dot must sit inside a segment, never act as the separator.
        assert not any(seg == "" for seg in key.split(fill.SEP))


def test_render_roundtrip_preserves_keys(fill, en_literals):
    sample = dict(list(en_literals.items())[:40])
    rendered = fill.render(fill.unflatten(sample))
    recovered = fill.parse_literals("const x = {\n" + rendered + "\n}\n")
    assert set(recovered) == set(sample)


def test_render_quotes_non_identifier_keys(fill):
    out = fill.render(fill.unflatten({
        f"composer{fill.SEP}commandDescs{fill.SEP}/help": "x",
        f"cron{fill.SEP}labels{fill.SEP}every-15-minutes": "y",
        f"normal{fill.SEP}key": "z",
    }))
    assert "'/help':" in out, out
    assert "'every-15-minutes':" in out, out
    assert "key: 'z'" in out, out


def test_render_escapes_apostrophes(fill):
    out = fill.render(fill.unflatten({f"x{fill.SEP}name": "Avañe'ẽ"}))
    assert "\\'" in out, out


def test_every_declared_language_has_a_desktop_module():
    names = json.loads(LANGS.read_text(encoding="utf-8"))
    missing = [c for c in names if not (I18N / f"{c}.ts").is_file()]
    assert not missing, f"no desktop module for: {missing[:10]}"


def test_picker_lists_every_declared_language():
    names = json.loads(LANGS.read_text(encoding="utf-8"))
    src = (I18N / "languages.ts").read_text(encoding="utf-8")
    start = src.index("export const LOCALE_OPTIONS = [")
    end = src.index("] as const satisfies", start)
    ids = re.findall(r"^\s*id: '([^']+)'", src[start:end], re.M)
    assert len(ids) == len(names), f"picker has {len(ids)}, expected {len(names)}"
    assert set(ids) == set(names)
    assert len(ids) == len(set(ids)), "duplicate locale in the picker"
