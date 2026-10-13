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

# Curated-catalog name lookup, built lazily on first use (see _curated_index).
_curated_cache = None


def _curated_index():
    """Map community github ``owner/repo`` tails to OpenAmer-approved catalog
    names, so a community search hit can be routed to the safe install path.

    The curated catalog (``openamer_cli.mcp_catalog``) ships supply-chain-pinned
    manifests; only those are installable. Community hits that match one are
    flagged ``curated`` and can be installed deterministically; hits without a
    match still need a manifest PR before OpenAmer will install them.
    """
    global _curated_cache
    if _curated_cache is not None:
        return _curated_cache
    tail_to_name = {}
    names = set()
    try:
        # Absolute import on purpose (distinct module from this one):
        from openamer_cli import mcp_catalog as curated
        for e in curated.list_catalog():
            names.add(e.name)
            m = re.search(r"github\.com/([^/]+/[^/?#]+)", e.source or "")
            if m:
                tail_to_name[m.group(1).rstrip("/").casefold()] = e.name
    except Exception:
        pass  # curated catalog unavailable → every community hit is "not curated"
    _curated_cache = (tail_to_name, names)
    return _curated_cache


def _annotate(entries):
    """Attach ``curated`` (approvable install target) + ``installed`` flags."""
    tail_to_name, _names = _curated_index()
    out = []
    for e in entries:
        curated_name = None
        if e.get("url"):
            m = re.search(r"github\.com/([^/]+/[^/?#]+)", e["url"])
            if m:
                curated_name = tail_to_name.get(m.group(1).rstrip("/").casefold())
        out.append({
            **e,
            "curated": curated_name,
            "installed": _is_installed(curated_name),
        })
    return out


def _is_installed(curated_name):
    if not curated_name:
        return False
    try:
        from openamer_cli import mcp_catalog as curated
        return curated.is_installed(curated_name)
    except Exception:
        return False


def _tokenize_clauses(query):
    """Split a query into AND-ed clauses; ``|`` ORs alternatives inside a
    clause; ``"double quoted"`` turns a multi-word run into one exact
    substring. Returns a list of lists of substring alternatives (casefolded).
    Opamer matches an entry when every clause has at least one alternative that
    is a substring of the entry text.
    """
    if not query:
        return []
    clauses = []
    for tok in re.findall(r'"[^"]+"|\S+', query):
        if tok.startswith('"') and tok.endswith('"'):
            alt = [tok[1:-1].casefold()]
        else:
            alt = [t.casefold() for t in tok.split("|") if t]
        if alt:
            clauses.append(alt)
    return clauses


def _entry_text(e) -> str:
    return (e.get("name", "") + " " + e.get("description", "")).casefold()


def _matches(e, clauses) -> bool:
    text = _entry_text(e)
    return all(any(t in text for t in alt) for alt in clauses)


def _matches_slice(entries, query: str, limit: int = 10) -> list:
    """Filter an already-parsed entry list by ``query`` without fetching.

    Hermetic counterpart to :func:`search` (which fetches the live catalog).
    Lets callers/tests run the same clause logic over a list of entries.
    """
    clauses = _tokenize_clauses(query)
    if not clauses:
        return entries[:limit]
    hits = [e for e in entries if _matches(e, clauses)]
    return hits[:limit]


def _fetch(raw: str = RAW, timeout: float = 25.0) -> str:
    global CACHE
    if CACHE is not None:
        return CACHE
    req = urllib.request.Request(raw, headers={"User-Agent": "openamer-mcp-catalog/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        CACHE = r.read().decode("utf-8", "replace")
    return CACHE


_ROW_RE = re.compile(
    r"- \[([^\]]+)\]\((https://github\.com/[^)]+)\) \[!\[[^\]]*\]\([^)]*\)\]\([^)]*\)(.*)",
    re.M)


def _clean_markdown(s: str) -> str:
    """Flatten markdown noise in a description to plain searchable text.

    Inline links become their label, backticks are stripped, and runs of
    whitespace collapse to a single space (the raw file uses one description
    per line, so there is no intra-cell newline to preserve).
    """
    s = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", s)  # [label](url) -> label
    s = s.replace("`", "")
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def _parse(text: str) -> list[dict]:
    out = []
    for m in _ROW_RE.finditer(text):
        name, url = m.group(1), m.group(2)
        if not name or not url:
            continue
        rest = m.group(3) or ""
        # Platform hints (emoji) + trailing meta end at the first dash; the
        # human-readable description follows it. Handle both hyphen and dash.
        parts = re.split(r"\s+[-–—]\s+", rest, maxsplit=1)
        desc = parts[1] if len(parts) > 1 else parts[0]
        desc = _clean_markdown(desc)
        out.append({"name": name, "url": url, "description": desc})
    return out


def search(query: str, *, raw: str = RAW, limit: int = 10, timeout: float = 25.0) -> list:
    """Return MCP-server entries matching ``query``.

    Query syntax: space-separated bare terms are AND-ed, ``|`` ORs
    alternatives inside one term, and ``"double quotes"`` group words into an
    exact substring (e.g. ``github api`` or ``postgres|mysql`` or
    ``"web scraping"``). Each hit is annotated with ``curated`` (the
    OpenAmer-approved catalog name this server maps to, if any) and
    ``installed`` (whether that approved entry is currently installed), so a
    caller can offer a safe install path instead of pinning an arbitrary repo.
    """
    clauses = _tokenize_clauses(query)
    try:
        text = _fetch(raw, timeout)
    except Exception:
        return []
    entries = _parse(text)
    if not clauses:
        return _annotate(entries[:limit])
    hits = [e for e in entries if _matches(e, clauses)]
    return _annotate(hits[:limit])


def format_entry(e: dict) -> str:
    gh = ""
    if "github" in e.get("url", "").lower():
        gh = f"  [{e['url']}]"
    badges = []
    curated = e.get("curated")
    if curated:
        badges.append(f"[approved: openamer mcp install {curated}]")
    if e.get("installed"):
        badges.append("[installed]")
    suffix = ("  " + " ".join(badges)) if badges else ""
    return f"- **{e['name']}** — {e['description'][:110]}{gh}{suffix}"