#!/usr/bin/env python3
"""
Integration test: MCP Bridge Plugin + Echo Server.

Simulates the OpenAmer plugin loader by:
1. Importing the plugin's __init__.py
2. Creating a mock PluginContext
3. Calling register(ctx)
4. Verifying tools are registered
5. Verifying tool calls work via the MCP connection

This demonstrates the full flow: plugin → MCP connection → tools/list → tool registration → tools/call.
"""

from __future__ import annotations

import json
import os
import sys
import time

# Add repo to path so imports work
REPO_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO_DIR))  # for plugin_utils

echo_server_path = os.path.join(os.path.dirname(__file__), "mcp_echo_server.py")
echo_server_abs = os.path.abspath(echo_server_path)

# ── Remove old __pycache__ so we get a clean import ──────────────────────
plugin_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # parent of test/
pycache = os.path.join(plugin_dir, "__pycache__")
if os.path.exists(pycache):
    import shutil
    shutil.rmtree(pycache, ignore_errors=True)

# Ensure we can import the module by adding its parent to path
sys.path.insert(0, os.path.dirname(plugin_dir))  # desktop-plugins/

# ── Mock PluginContext ─────────────────────────────────────────────────────

class MockPluginContext:
    """Minimal mock of the OpenAmer PluginContext."""

    def __init__(self):
        self.tools = {}
        self.logs = []
        self.ready_callbacks = []
        self._config = {}

    def set_config(self, key, value):
        self._config[key] = value

    def get_config(self, key, default=None):
        keys = key.split(".")
        val = self._config
        for k in keys:
            if isinstance(val, dict):
                val = val.get(k, None) if val is not None else None
            else:
                return default
        return val if val is not None else default

    def register_tool(
        self, name, toolset, schema, handler, check_fn=None,
        requires_env=None, is_async=False, description="", emoji="", override=False
    ):
        self.tools[name] = {
            "toolset": toolset,
            "schema": schema,
            "handler": handler,
            "description": description,
        }
        print(f"[MOCK] ✅ Tool registered: {name} ({toolset})")

    def log_info(self, msg):
        print(f"[MOCK] INFO: {msg}")
        self.logs.append(("INFO", msg))

    def log_debug(self, msg):
        print(f"[MOCK] DEBUG: {msg}")
        self.logs.append(("DEBUG", msg))

    def log_error(self, msg):
        print(f"[MOCK] ERROR: {msg}")
        self.logs.append(("ERROR", msg))

    # Hook decorators (simplified for testing)
    def on_ready(self, fn=None):
        if fn is not None:
            self.ready_callbacks.append(fn)
            return fn
        def wrapper(f):
            self.ready_callbacks.append(f)
            return f
        return wrapper


# ── Integration Test ───────────────────────────────────────────────────────

print("═" * 60)
print("  MCP Bridge Plugin — Integration Test")
print("═" * 60)
print()

# 1. Create mock context
print("─── Step 1: Create mock context with server config ───")
ctx = MockPluginContext()
ctx.set_config("servers", [
    {
        "name": "echo-test",
        "command": sys.executable,
        "args": [echo_server_abs],
        "timeout": 10,
    }
])
print("   ✅ Context with echo-test server config")
print()

# 2. Import and call register()
print("─── Step 2: Load plugin and call register(ctx) ───")
# Use exec to avoid import path issues with the test subdirectory
with open(os.path.join(plugin_dir, "__init__.py"), "r", encoding="utf-8") as f:
    plugin_code = f.read()
# Create a module-like namespace with access to __init__.py's globals
plugin_ns = {}
exec(compile(plugin_code, os.path.join(plugin_dir, "__init__.py"), "exec"), plugin_ns)
plugin_ns["register"](ctx)
print("   ✅ register() called")
print()

# 3. Wait for background thread to connect and register tools
print("─── Step 3: Wait for MCP connection + tool discovery ───")
time.sleep(3)  # Give background thread time

print(f"   Registered tools: {list(ctx.tools.keys())}")
assert "mcp_echo_test_echo" in ctx.tools, "Expected echo tool to be registered"
assert "mcp_echo_test_hello" in ctx.tools, "Expected hello tool to be registered"
print("   ✅ Both tools discovered and registered")
print()

# 4. Call the echo tool via handler
print("─── Step 4: Call echo tool handler ───")
handler = ctx.tools["mcp_echo_test_echo"]["handler"]
result = handler({"message": "Integration Test!", "uppercase": True})
print(f"   Result: {json.dumps(result, indent=4)}")

if "result" in result:
    parsed = json.loads(result["result"])
    assert parsed["echoed"] == "INTEGRATION TEST!"
    assert parsed["server"] == "mcp-echo-server"
    print("   ✅ Echo tool responded correctly")
else:
    print(f"   ❌ No result in response: {result}")
    sys.exit(1)

print()

# 5. Call the hello tool via handler
print("─── Step 5: Call hello tool handler ───")
handler = ctx.tools["mcp_echo_test_hello"]["handler"]
result = handler({"name": "MCP Bridge"})
print(f"   Result: {json.dumps(result, indent=4)}")

if "result" in result:
    parsed = json.loads(result["result"])
    assert "Hello, MCP Bridge!" in parsed["greeting"]
    print("   ✅ Hello tool responded correctly")
else:
    print(f"   ❌ No result in response: {result}")
    sys.exit(1)

print()

# 6. Fire onReady (simulate agent startup)
print("─── Step 6: Fire onReady callbacks ───")
for cb in ctx.ready_callbacks:
    cb()
print("   ✅ onReady fired")

print()
print("═" * 60)
print("  ✅ ALL INTEGRATION TESTS PASSED")
print("═" * 60)