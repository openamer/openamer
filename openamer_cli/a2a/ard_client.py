"""ARD client — search the public HF Agentic Resource Discovery registry.

Makes OpenAmer an ACTIVE ARD user (not just an entry): it can query a conformant
ARD discovery service (default: HuggingFace's public one) to find agents,
skills, MCP servers and other agentic resources by natural-language query.

Verified endpoint (real):
    POST https://huggingface-hf-discover.hf.space/search
    body SearchRequest: {"query":{"text":"..."},"pageSize":N}

No API key required.
"""
from __future__ import annotations

import json
import urllib.request

DEFAULT_REGISTRY = "https://huggingface-hf-discover.hf.space/search"


def search(query: str, *, registry: str = DEFAULT_REGISTRY,
           page_size: int = 5, timeout: float = 20.0) -> dict:
    """Query an ARD discovery registry. Returns the parsed SearchResponse."""
    body = json.dumps({"query": {"text": query}, "pageSize": page_size}).encode("utf-8")
    req = urllib.request.Request(
        registry, data=body, method="POST",
        headers={"Content-Type": "application/json",
                 "Accept": "application/json",
                 "User-Agent": "openamer-ard-client/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8", "replace"))


def search_results(query: str, *, registry: str = DEFAULT_REGISTRY,
                   page_size: int = 5, timeout: float = 20.0) -> list:
    """Return the list of SearchResult entries (empty on any failure)."""
    try:
        d = search(query, registry=registry, page_size=page_size, timeout=timeout)
        return d.get("results", []) or []
    except Exception:
        return []


def format_result(r: dict) -> str:
    name = r.get("displayName") or r.get("identifier") or "?"
    typ = r.get("type") or ""
    desc = (r.get("description") or "").strip()
    out = f"- **{name}** ({typ})"
    if desc:
        out += f" — {desc[:120]}"
    url = r.get("url")
    if url:
        out += f"  [{url}]"
    return out