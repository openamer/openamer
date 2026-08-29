#!/usr/bin/env python3
"""
MCP Echo Server — minimal test server for the MCP Bridge Plugin.

Implements the MCP stdio transport (JSON-RPC 2.0 over stdin/stdout):
  - initialize        → server info
  - tools/list        → single "echo" tool
  - tools/call        → echoes arguments back
  - notifications/*   → silently ignored (no response)

Usage:
    python test/mcp_echo_server.py

Designed to be spawned by the MCP bridge plugin as a subprocess.
"""

from __future__ import annotations

import json
import logging
import sys
from typing import Any

logging.basicConfig(
    level=logging.DEBUG,
    format="[echo-server] %(levelname)s %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("mcp-echo-server")

# ── Tool definitions ─────────────────────────────────────────────────────────

ECHO_TOOL = {
    "name": "echo",
    "description": "Echo back the arguments sent to this tool.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "message": {
                "type": "string",
                "description": "Message to echo back",
            },
            "uppercase": {
                "type": "boolean",
                "description": "If true, echo the message in uppercase",
            },
        },
        "required": ["message"],
    },
}

HELLO_TOOL = {
    "name": "hello",
    "description": "A simple hello world tool.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "Name to greet",
                "default": "World",
            },
        },
        "required": [],
    },
}

TOOLS = [ECHO_TOOL, HELLO_TOOL]


# ── JSON-RPC helpers ─────────────────────────────────────────────────────────


def make_error(id_val: int | None, code: int, message: str) -> str:
    """Build a JSON-RPC error response."""
    response = {
        "jsonrpc": "2.0",
        "id": id_val,
        "error": {"code": code, "message": message},
    }
    return json.dumps(response, ensure_ascii=False) + "\n"


def make_success(id_val: int, result: Any) -> str:
    """Build a JSON-RPC success response."""
    response = {
        "jsonrpc": "2.0",
        "id": id_val,
        "result": result,
    }
    return json.dumps(response, ensure_ascii=False) + "\n"


# ── Request handlers ─────────────────────────────────────────────────────────


def handle_initialize(params: dict | None) -> dict:
    """Handle the MCP initialize request."""
    logger.info("Received initialize request")
    return {
        "protocolVersion": "2025-03-26",
        "serverInfo": {
            "name": "mcp-echo-server",
            "version": "1.0.0",
        },
        "capabilities": {
            "tools": {},
        },
    }


def handle_list_tools() -> dict:
    """Handle the MCP tools/list request."""
    logger.info("Received tools/list request")
    return {"tools": TOOLS}


def handle_call_tool(params: dict | None) -> dict:
    """Handle the MCP tools/call request.

    Echoes back the arguments. Supports the 'echo' tool and the 'hello' tool.
    """
    if not isinstance(params, dict):
        return {"content": [{"type": "text", "text": "Error: params must be an object"}], "isError": True}

    tool_name = params.get("name", "")
    arguments = params.get("arguments", {}) or {}

    logger.info("Received tools/call: %s", tool_name)

    if tool_name == "echo":
        message = arguments.get("message", "")
        uppercase = arguments.get("uppercase", False)

        if uppercase:
            message = message.upper()

        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(
                        {
                            "echoed": message,
                            "received_args": arguments,
                            "server": "mcp-echo-server",
                        },
                        ensure_ascii=False,
                    ),
                }
            ],
        }

    elif tool_name == "hello":
        name = arguments.get("name", "World")
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(
                        {
                            "greeting": f"Hello, {name}!",
                            "server": "mcp-echo-server",
                        },
                        ensure_ascii=False,
                    ),
                }
            ],
        }

    else:
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(
                        {
                            "error": f"Unknown tool: {tool_name}",
                            "available_tools": [t["name"] for t in TOOLS],
                        },
                        ensure_ascii=False,
                    ),
                }
            ],
            "isError": True,
        }


# ── Main loop ────────────────────────────────────────────────────────────────


def main() -> None:
    """Read JSON-RPC requests from stdin and write responses to stdout."""
    logger.info("MCP Echo Server starting...")
    logger.info("Reading JSON-RPC requests from stdin")

    # Signal readiness by flushing stderr
    sys.stderr.flush()

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        try:
            request = json.loads(line)
        except json.JSONDecodeError as e:
            logger.warning("Invalid JSON received: %s", e)
            sys.stdout.write(make_error(None, -32700, f"Parse error: {e}"))
            sys.stdout.flush()
            continue

        req_id = request.get("id")
        method = request.get("method", "")
        params = request.get("params", {})
        jsonrpc_version = request.get("jsonrpc", "")

        if jsonrpc_version != "2.0":
            sys.stdout.write(
                make_error(req_id, -32600, "Invalid JSON-RPC version")
            )
            sys.stdout.flush()
            continue

        logger.debug("Request: %s (id=%s)", method, req_id)

        try:
            # Handle notifications (no id → no response expected)
            if req_id is None:
                if method == "notifications/initialized":
                    logger.info("Received initialized notification")
                    # No response for notifications
                else:
                    logger.debug("Ignoring notification: %s", method)
                continue

            # Method dispatch
            if method == "initialize":
                result = handle_initialize(params)
                sys.stdout.write(make_success(req_id, result))
            elif method == "tools/list":
                result = handle_list_tools()
                sys.stdout.write(make_success(req_id, result))
            elif method == "tools/call":
                result = handle_call_tool(params)
                sys.stdout.write(make_success(req_id, result))
            elif method == "tools/get":
                # Optional MCP method — some servers support it
                tool_name = params.get("name", "") if isinstance(params, dict) else ""
                tool = next(
                    (t for t in TOOLS if t["name"] == tool_name), None
                )
                if tool:
                    sys.stdout.write(make_success(req_id, {"tool": tool}))
                else:
                    sys.stdout.write(
                        make_error(req_id, -32601, f"Tool not found: {tool_name}")
                    )
            else:
                logger.warning("Unknown method: %s", method)
                sys.stdout.write(
                    make_error(req_id, -32601, f"Method not found: {method}")
                )

            sys.stdout.flush()

        except Exception as e:
            logger.error("Error handling request: %s", e)
            sys.stdout.write(
                make_error(req_id, -32603, f"Internal error: {e}")
            )
            sys.stdout.flush()

    logger.info("MCP Echo Server shutting down (stdin closed)")


if __name__ == "__main__":
    main()