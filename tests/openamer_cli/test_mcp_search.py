"""Tests for openamer_cli/mcp_search.py (Layer-1 catalog over installed MCPs).

Hermetic: no real MCP servers / network. We point the config at a temp
OPENAMER_HOME so installed_servers() reads a controlled mcp_servers block,
and stub _probe so tool availability is deterministic.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO))

from openamer_cli import mcp_search  # noqa: E402


@pytest.fixture
def fake_servers(tmp_path, monkeypatch):
    """Point installed_servers() at a temp OPENAMER_HOME with 2 servers."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("OPENAMER_HOME", str(home))
    cfg = home / "config.yaml"
    cfg.write_text(
        'mcp_servers:\n'
        '  salesforce:\n'
        '    enabled: true\n'
        '    command: "true"\n'
        '  notion:\n'
        '    enabled: true\n'
        '    command: "true"\n'
        '  disabledone:\n'
        '    enabled: false\n'
        '    command: "true"\n',
        encoding="utf-8",
    )

    probe_map = {
        "salesforce": [("updateRecord", "Update fields on a Salesforce object"),
                       ("upsertRecord", "Insert or update based on external ID")],
        "notion": [("searchDatabase", "Search Notion database"),
                   ("createPage", "Create a page in Notion")],
        "disabledone": [("hiddentool", "Should not appear")],
    }

    def fake_probe(name, cfg):
        return probe_map.get(name, [])

    monkeypatch.setattr(mcp_search, "_probe", fake_probe)
    return probe_map


def test_searches_across_servers_and_groups(fake_servers):
    res = mcp_search.search_tools("update")
    names = [(m["server"], m["name"]) for m in res["matches"]]
    assert ("salesforce", "updateRecord") in names
    # notion has no tool whose name+desc contains "update"
    assert all(s != "notion" for s, _ in names)
    # disabled server's tool never appears
    assert all(n != "hiddentool" for _, n in names)
    assert res["total_servers"] == 2


def test_search_across_servers_matches_shared_term(fake_servers):
    res = mcp_search.search_tools("record|database")
    subjects = {m["name"] for m in res["matches"]}
    # 'record' matches salesforce.updateRecord; 'database' matches notion.searchDatabase
    assert "updateRecord" in subjects
    assert "searchDatabase" in subjects


def test_search_server_filter(fake_servers):
    res = mcp_search.search_tools(query="", server="notion")
    assert {m["server"] for m in res["matches"]} == {"notion"}
    assert all(m["name"] in ("searchDatabase", "createPage") for m in res["matches"])


def test_no_servers(tmp_path, monkeypatch):
    home = tmp_path / "empty"
    home.mkdir()
    monkeypatch.setenv("OPENAMER_HOME", str(home))
    (home / "config.yaml").write_text("", encoding="utf-8")
    res = mcp_search.search_tools("anything")
    assert res["matches"] == [] and res["total_servers"] == 0


def test_probe_error_is_skipped_not_fatal(fake_servers, monkeypatch):
    def failing_probe(name, cfg):
        if name == "salesforce":
            raise ConnectionError("boom")
        return fake_servers[name]
    monkeypatch.setattr(mcp_search, "_probe", failing_probe)
    res = mcp_search.search_tools("page", on_probe_error="skip")
    # notion still searched despite salesforce having failed
    assert any(m["server"] == "notion" for m in res["matches"])
    assert any("salesforce" in e for e in res["probe_errors"])


def test_format_match_grouping_text():
    s = mcp_search.format_match({"server": "sf", "name": "updateRecord", "description": "x"})
    assert "sf::updateRecord" in s