# MCP Bridge Plugin Pattern — Case Study

Implements: Model Context Protocol client (JSON-RPC 2.0 over stdio) as an OpenAmer plugin.

## Architecture

- **MCPConnection** — manages one server subprocess (stdio), handles JSON-RPC lifecycle
- **MCPBridgeManager** — singleton, manages multiple servers, registered per ctx
- **onReady** — starts configured servers, discovers tools, registers via ctx.register_tool()
- **Handler closure** — `_make_handler(connection, tool_name)` captures connection per tool

## MCP Protocol Flow

1. **initialize** — handshake: client sends protocol version + capabilities
2. **notifications/initialized** — ack (no response expected)
3. **tools/list** — discover available tools + their JSON Schema input schemas
4. **tools/call** — invoke tool with arguments, returns content array

## Key Design Decisions

1. **queue.Queue for response matching** — each request gets a unique monotonic ID, responses matched by ID
2. **bufsize=1** — line-buffered stdout for clean JSON-per-line reading
3. **3 default retries** on tool call with linear backoff
4. **30s default timeout** per tool call (configurable)
5. **Tool name prefix** — `mcp_{server}_{tool}` to avoid namespace collisions
6. **Thread-safe** — threading.Lock for shared process write access
7. **Daemon threads** — reader thread auto-cleans on process death

## Test Infrastructure

- `test/mcp_echo_server.py` — standalone MCP-compatible echo server (2 tools: echo + hello)
- `test/test_bridge.py` — unit tests for MCPConnection (initialize, list_tools, call_tool)
- `test/test_integration.py` — end-to-end test: start echo server, connect, call tools, assert responses

## Verification

- `plugin-manager.py check mcp-bridge` → ✅ Enabled
- `python -c "compile(open('mcp-bridge/__init__.py','r').read(), 'x', 'exec')"` → OK
- Integration: start echo server, call `echo({"message": "hello"})` → `{"result": "hello"}`
- Echo server returns MCP-compliant `{"content": [{"type": "text", "text": "..."}]}`

## Files

- `desktop-plugins/mcp-bridge/__init__.py` — 674 lines, 23KB
- `desktop-plugins/mcp-bridge/plugin.yaml` — manifest
- `desktop-plugins/mcp-bridge/test/mcp_echo_server.py` — 8.7KB
- `desktop-plugins/mcp-bridge/test/test_bridge.py` — 6.2KB
- `desktop-plugins/mcp-bridge/test/test_integration.py` — 6KB