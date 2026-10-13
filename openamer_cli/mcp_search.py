"""openamer mcp search-tools — find a tool across all installed MCP servers.

Implements the Layer-1 catalog of the 2026 MCP client best-practice pattern
(progressive discovery): when a host accumulates tools from hundreds of
servers, naive "dump everything into context" tool management breaks down.
Instead, expose a light search that returns just the matching tool names +
one-line descriptions, grouped by their source server, so the model can pick a
candidate and inspect only that one.

This is the *tool* level over OpenAmer's *installed* servers — the sibling of
``openamer a2a mcp-catalog`` (which finds *servers* in the broad community
catalog). Query syntax matches the catalog: space = AND, ``a|b`` = OR,
``"exact phrase"``.

Usage:
    openamer mcp search-tools "update salesforce record"
    openamer mcp search-tools '"semantic search"'
    openamer mcp search-tools postgres --limit 5 --server n8n
"""
from __future__ import annotations

from openamer_cli.a2a import mcp_catalog as _cat  # clause helpers (no fetch side-effect at import)

DEFAULT_SERVER_TIMEOUT = 30.0


def _installed_servers() -> dict:
    """Return the configured ``mcp_servers`` block (name -> config)."""
    from openamer_cli import mcp_catalog as curated
    return curated.installed_servers()


def _probe(name: str, cfg: dict) -> list[tuple]:
    """Connect to one server and return [(tool_name, description)]. Raises on failure."""
    from openamer_cli.mcp_config import _probe_single_server
    timeout = cfg.get("connect_timeout", DEFAULT_SERVER_TIMEOUT)
    try:
        timeout = max(1.0, float(timeout))
    except (TypeError, ValueError):
        timeout = DEFAULT_SERVER_TIMEOUT
    return _probe_single_server(name, cfg, connect_timeout=timeout)


def _is_enabled(cfg: dict) -> bool:
    enabled = cfg.get("enabled", True)
    if isinstance(enabled, str):
        return enabled.lower() in {"true", "1", "yes"}
    return bool(enabled)


def search_tools(
    query: str = "",
    *,
    server: str | None = None,
    limit: int = 10,
    connect_timeout: float = DEFAULT_SERVER_TIMEOUT,
    on_probe_error: str = "skip",
) -> dict:
    """Search tool names+descriptions across installed MCP servers.

    Returns {"server": str|None(global), "matches": [ {server, name, description} ]}.
    Probing is per-server; a failing server is skipped (skip) or surfaced as a
    note in ``"probe_errors"``, never fatal.
    """
    servers = _installed_servers()
    if not servers:
        return {"matches": [], "probe_errors": [], "total_servers": 0}

    clause_helpers = (_cat._tokenize_clauses, _cat._matches)

    def _match_tool(name: str, desc: str) -> bool:
        tokens, matcher = clause_helpers
        clauses = tokens(query)
        if not clauses:
            return True
        return matcher({"name": name, "description": desc}, clauses)

    matches: list[dict] = []
    probe_errors: list[str] = []
    total = 0
    for name, cfg in sorted(servers.items()):
        if server and name != server:
            continue
        if not _is_enabled(cfg):
            continue
        total += 1
        try:
            tools = _probe(name, cfg)
        except Exception as exc:
            if on_probe_error == "fail":
                raise
            probe_errors.append(f"{name}: {exc}")
            continue
        for tname, desc in tools:
            if _match_tool(tname, desc):
                matches.append(
                    {"server": name, "name": tname, "description": desc}
                )
    matches.sort(key=lambda m: (m["server"], m["name"]))
    return {
        "matches": matches[:limit] if limit else matches,
        "probe_errors": probe_errors,
        "total_servers": total,
    }


def format_match(m: dict) -> str:
    desc = m.get("description", "")
    if len(desc) > 90:
        desc = desc[:87] + "..."
    return f"- **{m['server']}::{m['name']}** — {desc}"


def cmd_mcp_search_tools(args) -> int:
    """`openamer mcp search-tools` — print matching tools grouped by server."""
    query = getattr(args, "query", "") or ""
    limit = int(getattr(args, "limit", 10))
    server = (getattr(args, "server", "") or "").strip() or None
    result = search_tools(query, server=server, limit=limit)

    if result["total_servers"] == 0:
        print("  No enabled MCP servers configured. "
              "Install one with `openamer mcp add <name> ...` or `openamer mcp install <name>`.")
        return 1

    print(f"[mcp search-tools] '{query or ''}' across "
          f"{result['total_servers']} server(s) — {len(result['matches'])} tool match(es)")

    if not result["matches"]:
        if query:
            print("  (no tools match — try fewer or broader terms)")
        else:
            print("  (servers reachable but reported no tools)")
        return 1

    # Group by server so the model can reason about related capabilities
    # (2026 best-practice: "Group tools by server").
    current = None
    for m in result["matches"]:
        if m["server"] != current:
            print(f"\n  {m['server']}:")
            current = m["server"]
        print("  " + format_match(m))
    print()

    if result["probe_errors"]:
        print("  ⚠ servers that could not be probed:")
        for err in result["probe_errors"][:5]:
            print(f"    {err}")
    return 0