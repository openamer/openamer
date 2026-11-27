"""The public language index must match the locale data, never a hand-typed number.

Measured 2026-11-27: the landing page advertised 188 UI locales while the
repository carried 186 (184 ISO 639-1 + zh-hant + torbeski). A count in prose is
a number nobody re-measures, so the page is generated from the catalogs and this
test fails the moment it drifts.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "build_language_index.py"
INDEX = REPO / "website" / "static" / "api" / "languages.json"
PAGE = REPO / "website" / "docs" / "reference" / "languages.md"


def _index() -> dict:
    return json.loads(INDEX.read_text(encoding="utf-8"))


def test_artifacts_are_up_to_date() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--check"],
        cwd=REPO,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"language index is stale -- run `python scripts/build_language_index.py`\n"
        f"{result.stdout}{result.stderr}"
    )


def test_every_declared_locale_is_indexed() -> None:
    declared = json.loads((REPO / "locales" / "_languages.json").read_text(encoding="utf-8"))
    indexed = {row["code"] for row in _index()["languages"]}
    assert indexed == set(declared)


def test_summary_matches_the_index() -> None:
    data = _index()
    summary = data["summary"]
    rows = data["languages"]
    assert summary["locales_total"] == len(rows)
    assert summary["iso_639_1_two_letter"] == sum(1 for row in rows if len(row["code"]) == 2)
    assert summary["desktop_registered"] == sum(1 for row in rows if row["desktop"]["registered"])
    # The baseline language is 0% "translated" by definition and must not be
    # reported as an untranslated gap.
    assert "en" not in summary["fully_english_locales"]


def test_page_lists_every_locale() -> None:
    page = PAGE.read_text(encoding="utf-8")
    for row in _index()["languages"]:
        assert f"| `{row['code']}` |" in page, row["code"]
