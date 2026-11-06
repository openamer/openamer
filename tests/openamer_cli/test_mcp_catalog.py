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


# ─── Official registry (registry.modelcontextprotocol.io) ──────────────────


# The real response shape: {"servers": [{"server": {...}, "_meta": {...}}]},
# with remotes[] for remote-only servers and repository.url when published
# from a repo. Deprecated rows stay in the registry and must be filtered out.
REGISTRY_FIXTURE = {
    "servers": [
        {
            "server": {
                "name": "io.example/github-mcp",
                "title": "GitHub",
                "description": "GitHub issues and pull requests.",
                "version": "1.2.3",
                "repository": {"url": "https://github.com/example/github-mcp/",
                               "source": "github"},
                "remotes": [{"type": "streamable-http",
                             "url": "https://api.example.com/mcp"}],
            },
            "_meta": {"io.modelcontextprotocol.registry/official":
                      {"status": "active"}},
        },
        {
            "server": {
                "name": "io.example/remote-only",
                "description": "Web scraping, remote only.",
                "version": "0.1.0",
                "remotes": [{"type": "streamable-http",
                             "url": "https://scrape.example.com/mcp"}],
            },
            "_meta": {"io.modelcontextprotocol.registry/official":
                      {"status": "active"}},
        },
        {
            "server": {"name": "io.example/dead", "description": "Deprecated."},
            "_meta": {"io.modelcontextprotocol.registry/official":
                      {"status": "deprecated"}},
        },
    ]
}


def test_registry_entries_parses_and_filters_deprecated():
    rows = mcp_catalog._registry_entries(REGISTRY_FIXTURE)
    assert [r["id"] for r in rows] == [
        "io.example/github-mcp", "io.example/remote-only"]
    assert all(r["source"] == "registry" for r in rows)


def test_registry_entries_prefers_repo_then_remote():
    rows = mcp_catalog._registry_entries(REGISTRY_FIXTURE)
    # repo wins (trailing slash stripped), remote kept for reference
    assert rows[0]["url"] == "https://github.com/example/github-mcp"
    assert rows[0]["remote"]["type"] == "streamable-http"
    assert rows[0]["name"] == "GitHub"  # title preferred over machine name
    # remote-only server still yields a usable install target
    assert rows[1]["url"] == "https://scrape.example.com/mcp"


def test_registry_entries_absent_metadata_keeps_row():
    # A row without official _meta is not "not active" — keep it.
    rows = mcp_catalog._registry_entries(
        {"servers": [{"server": {"name": "x", "description": "d"}}]})
    assert len(rows) == 1 and rows[0]["url"] == ""


def test_registry_entries_dedupes_versions_keeping_latest():
    """The registry lists every published version; one row per server."""
    payload = {"servers": [
        {"server": {"name": "io.x/a", "description": "old", "version": "1.0.0"},
         "_meta": {"io.modelcontextprotocol.registry/official":
                   {"status": "active", "isLatest": False}}},
        {"server": {"name": "io.x/a", "description": "new", "version": "2.0.0"},
         "_meta": {"io.modelcontextprotocol.registry/official":
                   {"status": "active", "isLatest": True}}},
        {"server": {"name": "io.x/b", "description": "b", "version": "1.0.0"}},
    ]}
    rows = mcp_catalog._registry_entries(payload)
    assert [r["id"] for r in rows] == ["io.x/a", "io.x/b"]
    assert rows[0]["version"] == "2.0.0"  # isLatest wins over row order
    assert rows[0]["description"] == "new"
    assert "_latest" not in rows[0]  # internal flag never leaks to callers


def test_search_registry_source_uses_registry(monkeypatch):
    import json as _json

    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return _json.dumps(REGISTRY_FIXTURE).encode()

    seen = {}

    def _fake_urlopen(req, *a, **k):
        seen["url"] = getattr(req, "full_url", str(req))
        return _Resp()

    monkeypatch.setattr(mcp_catalog.urllib.request, "urlopen", _fake_urlopen)
    monkeypatch.setattr(mcp_catalog, "_registry_cache", {})
    monkeypatch.setattr(mcp_catalog, "_curated_cache", ({}, set()))
    hits = mcp_catalog.search("github", limit=5, source="registry")
    assert "/v0/servers" in seen["url"] and "search=github" in seen["url"]
    assert hits and hits[0]["id"] == "io.example/github-mcp"


def test_search_community_source_skips_registry(monkeypatch):
    calls = []

    def _fake_urlopen(req, *a, **k):
        calls.append(getattr(req, "full_url", str(req)))
        raise OSError("offline")

    monkeypatch.setattr(mcp_catalog.urllib.request, "urlopen", _fake_urlopen)
    assert mcp_catalog.search("x", source="community") == []
    assert all("/v0/servers" not in c for c in calls)