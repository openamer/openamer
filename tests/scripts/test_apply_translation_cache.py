"""The cache merge must never regenerate a locale module.

A previous version rebuilt the file as `"export default " + render(unflatten(...))`.
That dropped the defineLocale() wrapper, the imports and all 302 interpolated
arrow-function translations of every module it touched - invalid TypeScript, and
measured as 27 corrupted modules on 2026-11-11. These tests pin the contract:
only leaf values change, everything else stays byte-identical.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SEP = "\x1f"

MODULE = """import { defineLocale } from './define-locale'
import { FIELD_LABELS } from './field-copy/zz'

// zz - generated from en.ts
export const zz = defineLocale({
  common: {
    save: 'Save',
    apply: 'Apply',
  },
  settings: {
    nav: {
      mcp: 'MCP',
      help: 'Help',
    },
  },
  preview: {
    linkHint: link => `Open ${link} in the preview pane`,
  },
})
"""


@pytest.fixture(scope="module")
def apply(fill_module):
    spec = importlib.util.spec_from_file_location(
        "apply_cache", REPO / "scripts" / "apply_translation_cache.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def fill_module():
    spec = importlib.util.spec_from_file_location(
        "fill_desktop", REPO / "scripts" / "fill_desktop_locales.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_replaces_only_the_target_leaf(apply):
    patched, added, missing = apply.patch_module(
        MODULE, {"common" + SEP + "save": "Übersetzen"})

    assert added == 1
    assert missing == []
    assert "save: 'Übersetzen'," in patched
    assert "apply: 'Apply'," in patched, "a sibling value was modified"
    assert patched.count("\n") == MODULE.count("\n"), "line count changed"


def test_keeps_imports_wrapper_and_functions(apply):
    patched, _, _ = apply.patch_module(
        MODULE, {"settings" + SEP + "nav" + SEP + "help": "Hilfe"})

    assert patched.startswith("import { defineLocale }")
    assert "import { FIELD_LABELS } from './field-copy/zz'" in patched
    assert "export const zz = defineLocale({" in patched
    assert "linkHint: link => `Open ${link} in the preview pane`," in patched
    assert "help: 'Hilfe'," in patched


def test_reports_unmatched_keys(apply):
    _, added, missing = apply.patch_module(
        MODULE, {"does" + SEP + "not" + SEP + "exist": "x"})
    assert added == 0
    assert missing == ["does" + SEP + "not" + SEP + "exist"]


def test_escapes_quotes_and_backslashes(apply):
    patched, added, _ = apply.patch_module(
        MODULE, {"common" + SEP + "apply": "it's a \\ path"})
    assert added == 1
    assert r"apply: 'it\'s a \\ path'," in patched
