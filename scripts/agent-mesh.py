#!/usr/bin/env python3
"""
Distributed Agent Mesh — Master/Worker-Nodes, HTTP-Task-Delegation, Heartbeat, Local-First Fallback.

CLI Usage:
    agent-mesh.py start                  # Start master node (default port 8900)
    agent-mesh.py node --port 8901       # Start worker node
    agent-mesh.py status                 # List all known nodes and their health
    agent-mesh.py delegate 'task' --to node1  # Delegate a task to a named node
    agent-mesh.py register --host 10.0.0.5 --port 8902 --capabilities '["code","build"]'

Environment:
    OPENAMER_MESH_SECRET   Shared secret for request authentication (required for multi-node).
    OPENAMER_MESH_HOME     Override data directory (default: ~/.openamer/agent-mesh).
"""

import argparse
import json
import logging
import os
import secrets
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.error import URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S%z",
)
logger = logging.getLogger("agent-mesh")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
DEFAULT_MASTER_PORT = 8900
DEFAULT_WORKER_PORT = 8901
HEARTBEAT_INTERVAL = 30       # seconds between pings
HEARTBEAT_MISS_LIMIT = 3      # dead after N consecutive misses
HEARTBEAT_TIMEOUT = 10        # per-ping HTTP timeout
AGENT_MESH_DIR = Path(
    os.environ.get("OPENAMER_MESH_HOME") or
    Path.home() / ".openamer" / "agent-mesh"
)
NODES_FILE = AGENT_MESH_DIR / "nodes.json"
LOCAL_NODE_ID = f"local-{uuid.uuid4().hex[:8]}"

# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

class NodeInfo:
    """In-memory representation of a mesh node."""
    def __init__(
        self,
        node_id: str,
        host: str,
        port: int,
        capabilities: Optional[List[str]] = None,
        role: str = "worker",
    ):
        self.node_id = node_id
        self.host = host
        self.port = port
        self.capabilities = capabilities or []
        self.role = role
        self.last_seen: Optional[float] = None
        self.missed_heartbeats = 0
        self.alive = True
        self.last_error: Optional[str] = None

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "host": self.host,
            "port": self.port,
            "capabilities": self.capabilities,
            "role": self.role,
            "last_seen": self.last_seen,
            "missed_heartbeats": self.missed_heartbeats,
            "alive": self.alive,
            "last_error": self.last_error,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "NodeInfo":
        n = cls(
            node_id=d["node_id"],
            host=d["host"],
            port=d["port"],
            capabilities=d.get("capabilities", []),
            role=d.get("role", "worker"),
        )
        n.last_seen = d.get("last_seen")
        n.missed_heartbeats = d.get("missed_heartbeats", 0)
        n.alive = d.get("alive", True)
        n.last_error = d.get("last_error")
        return n


class MeshState:
    """Thread-safe mesh state backed by a JSON file."""

    def __init__(self, path: Path = NODES_FILE):
        self.path = path
        self._lock = threading.Lock()
        self._nodes: Dict[str, NodeInfo] = {}
        self._load()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------
    def _load(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            try:
                raw = json.loads(self.path.read_text(encoding="utf-8"))
                for d in raw.get("nodes", []):
                    n = NodeInfo.from_dict(d)
                    self._nodes[n.node_id] = n
                logger.info("Loaded %d known nodes from %s", len(self._nodes), self.path)
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning("Failed to load %s (%s); starting fresh", self.path, e)

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        raw = {"nodes": [n.to_dict() for n in self._nodes.values()]}
        tmp = self.path.with_suffix(".tmp")
        try:
            tmp.write_text(json.dumps(raw, indent=2, ensure_ascii=False), encoding="utf-8")
            tmp.replace(self.path)
        except OSError as e:
            logger.error("Failed to save state: %s", e)

    # ------------------------------------------------------------------
    # Node CRUD
    # ------------------------------------------------------------------
    def register(self, node: NodeInfo) -> bool:
        with self._lock:
            existing = self._nodes.get(node.node_id)
            if existing:
                existing.host = node.host
                existing.port = node.port
                existing.capabilities = node.capabilities
                existing.role = node.role
                existing.last_seen = time.time()
                existing.missed_heartbeats = 0
                existing.alive = True
                existing.last_error = None
                logger.info("Updated node %s at %s", node.node_id, node.url)
            else:
                node.last_seen = time.time()
                node.missed_heartbeats = 0
                node.alive = True
                self._nodes[node.node_id] = node
                logger.info("Registered new node %s at %s", node.node_id, node.url)
            self._save()
            return True

    def unregister(self, node_id: str) -> bool:
        with self._lock:
            if node_id in self._nodes:
                del self._nodes[node_id]
                self._save()
                logger.info("Unregistered node %s", node_id)
                return True
            return False

    def mark_dead(self, node_id: str, error: str) -> None:
        with self._lock:
            n = self._nodes.get(node_id)
            if n:
                n.alive = False
                n.last_error = error
                self._save()

    def touch(self, node_id: str) -> None:
        with self._lock:
            n = self._nodes.get(node_id)
            if n:
                n.last_seen = time.time()
                n.missed_heartbeats = 0
                n.alive = True
                n.last_error = None

    def get_node(self, node_id: str) -> Optional[NodeInfo]:
        with self._lock:
            return self._nodes.get(node_id)

    def list_nodes(self) -> List[NodeInfo]:
        with self._lock:
            return list(self._nodes.values())

    def alive_nodes(self) -> List[NodeInfo]:
        return [n for n in self.list_nodes() if n.alive and n.role != "master"]

    def master_node(self) -> Optional[NodeInfo]:
        for n in self.list_nodes():
            if n.role == "master":
                return n
        return None

    def find_node_by_name(self, name: str) -> Optional[NodeInfo]:
        """Match by node_id, hostname prefix, or 'local'."""
        with self._lock:
            for n in self._nodes.values():
                if n.node_id == name or n.node_id.startswith(name):
                    return n
                if n.host == name or n.host.split(".")[0] == name:
                    return n
            return None


# ---------------------------------------------------------------------------
# HTTP Server
# ---------------------------------------------------------------------------

class MeshHTTPHandler(BaseHTTPRequestHandler):
    """HTTP request handler for the mesh protocol."""

    # Shared references set by the server factory
    state: MeshState = None  # type: ignore[assignment]
    local_node_id: str = ""
    local_capabilities: List[str] = []

    def log_message(self, fmt: str, *args: Any) -> None:
        logger.info("HTTP %s %s", self.command, self.path)

    def _verify_token(self) -> Optional[Tuple[int, str]]:
        """Return None if valid, or (status, body) if invalid."""
        secret = os.environ.get("OPENAMER_MESH_SECRET", "")
        if not secret:
            return None  # no secret configured → skip auth
        token = self.headers.get("X-Mesh-Token", "")
        if not token:
            return self._json_error(401, "Missing X-Mesh-Token header")
        if not secrets.compare_digest(token, secret):
            return self._json_error(403, "Invalid token")
        return None

    def _json_error(self, code: int, msg: str) -> Tuple[int, str]:
        return code, json.dumps({"error": msg}, ensure_ascii=False)

    def _send_json(self, data: Any, status: int = 200) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    # ------------------------------------------------------------------
    # Routes
    # ------------------------------------------------------------------
    def do_POST(self) -> None:
        path = urlparse(self.path).path.rstrip("/")
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length) if content_length else b""

        err = self._verify_token()
        if err:
            self._send_json({"error": err[1]}, err[0])
            return

        try:
            payload = json.loads(body) if body else {}
        except json.JSONDecodeError:
            self._send_json({"error": "Invalid JSON"}, 400)
            return

        if path == "/register" or path == "/ping":
            node_id = payload.get("node_id", "")
            host = payload.get("host", self.client_address[0])
            port = int(payload.get("port", 0))
            capabilities = payload.get("capabilities", [])
            role = payload.get("role", "worker")

            if not node_id or not port:
                self._send_json({"error": "node_id and port required"}, 400)
                return

            node = NodeInfo(node_id, host, port, capabilities, role)
            self.state.register(node)
            self._send_json({"status": "ok", "node_id": node_id})

        elif path == "/run":
            task = payload.get("task", "")
            if not task:
                self._send_json({"error": "task field required"}, 400)
                return
            task_id = payload.get("task_id", uuid.uuid4().hex)
            logger.info("Received task %s: %.80s...", task_id, task)
            # Execute the task locally (in the server thread — simple)
            # For real workloads this would go to a thread pool, but for
            # the mesh protocol this is enough to demonstrate delegation.
            try:
                result = _run_task_locally(task, self.local_capabilities)
                self._send_json({
                    "status": "ok",
                    "task_id": task_id,
                    "result": result,
                })
            except Exception as e:
                logger.exception("Task %s failed", task_id)
                self._send_json({
                    "status": "error",
                    "task_id": task_id,
                    "error": str(e),
                }, 500)

        elif path == "/status":
            nodes = self.state.list_nodes()
            self._send_json({
                "status": "ok",
                "node_id": self.local_node_id,
                "capabilities": self.local_capabilities,
                "nodes": [n.to_dict() for n in nodes],
            })

        elif path == "/unregister":
            node_id = payload.get("node_id", "")
            if node_id:
                self.state.unregister(node_id)
            self._send_json({"status": "ok"})

        else:
            self._send_json({"error": f"Unknown path: {path}"}, 404)

    def do_GET(self) -> None:
        path = urlparse(self.path).path.rstrip("/")
        err = self._verify_token()
        if err:
            self._send_json({"error": err[1]}, err[0])
            return

        if path == "/status" or path == "/health":
            nodes = self.state.list_nodes()
            self._send_json({
                "status": "ok",
                "node_id": self.local_node_id,
                "capabilities": self.local_capabilities,
                "nodes": [n.to_dict() for n in nodes],
            })
        elif path == "/ping":
            self._send_json({"status": "pong", "node_id": self.local_node_id})
        else:
            self._send_json({"error": f"Unknown path: {path}"}, 404)


def _run_task_locally(task: str, capabilities: List[str]) -> Dict[str, Any]:
    """Execute a task string on the local machine.
    
    This is a simple placeholder that records the task. In production this
    could dispatch to an agent, a shell command, or a skill.
    """
    from subprocess import run as subprocess_run, PIPE, TimeoutExpired

    logger.info("Executing task locally: %.80s...", task)

    # Try to run as a shell command. If it looks like a natural language
    # task rather than a command, we just record it.
    if task.startswith("!"):
        # Shell command: prefix with !
        cmd = task[1:]
        try:
            result = subprocess_run(
                cmd, shell=True, capture_output=True, text=True, timeout=120
            )
            return {
                "exit_code": result.returncode,
                "stdout": result.stdout[:5000],
                "stderr": result.stderr[:2000],
            }
        except TimeoutExpired:
            return {"error": "Command timed out", "exit_code": -1}
        except Exception as e:
            return {"error": str(e), "exit_code": -1}
    else:
        # Natural language / script task — acknowledge
        return {
            "received": True,
            "task_preview": task[:200],
            "executed_by": "local",
            "capabilities": capabilities,
            "note": "Task recorded. Use '!' prefix for shell commands.",
        }


# ---------------------------------------------------------------------------
# Heartbeat Thread
# ---------------------------------------------------------------------------

def _heartbeat_worker(
    state: MeshState,
    local_node: Optional[NodeInfo],
    stop_event: threading.Event,
) -> None:
    """Periodically ping all known nodes and mark dead on timeout."""
    while not stop_event.is_set():
        nodes = state.list_nodes()
        for node in nodes:
            if node.node_id == (local_node.node_id if local_node else None):
                continue
            if node.role == "master":
                continue
            _ping_node(state, node)

        stop_event.wait(HEARTBEAT_INTERVAL)


def _ping_node(state: MeshState, node: NodeInfo) -> bool:
    """Send a single ping to a node. Returns True if alive."""
    secret = os.environ.get("OPENAMER_MESH_SECRET", "")
    url = f"{node.url}/ping"
    headers = {"Content-Type": "application/json"}
    if secret:
        headers["X-Mesh-Token"] = secret

    try:
        payload = json.dumps({"node_id": node.node_id}).encode("utf-8")
        req = Request(url, data=payload, headers=headers, method="POST")
        resp = urlopen(req, timeout=HEARTBEAT_TIMEOUT)
        data = json.loads(resp.read().decode("utf-8"))
        if data.get("status") == "pong":
            state.touch(node.node_id)
            node.missed_heartbeats = 0
            node.alive = True
            logger.debug("Heartbeat OK for %s (%s)", node.node_id, node.url)
            return True
    except (URLError, OSError, json.JSONDecodeError) as e:
        node.missed_heartbeats += 1
        logger.warning(
            "Heartbeat MISS for %s (%d/%d): %s",
            node.node_id,
            node.missed_heartbeats,
            HEARTBEAT_MISS_LIMIT,
            e,
        )
        if node.missed_heartbeats >= HEARTBEAT_MISS_LIMIT:
            state.mark_dead(node.node_id, str(e))
            logger.error("Node %s marked DEAD after %d missed heartbeats",
                         node.node_id, node.missed_heartbeats)
    return False


# ---------------------------------------------------------------------------
# Task Delegation
# ---------------------------------------------------------------------------

def delegate_task(
    state: MeshState,
    task: str,
    target_node_id: str,
    capabilities: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Delegate a task to a remote node, falling back to local execution."""
    node = state.find_node_by_name(target_node_id)
    if not node:
        return {"error": f"Unknown node: {target_node_id}", "status": "error"}

    if not node.alive:
        logger.warning("Node %s is dead; falling back to local execution", node.node_id)
        return _fallback_local(task, capabilities or [])

    secret = os.environ.get("OPENAMER_MESH_SECRET", "")
    task_id = uuid.uuid4().hex
    url = f"{node.url}/run"
    headers = {"Content-Type": "application/json"}
    if secret:
        headers["X-Mesh-Token"] = secret

    payload = json.dumps({
        "task": task,
        "task_id": task_id,
        "source": LOCAL_NODE_ID,
    }).encode("utf-8")

    try:
        req = Request(url, data=payload, headers=headers, method="POST")
        resp = urlopen(req, timeout=300)  # 5 min timeout for long tasks
        result = json.loads(resp.read().decode("utf-8"))
        logger.info("Task %s delegated to %s: %s", task_id, node.node_id, result.get("status"))
        return result
    except (URLError, OSError, json.JSONDecodeError) as e:
        logger.warning("Delegation to %s failed (%s); falling back to local", node.node_id, e)
        return _fallback_local(task, capabilities or [])


def _fallback_local(task: str, capabilities: List[str]) -> Dict[str, Any]:
    """Local-first fallback: execute the task on this machine."""
    logger.info("Local-fallback executing task: %.80s...", task)
    result = _run_task_locally(task, capabilities)
    result["delegation"] = "local_fallback"
    return result


# ---------------------------------------------------------------------------
# HTTP Server Runner
# ---------------------------------------------------------------------------

def _make_handler(
    state: MeshState,
    node_id: str,
    capabilities: List[str],
) -> type:
    """Create a handler class with the right state references."""
    class _Handler(MeshHTTPHandler):
        local_node_id: str = node_id
        local_capabilities: List[str] = capabilities
    _Handler.state = state
    return _Handler


def run_server(
    host: str,
    port: int,
    state: MeshState,
    node_id: str,
    capabilities: List[str],
    stop_event: threading.Event,
) -> None:
    """Start the HTTP server and run until stop_event is set."""
    handler = _make_handler(state, node_id, capabilities)
    server = HTTPServer((host, port), handler)
    logger.info("Mesh node %s listening on %s:%d", node_id, host, port)
    # Register self
    local_node = NodeInfo(
        node_id=node_id,
        host=host,
        port=port,
        capabilities=capabilities,
        role="master" if "master" in node_id else "worker",
    )
    state.register(local_node)

    # Start heartbeat thread for workers
    hb_stop = threading.Event()
    hb_thread = threading.Thread(
        target=_heartbeat_worker,
        args=(state, local_node, hb_stop),
        daemon=True,
        name="heartbeat",
    )
    hb_thread.start()

    try:
        while not stop_event.is_set():
            server.timeout = 1.0
            server.handle_request()
    except KeyboardInterrupt:
        pass
    finally:
        hb_stop.set()
        hb_thread.join(timeout=5)
        server.server_close()
        logger.info("Mesh node %s stopped", node_id)


# ---------------------------------------------------------------------------
# CLI Commands
# ---------------------------------------------------------------------------

def cmd_start(args: argparse.Namespace) -> None:
    """Start the master node."""
    port = args.port or DEFAULT_MASTER_PORT
    host = args.host or "0.0.0.0"
    capabilities = args.capabilities or ["code", "shell", "delegate"]
    node_id = f"master-{uuid.uuid4().hex[:8]}"
    state = MeshState()
    stop_event = threading.Event()

    logger.info("Starting MASTER node on %s:%d (id=%s)", host, port, node_id)
    logger.info("Capabilities: %s", capabilities)
    if os.environ.get("OPENAMER_MESH_SECRET"):
        logger.info("Mesh secret: CONFIGURED")
    else:
        logger.warning("OPENAMER_MESH_SECRET not set — no authentication!")

    try:
        run_server(host, port, state, node_id, capabilities, stop_event)
    except KeyboardInterrupt:
        logger.info("Shutting down master...")
        stop_event.set()


def cmd_node(args: argparse.Namespace) -> None:
    """Start a worker node (registers with master if --master-url given)."""
    port = args.port or DEFAULT_WORKER_PORT
    host = args.host or "0.0.0.0"
    capabilities = args.capabilities or ["code", "shell"]
    node_id = f"node-{uuid.uuid4().hex[:8]}"
    state = MeshState()
    stop_event = threading.Event()

    logger.info("Starting WORKER node on %s:%d (id=%s)", host, port, node_id)
    logger.info("Capabilities: %s", capabilities)

    # Register with master if URL provided
    master_url = args.master_url or os.environ.get("OPENAMER_MESH_MASTER")
    if master_url:
        secret = os.environ.get("OPENAMER_MESH_SECRET", "")
        headers = {"Content-Type": "application/json"}
        if secret:
            headers["X-Mesh-Token"] = secret
        payload = json.dumps({
            "node_id": node_id,
            "host": _get_local_ip(),
            "port": port,
            "capabilities": capabilities,
            "role": "worker",
        }).encode("utf-8")
        try:
            req = Request(f"{master_url}/register", data=payload, headers=headers, method="POST")
            resp = urlopen(req, timeout=10)
            result = json.loads(resp.read().decode("utf-8"))
            logger.info("Registered with master at %s: %s", master_url, result)
        except (URLError, OSError, json.JSONDecodeError) as e:
            logger.warning("Failed to register with master at %s: %s", master_url, e)
            logger.info("Continuing as standalone worker — master will discover via heartbeat")
    else:
        logger.info("No master URL provided — running as standalone worker")

    try:
        run_server(host, port, state, node_id, capabilities, stop_event)
    except KeyboardInterrupt:
        logger.info("Shutting down worker...")
        stop_event.set()


def cmd_status(args: argparse.Namespace) -> None:
    """Print the status of all known nodes."""
    state = MeshState()
    nodes = state.list_nodes()

    if not nodes:
        print("No nodes registered. Start a mesh node first:")
        print("  agent-mesh.py start")
        print("  agent-mesh.py node --port 8901")
        return

    print(f"\n{'Node ID':<30} {'Host':<20} {'Port':<6} {'Role':<10} {'Alive':<8} {'Misses':<8} {'Capabilities'}")
    print("-" * 120)
    for n in sorted(nodes, key=lambda x: x.role, reverse=True):
        alive_mark = "✓" if n.alive else "✗"
        last_seen_str = ""
        if n.last_seen:
            ago = time.time() - n.last_seen
            last_seen_str = f"{ago:.0f}s ago"
        caps = ",".join(n.capabilities[:3])
        if len(n.capabilities) > 3:
            caps += "..."
        print(
            f"{n.node_id:<30} {n.host:<20} {n.port:<6} {n.role:<10} "
            f"{alive_mark:<8} {n.missed_heartbeats:<8} {caps}"
        )
        if n.last_error:
            print(f"  └─ Last error: {n.last_error}")
    print(f"\nTotal: {len(nodes)} nodes ({sum(1 for n in nodes if n.alive)} alive)")


def cmd_delegate(args: argparse.Namespace) -> None:
    """Delegate a task to a node (with local-first fallback)."""
    state = MeshState()
    task = args.task
    target = args.to

    if not task:
        print("Error: No task specified.")
        return

    if not target:
        print("Error: No target node specified (use --to).")
        return

    node = state.find_node_by_name(target)
    if not node:
        print(f"Error: Unknown node '{target}'. Known nodes:")
        for n in state.list_nodes():
            print(f"  {n.node_id} ({n.host}:{n.port}) {'✓' if n.alive else '✗'}")
        return

    print(f"Delegating task to {node.node_id} ({node.url})...")
    result = delegate_task(state, task, target)
    status = result.get("status", "unknown")
    delegation = result.get("delegation", "remote")

    print(f"\nStatus: {status}")
    print(f"Delegation: {delegation}")

    if "result" in result:
        r = result["result"]
        if isinstance(r, dict):
            if "stdout" in r:
                print(f"\n--- stdout ---\n{r['stdout']}")
            if "stderr" in r and r["stderr"]:
                print(f"--- stderr ---\n{r['stderr']}")
            if r.get("received"):
                print(f"Task recorded (preview: {r.get('task_preview', '')})")
        else:
            print(f"Result: {r}")
    if "error" in result:
        print(f"Error: {result['error']}")


def cmd_register(args: argparse.Namespace) -> None:
    """Manually register a node (without running a server)."""
    state = MeshState()
    node_id = args.node_id or f"node-{uuid.uuid4().hex[:8]}"
    host = args.host or "127.0.0.1"
    port = args.port or DEFAULT_WORKER_PORT
    capabilities = args.capabilities or ["code"]
    role = args.role or "worker"

    node = NodeInfo(node_id, host, port, capabilities, role)
    state.register(node)
    print(f"Registered node {node_id} at {host}:{port} (role={role})")


def _get_local_ip() -> str:
    """Get the local IP address that other nodes can reach."""
    try:
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(1)
        try:
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
        except OSError:
            ip = "127.0.0.1"
        finally:
            s.close()
        return ip
    except Exception:
        return "127.0.0.1"


# ---------------------------------------------------------------------------
# Entry Point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Distributed Agent Mesh — Master/Worker orchestration",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # start
    p_start = sub.add_parser("start", help="Start master node (default port 8900)")
    p_start.add_argument("--port", "-p", type=int, default=DEFAULT_MASTER_PORT)
    p_start.add_argument("--host", type=str, default="0.0.0.0")
    p_start.add_argument("--capabilities", "-c", nargs="*", default=["code", "shell", "delegate"])

    # node
    p_node = sub.add_parser("node", help="Start worker node (default port 8901)")
    p_node.add_argument("--port", "-p", type=int, default=DEFAULT_WORKER_PORT)
    p_node.add_argument("--host", type=str, default="0.0.0.0")
    p_node.add_argument("--capabilities", "-c", nargs="*", default=["code", "shell"])
    p_node.add_argument("--master-url", "-m", type=str, default=None,
                        help="Master URL (e.g. http://10.0.0.1:8900) for auto-registration")

    # status
    sub.add_parser("status", help="List all known nodes and their health")

    # delegate
    p_delegate = sub.add_parser("delegate", help="Delegate a task to a node")
    p_delegate.add_argument("task", type=str, help="Task string to delegate")
    p_delegate.add_argument("--to", "-t", type=str, required=True, help="Target node name/id")

    # register
    p_reg = sub.add_parser("register", help="Manually register a node")
    p_reg.add_argument("--node-id", type=str, default=None)
    p_reg.add_argument("--host", type=str, default="127.0.0.1")
    p_reg.add_argument("--port", "-p", type=int, default=DEFAULT_WORKER_PORT)
    p_reg.add_argument("--capabilities", "-c", nargs="*", default=["code"])
    p_reg.add_argument("--role", "-r", type=str, default="worker",
                       choices=["worker", "master"])

    args = parser.parse_args()

    if args.command == "start":
        cmd_start(args)
    elif args.command == "node":
        cmd_node(args)
    elif args.command == "status":
        cmd_status(args)
    elif args.command == "delegate":
        cmd_delegate(args)
    elif args.command == "register":
        cmd_register(args)


if __name__ == "__main__":
    main()