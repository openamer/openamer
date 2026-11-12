"""Tests for the locale-set expansion.

The advertised language list and the on-disk catalogs must never drift: a code
in agent/i18n.py with no locales/<code>.yaml makes the suite red and ships a
language that silently falls back to English.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
LANGS = REPO / "locales" / "_languages.json"


@pytest.fixture(scope="module")
def names() -> dict[str, str]:
    return json.loads(LANGS.read_text(encoding="utf-8"))


def test_language_file_is_valid_and_nonempty(names):
    assert len(names) >= 180, f"only {len(names)} languages declared"
    assert names["en"] == "English"
    assert names["zh-hant"] == "Traditional Chinese"


def test_every_code_looks_like_a_locale_tag(names):
    # ISO 639-1 is two lowercase letters; zh-hant is the one script subtag.
    # Torbeski has no ISO code and is an intentional OpenAmer application
    # locale, not a malformed language tag.
    bad = [
        c for c in names
        if c != "torbeski" and not re.fullmatch(r"[a-z]{2}(?:-[a-z]{4})?", c)
    ]
    assert not bad, f"malformed locale codes: {bad}"


def test_every_declared_language_has_a_catalog(names):
    missing = [c for c in names if not (REPO / "locales" / f"{c}.yaml").is_file()]
    assert not missing, f"advertised without a catalog: {missing}"


def test_supported_languages_matches_the_json(names):
    sys.path.insert(0, str(REPO))
    try:
        from agent import i18n
    finally:
        sys.path.remove(str(REPO))
    assert list(i18n.SUPPORTED_LANGUAGES) == list(names.keys())


def test_expand_script_is_idempotent():
    """A second run must report nothing to add and touch no catalog."""
    before = sorted(p.name for p in (REPO / "locales").glob("*.yaml"))
    proc = subprocess.run([sys.executable, str(REPO / "scripts" / "expand_locale_set.py")],
                          capture_output=True, text=True, timeout=180)
    assert proc.returncode == 0, proc.stderr
    assert "to add          : 0" in proc.stdout, proc.stdout
    assert "created catalogs : 0" in proc.stdout, proc.stdout
    assert sorted(p.name for p in (REPO / "locales").glob("*.yaml")) == before
