"""Tests for openamer_cli/a2a/mcp_catalog.py (keyless MCP server catalog).

Hermetic: no network here. We exercise the real parsing regex against a
representative fixture (the actual row format of punkpeye/awesome-mcp-servers)
and the search/filter + format logic, including description extraction. The
live 1.3 MB fetch is validated separately by a manual run.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO))

from openamer_cli.a2a import mcp_catalog  # noqa: E402

# FIXTURE: the real row shape in punkpeye/awesome-mcp-servers README:
# - [name](github) [![badge](glama-svg)](glama-link) <emoji hints> - description
# Descriptions may contain inline markdown links / backticks. The third row has
# no description (only name + github + badge) — exercises the empty-desc path.
FIXTURE = """\n
- [firecrawl/firecrawl-mcp-server](https://github.com/firecrawl/firecrawl-mcp-server) [![firecrawl/firecrawl-mcp-server MCP server](https://glama.ai/mcp/servers/1/badges/score.svg)](https://glama.ai/mcp/servers/firecrawl) 📇 ☁️ 🐧 - Web scraping & crawling. See [docs](https://firecrawl.dev) for setup. Install: `pip install firecrawl-py`.
- [featurebase/featurebase-mcp](https://github.com/featurebase/featurebase-mcp) [![featurebase MCP server](https://glama.ai/mcp/servers/featurebase/badges/score.svg)](https://glama.ai/mcp/servers/featurebase) 🌎 - Chat with your database, run semantic search on your data with no code.
- [n24q02m/better-notion-mcp](https://github.com/n24q02m/better-notion-mcp) [![](...)](https://glama.ai)
- a non-row line that should be ignored
"""


def test_parse_real_format():
    rows = mcp_catalog._parse(FIXTURE)
    assert len(rows) == 3
    assert rows[0]["name"] == "firecrawl/firecrawl-mcp-server"
    assert rows[0]["url"] == "https://github.com/firecrawl/firecrawl-mcp-server"
    assert rows[1]["name"] == "featurebase/featurebase-mcp"
    assert rows[2]["name"] == "n24q02m/better-notion-mcp"


def test_description_extracted_and_cleaned():
    rows = mcp_catalog._parse(FIXTURE)
    # Emoji hints + leading dash stripped; markdown link flattened to its label;
    # backticks removed.
    assert rows[0]["description"] == (
        "Web scraping & crawling. See docs for setup. Install: pip install firecrawl-py."
    )
    assert rows[1]["description"] == (
        "Chat with your database, run semantic search on your data with no code."
    )
    # No description present -> empty string (not None / not the emoji strip).
    assert rows[2]["description"] == ""


def test_description_matches_phrase():
    # The phrase appears only inside a description, not in the name — this is
    # the whole point of the description extraction.
    rows = mcp_catalog._parse(FIXTURE)
    hits = mcp_catalog._matches_slice(rows, '"semantic search"')
    assert len(hits) == 1
    assert hits[0]["name"] == "featurebase/featurebase-mcp"
    hits2 = mcp_catalog._matches_slice(rows, '"database"')
    assert len(hits2) == 1
    assert hits2[0]["name"] == "featurebase/featurebase-mcp"


def test_search_filters_by_terms():
    rows = mcp_catalog._parse(FIXTURE)
    # emulate search on the parsed fixture (search() itself fetches)
    hits = mcp_catalog._matches_slice(rows, "notion")
    assert len(hits) == 1
    assert hits[0]["name"] == "n24q02m/better-notion-mcp"


def test_search_empty_on_network_fail(monkeypatch):
    monkeypatch.setattr(mcp_catalog.urllib.request, "urlopen",
                        lambda *a, **k: (_ for _ in ()).throw(OSError("offline")))
    assert mcp_catalog.search("x") == []


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
    # OR alternative matches through the | split (split at tokenize time)
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


def test_format_entry_truncates_long_description():
    longd = "x" * 300
    s = mcp_catalog.format_entry({
        "name": "a/b", "url": "", "description": longd})
    assert len(s) <= 200