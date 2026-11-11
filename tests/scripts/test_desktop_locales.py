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
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
I18N = REPO / "apps" / "desktop" / "src" / "i18n"
LANGS = REPO / "locales" / "_languages.json"

def _extractor_available() -> bool:
    """True only when node can actually require the TypeScript compiler.

    ``shutil.which("node")`` is not enough: CI images ship node without the
    repo's node_modules, so the extractor dies inside require('typescript')
    with a SystemExit instead of a skip (measured on PR #346, tests slice 4:
    "literal extraction failed: ... cjs/loader").
    """
    if shutil.which("node") is None:
        return False
    try:
        probe = subprocess.run(["node", "-e", "require('typescript')"],
                               cwd=str(REPO), capture_output=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return False
    return probe.returncode == 0


needs_node = pytest.mark.skipif(
    not _extractor_available(),
    reason="node + resolvable typescript required for AST extraction")


@pytest.fixture(scope="module")
def fill():
    spec = importlib.util.spec_from_file_location(
        "fill_desktop", REPO / "scripts" / "fill_desktop_locales.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def en_literals(fill) -> dict[str, str]:
    # Skip at the fixture so a test that forgets the needs_node mark cannot fail
    # with the extractor's SystemExit instead of a clean skip.
    if not _extractor_available():
        pytest.skip("node + resolvable typescript required for AST extraction")
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


def test_locale_lock_is_exclusive(fill, tmp_path, monkeypatch):
    """A second holder of the same locale must be refused, not queued."""
    monkeypatch.setattr(fill, "HOME", tmp_path)
    with fill.locale_lock("zz") as first:
        assert first is True
        with fill.locale_lock("zz") as second:
            assert second is False
    # Released: the next run may take it.
    with fill.locale_lock("zz") as again:
        assert again is True


def test_locale_lock_steals_stale_lock(fill, tmp_path, monkeypatch):
    """A lock whose owner is dead must not block the queue forever."""
    monkeypatch.setattr(fill, "HOME", tmp_path)
    lockdir = tmp_path / "tmp" / "locks"
    lockdir.mkdir(parents=True)
    dead = subprocess.Popen([sys.executable, "-c", "pass"])
    dead.wait()
    (lockdir / "desktop-zz.lock").write_text(str(dead.pid), encoding="utf-8")

    with fill.locale_lock("zz") as owned:
        assert owned is True, "stale lock from a dead pid was not taken over"


def test_atomic_write_leaves_no_temp_file(fill, tmp_path):
    target = tmp_path / "mod.ts"
    fill.atomic_write(target, "export const x = 1\n")
    assert target.read_text(encoding="utf-8") == "export const x = 1\n"
    assert not (tmp_path / "mod.ts.tmp").exists()


def test_protocol_acronyms_are_not_prose(fill):
    """"MCP" is a protocol name, not a sentence.

    Rejecting it as "unchanged English" left four MCP labels open in every one
    of the 185 locales on every wave, so full coverage was unreachable by
    construction. Same class: CLI/TUI/SDK/GPU and the product names below.
    """
    for token in ("MCP", "CLI", "TUI", "SDK", "GPU", "Discord", "Slack",
                  "Telegram", "WhatsApp"):
        assert fill.validation_error(token, token) is None, token


def test_matrix_user_id_is_a_syntax_example(fill):
    """A Matrix id cannot be localised without becoming unparseable."""
    handle = "@openamer:example.org"
    assert fill.validation_error(handle, handle) is None


def test_prose_still_must_be_translated(fill):
    """The exemptions must stay narrow - plain English may not pass through."""
    assert fill.validation_error("Settings", "Settings") == "unchanged English"
    assert fill.validation_error("Message (⌘↵ to commit)",
                                 "Message (⌘↵ to commit)") == "unchanged English"
