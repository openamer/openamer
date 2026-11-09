"""Tests for the desktop locale-set expansion.

scripts/expand_desktop_locales.py generates one module per language plus the
catalog imports, the `Locale` union and the picker metadata from
locales/_languages.json. If any of those four outputs drifts from that file the
app either fails to typecheck or silently omits a language, so each is pinned
here -- and a second run must be a no-op.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
I18N = REPO / "apps" / "desktop" / "src" / "i18n"
LANGS = REPO / "locales" / "_languages.json"
SCRIPT = REPO / "scripts" / "expand_desktop_locales.py"


@pytest.fixture(scope="module")
def names() -> dict[str, str]:
    return json.loads(LANGS.read_text(encoding="utf-8"))


def test_locale_union_covers_every_language(names):
    src = (I18N / "types.ts").read_text(encoding="utf-8")
    m = re.search(r"^export type Locale = ([^\n]+)$", src, re.M)
    assert m, "no Locale union found"
    codes = re.findall(r"'([^']+)'", m.group(1))
    assert codes == list(names.keys()), (
        f"union has {len(codes)} codes, expected {len(names)}")


def test_catalog_imports_and_keys_cover_every_language(names):
    src = (I18N / "catalog.ts").read_text(encoding="utf-8")
    imports = re.findall(r"from '\./([^']+)'", src)
    keys = re.findall(r"^\s*'([^']+)':", src, re.M)
    expected = [c for c in names if c != "en"]
    # The catalog also imports the English baseline and its types module.
    assert sorted(imports) == sorted(expected + ["en", "types"]), (
        f"catalog imports {len(imports)}, expected {len(expected) + 2}")
    assert sorted(keys) == sorted(expected), (
        f"catalog has {len(keys)} entries, expected {len(expected)}")


def test_no_locale_module_is_missing(names):
    missing = [c for c in names if not (I18N / f"{c}.ts").is_file()]
    assert not missing, f"missing modules: {missing[:10]}"


def test_expansion_is_idempotent(names):
    """A second run must not create modules or rewrite the generated files."""
    before = {p.name: p.read_text(encoding="utf-8") for p in I18N.glob("*.ts")}
    proc = subprocess.run([sys.executable, str(SCRIPT)],
                          capture_output=True, text=True, timeout=600, cwd=str(REPO))
    assert proc.returncode == 0, proc.stderr[-500:]
    assert "modules created: 0" in proc.stdout, proc.stdout
    after = {p.name: p.read_text(encoding="utf-8") for p in I18N.glob("*.ts")}
    assert before == after, "expansion rewrote files on an idempotent run"
