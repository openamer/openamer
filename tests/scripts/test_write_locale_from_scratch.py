"""Regression test: a locale generated from scratch must use the table.

i18n_write_locale.mjs merges two sources: the existing locale file (which may
carry values a table cannot express) and en.ts for everything the locale does
not have yet. The second path is where the bug lived.

``mergeMissing`` passed the already-qualified path down to ``buildTree``, which
prepends its own prefix. Every key generated for a missing section therefore
resolved to ``common.common.apply`` instead of ``common.apply``. The table
lookup returned undefined for every single string and the file was written in
English — silently, with a successful exit code and a valid, type-correct file.

That is exactly the failure mode that left 136 of the 185 desktop locale
modules on main empty of translations: the writer "worked", it just ignored the
translation table for any locale it had to build from scratch.

This test pins the contract: a from-scratch locale takes its text from the table.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
I18N = REPO / "apps" / "desktop" / "src" / "i18n"
WRITER = REPO / "scripts" / "i18n_write_locale.mjs"


def _writer_available() -> bool:
    if shutil.which("node") is None:
        return False
    try:
        probe = subprocess.run(["node", "-e", "require('typescript')"],
                               cwd=str(REPO), capture_output=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return False
    return probe.returncode == 0


pytestmark = pytest.mark.skipif(
    not _writer_available(),
    reason="node with the TypeScript compiler is not available",
)


def _run_writer(tmp_path: Path, table: dict[str, str]) -> str:
    """Generate a scratch locale and return the written source.

    The target must start as ``defineLocale({})`` — that is the shape of the
    locales that were left empty (``lg``, ``wa``, ``yi``, ``co``). An *empty*
    file takes a different code path (en.ts becomes the base), so it would not
    exercise the merge that the bug lived in.
    """
    locale = tmp_path / "zz.ts"
    table_file = tmp_path / "zz.json"
    table_file.write_text(json.dumps(table, ensure_ascii=False), encoding="utf-8")
    # en.ts is resolved as a sibling of the target file, so the scratch locale
    # has to live next to it.
    target = I18N / "zz-regression-test.ts"
    target.write_text(
        "import { defineLocale } from './define-locale'\n"
        "\n"
        "export const zzRegressionTest = defineLocale({})\n",
        encoding="utf-8",
    )
    try:
        result = subprocess.run(
            ["node", str(WRITER), str(target), str(table_file)],
            cwd=str(REPO), capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=180,
        )
        assert result.returncode == 0, result.stderr[-800:]
        return target.read_text(encoding="utf-8")
    finally:
        target.unlink(missing_ok=True)


def test_top_level_and_nested_keys_take_the_translation(tmp_path: Path) -> None:
    """A key in a section the locale does not have yet must be translated."""
    source = _run_writer(tmp_path, {
        "common.apply": "ZZAPPLY",
        "common.save": "ZZSAVE",
        "settings.gateway.sshHostTitle": "ZZHOST",
    })

    assert "ZZAPPLY" in source, (
        "a leaf in a missing section fell back to English — the path was "
        "double-prefixed (common.common.apply)"
    )
    assert "ZZSAVE" in source
    assert "ZZHOST" in source, (
        "a leaf in a missing NESTED section fell back to English — every level "
        "of the merge has to pass the parent prefix"
    )


def test_untranslated_keys_keep_english(tmp_path: Path) -> None:
    """The table is not the only source: absent keys stay English, not empty."""
    source = _run_writer(tmp_path, {"common.apply": "ZZAPPLY"})

    assert "ZZAPPLY" in source
    # common.back was not in the table, so it must still be the English literal.
    assert "back: 'Back'" in source


def test_generated_file_is_valid_typescript(tmp_path: Path) -> None:
    """A generated locale must still parse — the writer reports this itself."""
    source = _run_writer(tmp_path, {"common.apply": "ZZAPPLY"})
    assert "defineLocale(" in source
    assert source.count("{") == source.count("}"), "unbalanced braces in output"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
