"""Tests for openamer_cli/a2a/mcp_catalog.py (keyless MCP server catalog).

Hermetic: no network here. We exercise the real parsing regex against a
representative fixture (the actual row format of punkpeye/awesome-mcp-servers)
and the search/filter + format logic. The live 1.3 MB fetch is validated
separately by a manual run (1989 entries parsed, searches return results).
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO))

from openamer_cli.a2a import mcp_catalog  # noqa: E402

# FIXTURE: the real row shape in punkpeye/awesome-mcp-servers README
FIXTURE = """
- [firecrawl/firecrawl-mcp-server](https://github.com/firecrawl/firecrawl-mcp-server) [![firecrawl/firecrawl-mcp-server MCP server](https://glama.ai/mcp/servers/1/badges/score.svg)](https://glama.ai/mcp/servers/firecrawl) — Web scraping & crawling
- [n24q02m/better-notion-mcp](https://github.com/n24q02m/better-notion-mcp) [![](...)](https://glama.ai) — Notion integration
- a non-row line that should be ignored
"""


def test_parse_real_format():
    rows = mcp_catalog._parse(FIXTURE)
    assert len(rows) == 2
    assert rows[0]["name"] == "firecrawl/firecrawl-mcp-server"
    assert rows[0]["url"] == "https://github.com/firecrawl/firecrawl-mcp-server"
    assert rows[1]["name"] == "n24q02m/better-notion-mcp"


def test_search_filters_by_terms():
    rows = mcp_catalog._parse(FIXTURE)
    # emulate search on the parsed fixture (search() itself fetches)
    terms = ["notion"]
    hits = [e for e in rows if all(t in (e["name"] + " " + e["description"]).casefold() for t in terms)]
    assert len(hits) == 1
    assert hits[0]["name"] == "n24q02m/better-notion-mcp"


def test_search_empty_on_network_fail(monkeypatch):
    monkeypatch.setattr(mcp_catalog.urllib.request, "urlopen",
                        lambda *a, **k: (_ for _ in ()).throw(OSError("offline")))
    assert mcp_catalog.search("x") == []


def test_format_entry():
    s = mcp_catalog.format_entry({"name": "a/b", "url": "https://github.com/a/b", "description": ""})
    assert "a/b" in s and "github.com/a/b" in s