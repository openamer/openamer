"""Probe every configured MCP server and classify WHY it fails.

Run with the install's own venv (the one that has `mcp` + `httpx`):

    cd "$OPENAMER_HOME/openamer-agent"
    venv/Scripts/python.exe \
        "$OPENAMER_HOME/skills/mcp/mcp-server-triage/scripts/probe_mcp_servers.py"

Levels, cheapest first:
  1. token file present + live?      -> credential class
  2. raw MCP SDK handshake           -> transport class
  3. real OpenAmer MCPServerTask     -> OpenAmer-internal class

A level that PASSES proves that level is fine. Report the FIRST level that
fails; do not report "the network is down" from level 3 alone.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from pathlib import Path

HOME = Path(os.environ.get("OPENAMER_HOME") or Path.home() / ".openamer")
REPO = HOME / "openamer-agent"

if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

# Servers we know how to reach over streamable HTTP. Extend as needed.
HTTP_SERVERS = {
    "linear": "https://mcp.linear.app/mcp",
    "notion": "https://mcp.notion.com/mcp",
    "stripe": "https://mcp.stripe.com",
    "sentry": "https://mcp.sentry.dev/mcp",
    "supabase": "https://mcp.supabase.com/mcp",
    "vercel": "https://mcp.vercel.com",
}

CONNECT_TIMEOUT = float(os.environ.get("MCP_PROBE_TIMEOUT", "75"))


def check_token(name: str) -> tuple[str, float | None]:
    """Return (verdict, seconds_until_expiry) for the stored OAuth token."""
    path = HOME / "mcp-tokens" / f"{name}.json"
    if not path.is_file():
        return "NO TOKEN FILE", None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        return f"UNREADABLE TOKEN ({exc})", None
    expires_at = data.get("expires_at")
    if not isinstance(expires_at, (int, float)):
        return "TOKEN WITHOUT expires_at", None
    remaining = expires_at - time.time()
    if remaining <= 0:
        return "TOKEN EXPIRED", remaining
    return "TOKEN OK", remaining


async def probe_raw_sdk(name: str, url: str) -> str:
    """Level 2: the plain MCP SDK with the stored bearer token."""
    try:
        import httpx
        from mcp import ClientSession
        from mcp.client.streamable_http import streamable_http_client
    except ImportError as exc:
        return f"SKIP (SDK missing: {exc})"

    token_path = HOME / "mcp-tokens" / f"{name}.json"
    if not token_path.is_file():
        return "SKIP (no token)"

    token = json.loads(token_path.read_text(encoding="utf-8")).get("access_token", "")
    started = time.time()
    try:
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=httpx.Timeout(CONNECT_TIMEOUT, read=300.0),
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/json, text/event-stream",
            },
        ) as client:
            async with streamable_http_client(url, http_client=client) as (r, w, _sid):
                async with ClientSession(r, w) as session:
                    await asyncio.wait_for(session.initialize(), timeout=CONNECT_TIMEOUT)
                    tools = await asyncio.wait_for(session.list_tools(), timeout=CONNECT_TIMEOUT)
        return f"OK in {time.time() - started:.2f}s tools={len(tools.tools)}"
    except Exception as exc:  # noqa: BLE001
        return f"FAIL after {time.time() - started:.2f}s {type(exc).__name__}: {exc}"


async def probe_openamer_path(name: str) -> str:
    """Level 3: OpenAmer's own MCPServerTask, i.e. the real code path."""
    try:
        from tools import mcp_tool
        from tools.mcp_tool import MCPServerTask
    except ImportError as exc:
        return f"SKIP (cannot import tools.mcp_tool: {exc})"

    config = (mcp_tool._load_mcp_config() or {}).get(name)
    if not config:
        return "SKIP (not in config.yaml)"

    started = time.time()
    server = MCPServerTask(name)
    try:
        await asyncio.wait_for(server.start(config), timeout=CONNECT_TIMEOUT)
        return f"READY in {time.time() - started:.2f}s tools={len(server._tools)}"
    except Exception as exc:  # noqa: BLE001
        return f"FAIL after {time.time() - started:.2f}s {type(exc).__name__}: {exc}"


async def main() -> int:
    names = list(HTTP_SERVERS)
    print(f"OPENAMER_HOME = {HOME}")
    print(f"mcp SDK      = ", end="")
    try:
        import importlib.metadata as md

        print(md.version("mcp"))
    except Exception:  # noqa: BLE001
        print("unknown")
    print()

    for name in names:
        verdict, remaining = check_token(name)
        expiry = "n/a" if remaining is None else f"{remaining:.0f}s"
        print(f"=== {name} ===")
        print(f"  level 1 token      : {verdict} (expires in {expiry})")
        print(f"  level 2 raw SDK    : {await probe_raw_sdk(name, HTTP_SERVERS[name])}")
        print(f"  level 3 openamer   : {await probe_openamer_path(name)}")
        print()

    print("Interpretation:")
    print("  level 1 fails            -> credential class: `openamer mcp login <name>` (needs a TTY)")
    print("  level 1 ok, level 2 fails -> transport class: server rejected/late handshake")
    print("  level 2 ok, level 3 fails -> fault is inside OpenAmer's MCP connection code")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
