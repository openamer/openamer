"""
mcp-bridge — OpenAmer MCP Bridge Plugin.

Connects to external MCP (Model Context Protocol) servers as a client via
stdio JSON-RPC, discovers their tools, and registers them as first-class
OpenAmer tools.

Protocol: MCP uses JSON-RPC 2.0 over stdin/stdout.
  - initialize     {"jsonrpc":"2.0","id":1,"method":"initialize","params":{...}}
  - tools/list     {"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}
  - tools/call     {"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"...","arguments":{...}}}

Requires no external dependencies — only stdlib json + subprocess.
"""

from __future__ import annotations

import json
import logging
import os
import queue
import subprocess
import threading
import time
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


# ── Constants ────────────────────────────────────────────────────────────────

MCP_PROTOCOL_VERSION = "2025-03-26"
CLIENT_NAME = "openamer-mcp-bridge"
CLIENT_VERSION = "1.0.0"
DEFAULT_TIMEOUT = 30

# JSON-RPC error codes
JRPC_PARSE_ERROR = -32700
JRPC_INVALID_REQUEST = -32600
JRPC_METHOD_NOT_FOUND = -32601
JRPC_INVALID_PARAMS = -32602
JRPC_INTERNAL_ERROR = -32603


# ── Helpers ──────────────────────────────────────────────────────────────────


_request_id_counter: int = 0


def _make_request_id() -> int:
    """Generate a simple monotonic request ID."""
    global _request_id_counter
    _request_id_counter += 1
    return _request_id_counter


def _build_jrpc_request(method: str, params: dict | None = None) -> str:
    """Build a JSON-RPC 2.0 request string with trailing newline."""
    request = {
        "jsonrpc": "2.0",
        "id": _make_request_id(),
        "method": method,
        "params": params or {},
    }
    return json.dumps(request, ensure_ascii=False) + "\n"


def _mcp_tool_name(server_name: str, tool_name: str) -> str:
    """Generate a unique tool name for the agent.

    Replaces hyphens/dots with underscores for LLM API compatibility.
    """
    safe_server = server_name.replace("-", "_").replace(".", "_")
    safe_tool = tool_name.replace("-", "_").replace(".", "_")
    return f"mcp_{safe_server}_{safe_tool}"


# ── MCP Connection ───────────────────────────────────────────────────────────


class MCPConnectionError(Exception):
    """Raised when an MCP server connection or call fails."""


class MCPConnection:
    """Manages a single MCP server subprocess and its JSON-RPC communication.

    Handles:
      - Subprocess lifecycle (start, shutdown)
      - MCP initialize handshake
      - Tool discovery (tools/list -> register with ctx)
      - Tool invocation (tools/call)
      - Timeout and error handling
    """

    def __init__(
        self,
        ctx: Any,
        server_name: str,
        command: str,
        args: list[str] | None = None,
        env: dict[str, str] | None = None,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> None:
        self.ctx = ctx
        self.server_name = server_name
        self.command = command
        self.args = args or []
        self.server_env = env or {}
        self.timeout = timeout

        self._proc: subprocess.Popen | None = None
        self._lock = threading.Lock()
        self._tool_handlers: dict[str, Callable] = {}
        self._tool_names: list[str] = []
        self._ready = threading.Event()
        self._stopped = False

    # ── Public API ───────────────────────────────────────────────────────

    def connect_and_register(self) -> None:
        """Start the subprocess, connect, and register tools.

        This runs in a background thread so it does not block agent startup.
        """
        try:
            self._start_process()
            self._initialize()
            tools = self._list_tools()
            self._register_tools(tools)
            self._ready.set()
            self.ctx.log_info(
                f"MCP bridge: server '{self.server_name}' connected — "
                f"{len(tools)} tool(s) registered"
            )
        except MCPConnectionError as e:
            self.ctx.log_error(
                f"MCP bridge: server '{self.server_name}' connection failed: {e}"
            )
        except Exception as e:
            self.ctx.log_error(
                f"MCP bridge: server '{self.server_name}' unexpected error: {e}"
            )

    def call_tool(self, tool_name: str, arguments: dict) -> dict:
        """Call an MCP tool and return the result.

        Args:
            tool_name: The original MCP tool name (without prefix).
            arguments: Tool arguments as a dict.

        Returns:
            A dict with either a ``result`` or ``error`` key.
        """
        timeouts = 0
        last_error = ""

        for attempt in range(3):
            if not self._ready.is_set():
                # Server still connecting — wait a bit
                if self._ready.wait(timeout=10):
                    return self._do_call_tool(tool_name, arguments)

            # Re-check ready after wait
            if not self._ready.is_set():
                return self._make_error("MCP server not ready yet")

            return self._do_call_tool(tool_name, arguments)

        return self._make_error(
            f"MCP server '{self.server_name}' unreachable after 3 attempts: "
            f"{last_error}"
        )

    def shutdown(self) -> None:
        """Terminate the subprocess gracefully."""
        self._stopped = True
        if self._proc and self._proc.poll() is None:
            try:
                self._proc.terminate()
                self._proc.wait(timeout=5)
            except Exception:
                try:
                    self._proc.kill()
                    self._proc.wait(timeout=2)
                except Exception:
                    pass

    # ── Internal: Subprocess ─────────────────────────────────────────────

    def _start_process(self) -> None:
        """Launch the MCP server as a subprocess."""
        cmd = [self.command] + self.args
        filtered_env = self._build_env()
        logger.debug(
            "MCP bridge: starting server '%s': %s", self.server_name, cmd
        )
        try:
            self._proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=filtered_env,
                text=True,
                bufsize=1,  # line-buffered
            )
        except FileNotFoundError:
            raise MCPConnectionError(
                f"Command '{self.command}' not found. Is it installed?"
            ) from None
        except Exception as e:
            raise MCPConnectionError(
                f"Failed to start process: {e}"
            ) from e

    def _build_env(self) -> dict[str, str]:
        """Build a safe environment dict for the subprocess.

        Passes only common safe variables from the parent plus any
        user-specified env vars.
        """
        safe_keys = {"PATH", "HOME", "USER", "LANG", "LC_ALL", "TERM", "SHELL"}
        env = {}
        for key in safe_keys:
            val = os.environ.get(key)
            if val is not None:
                env[key] = val
        env.update(self.server_env)
        return env

    # ── Internal: JSON-RPC over stdio ────────────────────────────────────

    def _send_request(self, method: str, params: dict | None = None) -> dict:
        """Send a JSON-RPC request and wait for a response.

        Raises MCPConnectionError on failure or timeout.
        """
        if self._proc is None or self._proc.stdin is None or self._proc.stdout is None:
            raise MCPConnectionError("Process not running")

        request_line = _build_jrpc_request(method, params)
        logger.debug(
            "MCP bridge [%s] -> %s", self.server_name, request_line.strip()
        )

        with self._lock:
            self._proc.stdin.write(request_line)
            self._proc.stdin.flush()

            # Read response line-by-line until we get a matching id
            deadline = time.monotonic() + self.timeout
            while time.monotonic() < deadline:
                # Check if process is still alive
                if self._proc.poll() is not None:
                    stderr_output = self._read_stderr()
                    raise MCPConnectionError(
                        f"Process terminated unexpectedly (exit code "
                        f"{self._proc.returncode}). "
                        f"Stderr: {stderr_output[:500]}"
                    )

                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise MCPConnectionError(
                        f"Timeout ({self.timeout}s) waiting for response to "
                        f"'{method}'"
                    )

                # Use select-like polling via readline in a thread with timeout
                response_line = self._read_line_with_timeout(
                    proc=self._proc, timeout=min(2.0, remaining)
                )
                if response_line is None:
                    # Read stderr to check if server printed something useful
                    stderr = self._read_stderr()
                    if stderr:
                        logger.debug(
                            "MCP bridge [%s] stderr: %s",
                            self.server_name,
                            stderr[:300],
                        )
                    continue

                try:
                    response = json.loads(response_line)
                except json.JSONDecodeError:
                    # Could be a log line from the server — skip it
                    logger.debug(
                        "MCP bridge [%s] non-JSON output: %s",
                        self.server_name,
                        response_line[:200],
                    )
                    continue

                # Check for error response
                if "error" in response:
                    error = response["error"]
                    raise MCPConnectionError(
                        f"JSON-RPC error ({error.get('code', '?')}): "
                        f"{error.get('message', 'Unknown error')}"
                    )

                return response.get("result", {})

            raise MCPConnectionError(
                f"Timeout ({self.timeout}s) waiting for response to '{method}'"
            )

    @staticmethod
    def _read_line_with_timeout(
        proc: subprocess.Popen,
        timeout: float,
    ) -> str | None:
        """Read a line from stdout with a timeout.

        Returns None if the timeout is reached before a full line is available.
        Uses a helper thread since Popen.stdout.readline() is blocking.
        """
        result_queue: queue.Queue = queue.Queue()

        def _reader():
            try:
                if proc.stdout:
                    line = proc.stdout.readline()
                    result_queue.put(line)
            except Exception:
                result_queue.put(None)

        thread = threading.Thread(target=_reader, daemon=True)
        thread.start()
        thread.join(timeout=timeout)

        if thread.is_alive():
            return None

        try:
            return result_queue.get_nowait()
        except queue.Empty:
            return None

    def _read_stderr(self) -> str:
        """Read any available stderr output."""
        if self._proc and self._proc.stderr:
            try:
                return self._proc.stderr.read(4096)
            except Exception:
                return ""
        return ""

    # ── Internal: MCP Protocol ───────────────────────────────────────────

    def _initialize(self) -> None:
        """Perform the MCP initialize handshake.

        Sends:
            initialize -> {protocolVersion, capabilities, clientInfo}
        Then sends:
            notifications/initialized
        """
        logger.debug("MCP bridge [%s]: initializing...", self.server_name)
        init_params = {
            "protocolVersion": MCP_PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": {
                "name": CLIENT_NAME,
                "version": CLIENT_VERSION,
            },
        }
        try:
            result = self._send_request("initialize", init_params)
            logger.debug(
                "MCP bridge [%s]: initialized — server: %s, version: %s",
                self.server_name,
                result.get("serverInfo", {}).get("name", "?"),
                result.get("serverInfo", {}).get("version", "?"),
            )

            # Send initialized notification (no response expected)
            notif = json.dumps({
                "jsonrpc": "2.0",
                "method": "notifications/initialized",
            }) + "\n"
            if self._proc and self._proc.stdin:
                self._proc.stdin.write(notif)
                self._proc.stdin.flush()
        except Exception as e:
            raise MCPConnectionError(
                f"Failed to initialize MCP server: {e}"
            ) from e

    def _list_tools(self) -> list[dict]:
        """Call tools/list and return the list of tool definitions."""
        logger.debug("MCP bridge [%s]: listing tools...", self.server_name)
        result = self._send_request("tools/list")
        tools = result.get("tools", [])
        logger.debug(
            "MCP bridge [%s]: found %d tool(s)",
            self.server_name,
            len(tools),
        )
        return tools

    def _register_tools(self, tools: list[dict]) -> None:
        """Register each discovered tool with the OpenAmer tool registry.

        Args:
            tools: List of tool definition dicts from the MCP server.
                   Each has: name, description (optional), inputSchema (optional).
        """
        for tool_def in tools:
            tool_name = tool_def.get("name", "")
            if not tool_name:
                continue

            description = tool_def.get("description", "")
            input_schema = tool_def.get("inputSchema", {}) or {}

            # Ensure inputSchema has the expected structure
            if not input_schema.get("type"):
                input_schema = {
                    "type": "object",
                    "properties": input_schema.get("properties", {}),
                    "required": input_schema.get("required", []),
                }

            # Build the schema dict for OpenAmer's tool registry
            agent_tool_name = _mcp_tool_name(self.server_name, tool_name)
            schema = {
                "name": agent_tool_name,
                "description": description
                    or f"MCP tool '{tool_name}' from server '{self.server_name}'",
                "parameters": input_schema,
            }

            # Create a closure-based handler that captures tool_name
            def _make_handler(
                mcp_connection: MCPConnection, mcp_tool: str
            ) -> Callable:
                def handler(arguments: dict) -> dict:
                    try:
                        result = mcp_connection.call_tool(mcp_tool, arguments)
                        return result
                    except MCPConnectionError as e:
                        return {"error": str(e)}
                    except Exception as e:
                        return {"error": f"Unexpected error: {e}"}

                return handler

            handler = _make_handler(self, tool_name)

            try:
                self.ctx.register_tool(
                    name=agent_tool_name,
                    toolset=f"mcp-bridge-{self.server_name}",
                    schema=schema,
                    handler=handler,
                    description=description[:200],
                    emoji="\U0001f50c",
                )
                self._tool_handlers[tool_name] = handler
                self._tool_names.append(agent_tool_name)
                logger.debug(
                    "MCP bridge: registered tool '%s' from server '%s'",
                    agent_tool_name,
                    self.server_name,
                )
            except Exception as e:
                self.ctx.log_error(
                    f"MCP bridge: failed to register tool '{agent_tool_name}': {e}"
                )

    def _do_call_tool(self, tool_name: str, arguments: dict) -> dict:
        """Execute the actual tools/call RPC."""
        params = {
            "name": tool_name,
            "arguments": arguments,
        }
        try:
            result = self._send_request("tools/call", params)
            # The MCP protocol returns a "content" array with items that have
            # a "type" field (text, image, resource, etc.)
            content = result.get("content", [])
            if content:
                # Extract text from content items
                texts = []
                for item in content:
                    if isinstance(item, dict):
                        item_type = item.get("type", "")
                        if item_type == "text":
                            texts.append(item.get("text", ""))
                        elif item_type == "resource":
                            # Resource content — include as JSON
                            texts.append(
                                json.dumps(
                                    item.get("resource", {}),
                                    ensure_ascii=False,
                                )
                            )
                        else:
                            texts.append(
                                json.dumps(item, ensure_ascii=False)
                            )
                    else:
                        texts.append(str(item))
                return {"result": "\n".join(texts)}

            if "result" in result:
                return {"result": result["result"]}

            return {"result": json.dumps(result, ensure_ascii=False)}
        except MCPConnectionError as e:
            return {"error": f"MCP error: {e}"}

    @staticmethod
    def _make_error(message: str) -> dict:
        """Build a standard error response dict."""
        return {"error": message}


# ── Bridge Manager (Singleton) ────────────────────────────────────────────────


class MCPBridgeManager:
    """Manages multiple MCP server connections.

    Thread-safe singleton that controls the lifecycle of all MCP servers
    configured for the agent.
    """

    def __init__(self, ctx: Any) -> None:
        self.ctx = ctx
        self._connections: dict[str, MCPConnection] = {}
        self._lock = threading.Lock()

    def add_server(
        self,
        server_name: str,
        command: str,
        args: list[str] | None = None,
        env: dict[str, str] | None = None,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> MCPConnection:
        """Add and start a new MCP server connection.

        Args:
            server_name: Unique name for this server.
            command: The executable to run.
            args: Optional command-line arguments.
            env: Optional extra environment variables.
            timeout: Per-call timeout in seconds.

        Returns:
            The MCPConnection instance.

        Raises:
            ValueError: If a server with this name already exists.
        """
        with self._lock:
            if server_name in self._connections:
                raise ValueError(
                    f"MCP server '{server_name}' is already registered"
                )

            conn = MCPConnection(
                ctx=self.ctx,
                server_name=server_name,
                command=command,
                args=args,
                env=env,
                timeout=timeout,
            )
            self._connections[server_name] = conn

        # Start connection in a background thread
        thread = threading.Thread(
            target=conn.connect_and_register,
            name=f"mcp-connect-{server_name}",
            daemon=True,
        )
        thread.start()
        return conn

    def get_connection(self, server_name: str) -> MCPConnection | None:
        """Get an MCP connection by server name."""
        with self._lock:
            return self._connections.get(server_name)

    def close_all(self) -> None:
        """Shut down all MCP server connections."""
        with self._lock:
            names = list(self._connections.keys())
            for name in names:
                conn = self._connections.pop(name, None)
                if conn:
                    try:
                        conn.shutdown()
                    except Exception as e:
                        logger.warning(
                            "MCP bridge: error shutting down '%s': %s",
                            name,
                            e,
                        )


# ── Singleton Slot ────────────────────────────────────────────────────────────


_manager_instance: Optional[MCPBridgeManager] = None
_manager_lock = threading.Lock()


def _get_manager(ctx: Any) -> MCPBridgeManager:
    """Thread-safe lazy singleton accessor for MCPBridgeManager."""
    global _manager_instance
    if _manager_instance is not None:
        return _manager_instance
    with _manager_lock:
        if _manager_instance is not None:
            return _manager_instance
        _manager_instance = MCPBridgeManager(ctx)
        return _manager_instance


# ── Plugin Entry Point ────────────────────────────────────────────────────────


def register(ctx) -> None:
    """Plugin entry point — called by the plugin loader on startup.

    Reads MCP server configurations from the agent config and starts
    connections to each configured server.
    """
    @ctx.on_ready
    def on_ready() -> None:
        """Start all configured MCP servers after the agent is fully loaded."""
        servers: list[dict] = ctx.get_config("servers", [])

        if not servers:
            ctx.log_info(
                "MCP bridge: no servers configured — "
                "add plugin.mcp-bridge.servers to config.yaml"
            )
            return

        manager = _get_manager(ctx)

        for server_cfg in servers:
            name = server_cfg.get("name")
            command = server_cfg.get("command")
            if not name or not command:
                ctx.log_warning(
                    "MCP bridge: skipping server with missing name or command"
                )
                continue

            try:
                manager.add_server(
                    server_name=name,
                    command=command,
                    args=server_cfg.get("args", []),
                    env=server_cfg.get("env", {}),
                    timeout=server_cfg.get("timeout", DEFAULT_TIMEOUT),
                )
            except ValueError as e:
                ctx.log_warning(
                    f"MCP bridge: {e}"
                )
            except Exception as e:
                ctx.log_error(
                    f"MCP bridge: failed to add server '{name}': {e}"
                )