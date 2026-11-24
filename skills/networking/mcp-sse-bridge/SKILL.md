---
name: mcp-sse-bridge
description: Use when building or running the MCP SSE bridge.
trigger: MCP bridge, SSE transport, Model Context Protocol
category: networking
version: 1.0.0
---

# MCP SSE Bridge

Exposes OpenAmer's tools via MCP SSE protocol on port 8090. Any MCP client (Claude Desktop, Cursor, VS Code AI, etc.) connects via SSE and gets tool schemas + execution.

## Start

```bash
cd /c/Users/damir/AppData/Local/openamer-laptop
python scripts/mcp_sse_bridge.py --port 8090
```

## MCP Client Config

```json
{"mcpServers": {"openamer": {"url": "http://localhost:8090/sse"}}}
```

## Endpoints

| Path | Method | Description |
|---|---|---|
| `/health` | GET | Status + session count |
| `/sse` | GET | SSE stream (MCP endpoint negotiation) |
| `/message/{session}` | POST | MCP JSON-RPC dispatch |

## Verified RPC methods

- `initialize` — Protocol version 2025-03-26
- `tools/list` — Returns 6 tool schemas
- `tools/call` — Forwards to Mini-OpenAmer via `/v1/chat/completions`

## Files

- `scripts/mcp_sse_bridge.py` — HTTP server (Python stdlib)
- Uses only `http.server`, `urllib.request`, `json`, `threading`, `queue`

## Pitfalls

- Tool calls can be slow (up to 60s for 2B model reasoning)
- SSE handler uses threading (HTTPServer is synchronous)
- Kill via `process(action='kill')`