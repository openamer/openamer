"""Tests for docs/ai-catalog.json + docs/.well-known/ai-catalog.json (ARD interop).

Hermeisch: no network. Verifies the two published ARD catalog files are valid
JSON and conform to the ARD ai-catalog contract (specVersion/host/entries and
per-entry identifier URN + discovery signals).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO))

FILES = [
    REPO / "docs" / "ai-catalog.json",
    REPO / "docs" / ".well-known" / "ai-catalog.json",
]


@pytest.mark.parametrize("path", FILES)
def test_catalog_is_valid_json_and_conformant(path):
    assert path.exists(), f"missing {path.name}"
    d = json.loads(path.read_text(encoding="utf-8"))
    # ARD ai-catalog top-level contract
    assert {"specVersion", "host", "entries"} <= set(d.keys())
    # host must be the Pages host for the repo
    assert d["host"] == "https://openamer.github.io/openamer"
    assert len(d["entries"]) >= 1
    e = d["entries"][0]
    for k in ("identifier", "displayName", "type", "url", "description"):
        assert e.get(k), f"{path.name}: missing entry.{k}"
    assert e["identifier"].startswith("urn:air:"), "identifier must be ARD URN"
    # discovery signals (what makes it searchable)
    assert len(e.get("representativeQueries", [])) >= 2
    assert e.get("capabilities")


def test_root_and_wellknown_catalogs_match():
    a = json.loads(FILES[0].read_text(encoding="utf-8"))
    b = json.loads(FILES[1].read_text(encoding="utf-8"))
    # same catalog exposed at both paths (Root is the Pages-servable one)
    assert a["entries"][0]["identifier"] == b["entries"][0]["identifier"]
    assert a["entries"][0]["displayName"] == b["entries"][0]["displayName"]