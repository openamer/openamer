"""openamer_cli/a2a/mcp_catalog.py — browse the MCP server catalog (keyless).

Fetches the largest curated, keyless list of MCP (Model Context Protocol)
servers — punkpeye/awesome-mcp-servers (raw, ~1.3 MB) — and lets the agent
search it by keyword, so OpenAmer can find a ready-made tool instead of always
building one. No API key, no fragile UI scraping.

Format (markdown table): | name | description | [stars/mcp] | [github] | [announcement] |
We parse rows; github links are the primary install target.
"""
from __future__ import annotations

import re
import subprocess
import urllib.request

RAW = ("https://raw.githubusercontent.com/punkpeye/awesome-mcp-servers/"
       "main/README.md")
CACHE = None  # module-level cache (per process)


def _fetch(raw: str = RAW, timeout: float = 25.0) -> str:
    global CACHE
    if CACHE is not None:
        return CACHE
    req = urllib.request.Request(raw, headers={"User-Agent": "openamer-mcp-catalog/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        CACHE = r.read().decode("utf-8", "replace")
    return CACHE


_ROW_RE = re.compile(
    r"-\s*\[([^\]]+)\]\((https://github\.com/[^)]+)\)\s*\[!\[",
    re.M)


def _parse(text: str) -> list[dict]:
    out = []
    for m in _ROW_RE.finditer(text):
        name, url = m.group(1), m.group(2)
        if not name or not url:
            continue
        out.append({"name": name, "url": url, "description": ""})
    return out


def search(query: str, *, raw: str = RAW, limit: int = 10, timeout: float = 25.0) -> list:
    """Return MCP-server entries whose name/description contain query terms."""
    terms = [t for t in query.casefold().split() if t]
    try:
        text = _fetch(raw, timeout)
    except Exception:
        return []
    entries = _parse(text)
    if not terms:
        return entries[:limit]
    hits = [e for e in entries if all(t in (e["name"] + " " + e["description"]).casefold() for t in terms)]
    return hits[:limit]


def format_entry(e: dict) -> str:
    gh = ""
    if "github" in e.get("url", "").lower():
        gh = f"  [{e['url']}]"
    return f"- **{e['name']}** — {e['description'][:110]}{gh}"