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


# ─── New: query syntax (phrases / OR / AND) ────────────────────────────────


def test_tokenize_clauses_handles_phrases_or_and():
    # AND of two bare terms
    assert mcp_catalog._tokenize_clauses("github api") == [["github"], ["api"]]
    # OR alternatives inside one term
    assert mcp_catalog._tokenize_clauses("postgres|mysql") == [["postgres", "mysql"]]
    # quoted phrase becomes one exact substring, casefolded
    assert mcp_catalog._tokenize_clauses('"Web Scraping"') == [["web scraping"]]
    # mixed
    assert mcp_catalog._tokenize_clauses('github "api|docs" python') == [
        ["github"], ["api|docs"], ["python"]]


def test_matches_requires_every_clause_and_any_alternative():
    e = {"name": "foo/bar", "description": "GitHub API client"}
    assert mcp_catalog._matches(e, [["github"]]) is True
    assert mcp_catalog._matches(e, [["github"], ["api"]]) is True
    # second clause not present -> False (AND)
    assert mcp_catalog._matches(e, [["github"], ["postgres"]]) is False
    # OR alternative matches through the | split (split happens at tokenize time,
    # so _matches receives already-separated alternatives)
    assert mcp_catalog._matches(e, [["postgres", "api"]]) is True
    assert mcp_catalog._matches(e, [["postgres", "notion"]]) is False
    # full pipeline: tokenize("postgres|api") -> [["postgres","api"]]
    clauses = mcp_catalog._tokenize_clauses("postgres|api")
    assert mcp_catalog._matches(e, clauses) is True
    assert mcp_catalog._tokenize_clauses("postgres|api") == [["postgres", "api"]]


def test_annotate_attaches_curated_and_installed(monkeypatch):
    # No real curated-catalog IO: stub the index with a known github tail.
    monkeypatch.setattr(
        mcp_catalog, "_curated_cache",
        ({"n24q02m/better-notion-mcp": "better-notion-mcp"}, {"better-notion-mcp"}))
    entries = [
        {"name": "n24q02m/better-notion-mcp", "url": "https://github.com/n24q02m/better-notion-mcp", "description": ""},
        {"name": "foo/bar", "url": "https://github.com/foo/bar", "description": ""},
    ]
    out = mcp_catalog._annotate(entries)
    assert out[0]["curated"] == "better-notion-mcp"
    assert out[1]["curated"] is None
    # curated/installed keys always present
    assert all("curated" in e and "installed" in e for e in out)


def test_format_entry_shows_approved_badge():
    s = mcp_catalog.format_entry({
        "name": "blender", "url": "https://github.com/ahujasid/blender-mcp",
        "description": "", "curated": "blender", "installed": True})
    assert "approved: openamer mcp install blender" in s
    assert "[installed]" in s
