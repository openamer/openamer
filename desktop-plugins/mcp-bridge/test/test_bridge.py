#!/usr/bin/env python3
"""Test the MCP bridge connection programmatically."""

from __future__ import annotations

import sys
import os
import json
import time

# Add the repo to path so we can import the plugin
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
os.chdir(os.path.join(os.path.dirname(__file__), "..", ".."))

# Extract the MCPConnection class and test it standalone
from plugins.plugin_utils import lazy_singleton, SingletonSlot

# Create a minimal mock context
class MockContext:
    def __init__(self):
        self._logs = []
    def log_info(self, msg):
        self._logs.append(f"INFO: {msg}")
        print(f"[MOCK] INFO: {msg}")
    def log_debug(self, msg):
        self._logs.append(f"DEBUG: {msg}")
        print(f"[MOCK] DEBUG: {msg}")
    def log_error(self, msg):
        self._logs.append(f"ERROR: {msg}")
        print(f"[MOCK] ERROR: {msg}")
    def register_tool(self, **kwargs):
        self._last_tool = kwargs
        print(f"[MOCK] register_tool: {kwargs['name']} (toolset={kwargs['toolset']})")
    def get_config(self, key, default=None):
        return default

# Now import our connection module — need to handle the fact that it
# lives in desktop-plugins/
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# We can't easily import it because it uses decorator-based hooks.
# Let's just test the raw JSON-RPC logic against the echo server.

import subprocess
import threading
import queue

# ── Start echo server ──────────────────────────────────────────────────────

echo_server_path = os.path.join(
    os.path.dirname(__file__), "test", "mcp_echo_server.py"
)
proc = subprocess.Popen(
    [sys.executable, echo_server_path],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    bufsize=1,
)

print(f"Started echo server (pid={proc.pid})")
print()

# ── JSON-RPC helpers ───────────────────────────────────────────────────────

_request_id = [0]
def next_id():
    _request_id[0] += 1
    return _request_id[0]

def send_request(method, params=None):
    req_id = next_id()
    request = {
        "jsonrpc": "2.0",
        "id": req_id,
        "method": method,
        "params": params or {},
    }
    line = json.dumps(request) + "\n"
    print(f">> {method} (id={req_id})")
    proc.stdin.write(line)
    proc.stdin.flush()
    return req_id

def read_response(timeout=10):
    """Read a JSON-RPC response line from stdout."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        line = proc.stdout.readline()
        if not line:
            raise TimeoutError("No response from server")
        line = line.strip()
        if not line:
            continue
        try:
            return json.loads(line)
        except json.JSONDecodeError:
            continue
    raise TimeoutError("Timeout waiting for response")

# ── Test initialize ────────────────────────────────────────────────────────

print("═══ Test: initialize ═══")
send_request("initialize", {
    "protocolVersion": "2025-03-26",
    "capabilities": {},
    "clientInfo": {"name": "test-bridge", "version": "1.0.0"}
})
resp = read_response()
print(f"   << {json.dumps(resp, indent=2)}")
assert "result" in resp, "Expected result in initialize response"
assert resp["result"].get("serverInfo", {}).get("name") == "mcp-echo-server"
print("   ✅ initialize OK")

# Send initialized notification (no response expected)
notif = json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n"
proc.stdin.write(notif)
proc.stdin.flush()
print("   ✅ notification sent")

print()

# ── Test tools/list ────────────────────────────────────────────────────────

print("═══ Test: tools/list ═══")
send_request("tools/list")
resp = read_response()
assert "result" in resp
tools = resp["result"].get("tools", [])
print(f"   Found {len(tools)} tool(s):")
for t in tools:
    print(f"     - {t['name']}: {t.get('description', '')[:60]}...")
assert len(tools) == 2
assert tools[0]["name"] == "echo"
assert tools[1]["name"] == "hello"
print("   ✅ tools/list OK")

print()

# ── Test tools/call (echo) ─────────────────────────────────────────────────

print("═══ Test: tools/call (echo) ═══")
send_request("tools/call", {
    "name": "echo",
    "arguments": {"message": "Hello MCP Bridge!", "uppercase": True}
})
resp = read_response()
result = resp.get("result", {})
content = result.get("content", [])
text = content[0].get("text", "") if content else ""
print(f"   Response: {text}")
assert "HELLO MCP BRIDGE!" in text
assert "mcp-echo-server" in text
print("   ✅ tools/call (echo) OK")

print()

# ── Test tools/call (hello) ────────────────────────────────────────────────

print("═══ Test: tools/call (hello) ═══")
send_request("tools/call", {
    "name": "hello",
    "arguments": {"name": "MCP Bridge"}
})
resp = read_response()
result = resp.get("result", {})
content = result.get("content", [])
text = content[0].get("text", "") if content else ""
print(f"   Response: {text}")
assert "Hello, MCP Bridge!" in text
print("   ✅ tools/call (hello) OK")

print()

# ── Cleanup ────────────────────────────────────────────────────────────────

print("═══ Shutting down ═══")
proc.terminate()
proc.wait(timeout=5)
print("   ✅ Server terminated")

print()
print("═══ ALL TESTS PASSED ═══")