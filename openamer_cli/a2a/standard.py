"""openamer_cli.a2a.standard — A2A v1.0 standard interoperability.

Implements a **bounded subset** of the public Agent2Agent protocol on top of
the existing OpenAmer node server. It is an extension adapter: the custom
``/card`` and signed ``/message`` routes keep working unchanged, and no part of
the mesh/trust runtime is replaced.

Pinned against:

* Specification: https://github.com/a2aproject/A2A tag ``v1.0.1``
  (``docs/specification.md`` — Apache-2.0)
* Wire schema: ``specification/a2a.proto`` (same tag)

Endpoints
---------
``GET  /.well-known/agent-card.json``
    Public Agent Card (A2A §8.2 discovery URI).
``GET  /.well-known/agent.json``
    Pre-1.0 alias of the same card.
``POST <rpc_path>`` (default ``/a2a``)
    JSON-RPC 2.0 binding (A2A §9): ``SendMessage`` and ``GetTask``.

Deliberately not implemented, and **not** advertised on the card: streaming
(``SendStreamingMessage``), push notifications, ``ListTasks``, ``CancelTask``,
``SubscribeToTask``, extended agent card and multi-tenancy. This module makes
no compliance or interoperability certification claim; it implements the
subset above and reports everything else as an explicit error.

Security model
--------------
* The Agent Card is public (as required for discovery) and contains no peer,
  grant or profile information.
* Every JSON-RPC request requires ``Authorization: Bearer <token>``. The token
  is a secret supplied by the operator; when none is configured the standard
  routes are not served at all (404) rather than falling open.
* A request may only reach the task handler when the configured capability set
  allows ``task.ask``. The handler is the same callback the signed
  ``/message`` channel uses, so tool permissions and approvals are unchanged —
  the adapter never executes tools itself.
* ``A2A-Version`` follows §3.2.6: a client that omits the header is treated as a
  pre-1.0 client, and any version other than the advertised ``1.0`` is
  rejected with ``VersionNotSupportedError`` (-32009).
"""
from __future__ import annotations

import hmac
import json
import threading
import time
import uuid
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional, Tuple

# --- protocol constants (A2A v1.0.1) ----------------------------------------

PROTOCOL_VERSION = "1.0"
SUPPORTED_PROTOCOL_VERSIONS = frozenset({"1.0", "1.0.0"})
#: Version assumed for requests that omit ``A2A-Version`` (A2A §3.2.6: 0.3).
IMPLICIT_PROTOCOL_VERSION = "0.3"

# JSON-RPC error codes used by the A2A binding (A2A §5.4).
ERR_PARSE = -32700
ERR_INVALID_REQUEST = -32600
ERR_METHOD_NOT_FOUND = -32601
ERR_INVALID_PARAMS = -32602
ERR_TASK_NOT_FOUND = -32001
ERR_VERSION_NOT_SUPPORTED = -32009
#: Implementation-defined (A2A reserves -32001..-32009 for named errors).
ERR_UNAUTHORIZED = -32050

TASK_STATE_COMPLETED = "TASK_STATE_COMPLETED"
TASK_STATE_FAILED = "TASK_STATE_FAILED"
ROLE_USER = "ROLE_USER"
ROLE_AGENT = "ROLE_AGENT"

METHOD_SEND_MESSAGE = "SendMessage"
METHOD_GET_TASK = "GetTask"
#: Legacy slash aliases accepted for pre-1.0 clients; never advertised.
METHOD_ALIASES = {
    "message/send": METHOD_SEND_MESSAGE,
    "tasks/get": METHOD_GET_TASK,
}
SUPPORTED_METHODS = frozenset({METHOD_SEND_MESSAGE, METHOD_GET_TASK})

MAX_BODY_BYTES = 1_048_576
DEFAULT_MAX_TASKS = 256


def now_iso() -> str:
    """ISO 8601 UTC timestamp with millisecond precision."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def jsonrpc_result(req_id: Any, result: Any) -> dict:
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def jsonrpc_error(req_id: Any, code: int, message: str,
                  data: Optional[dict] = None) -> dict:
    err: Dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        err["data"] = data
    return {"jsonrpc": "2.0", "id": req_id, "error": err}


# --- configuration ----------------------------------------------------------


@dataclass(frozen=True)
class StandardA2AConfig:
    """Operator-supplied configuration for the standard A2A surface.

    ``bearer_token`` is a secret (``A2A_BEARER_TOKEN`` in the profile ``.env``
    or an explicit CLI flag). An empty token disables the whole surface.
    """

    bearer_token: str = ""
    public_url: str = ""
    agent_name: str = "OpenAmer"
    description: str = "OpenAmer agent reachable over the standard A2A protocol."
    provider_organization: str = "OpenAmer"
    provider_url: str = ""
    agent_version: str = "1.0.0"
    rpc_path: str = "/a2a"
    capabilities: Tuple[str, ...] = ("task.ask",)

    @property
    def enabled(self) -> bool:
        return bool(self.bearer_token)


# --- Agent Card -------------------------------------------------------------


def _skills_from_capabilities(capabilities: Tuple[str, ...]) -> list:
    skills = []
    for cap in sorted(capabilities):
        skills.append({
            "id": cap,
            "name": cap,
            "description": f"OpenAmer capability '{cap}'",
            "tags": [cap],
        })
    return skills or [{
        "id": "general",
        "name": "general",
        "description": "General-purpose conversational agent",
        "tags": ["general"],
    }]


def build_agent_card(config: StandardA2AConfig, *, base_url: str = "") -> dict:
    """Build an A2A v1.0 ``AgentCard`` (ProtoJSON lowerCamelCase shape).

    ``base_url`` overrides ``config.public_url`` and is normally derived from
    the request ``Host`` header so a loopback node advertises a loopback URL.
    """
    url = (base_url or config.public_url or "").rstrip("/")
    rpc_path = config.rpc_path if config.rpc_path.startswith("/") else "/" + config.rpc_path
    rpc_url = f"{url}{rpc_path}" if url else rpc_path
    provider_url = config.provider_url or url or "https://github.com/openamer/openamer"
    card: Dict[str, Any] = {
        "name": config.agent_name,
        "description": config.description,
        "supportedInterfaces": [{
            "url": rpc_url,
            "protocolBinding": "JSONRPC",
            "protocolVersion": PROTOCOL_VERSION,
        }],
        "provider": {
            "organization": config.provider_organization,
            "url": provider_url,
        },
        "version": config.agent_version,
        "capabilities": {
            "streaming": False,
            "pushNotifications": False,
            "extendedAgentCard": False,
        },
        "defaultInputModes": ["text/plain"],
        "defaultOutputModes": ["text/plain"],
        "skills": _skills_from_capabilities(tuple(config.capabilities)),
        "securitySchemes": {
            "bearer": {"httpBearerSecurityScheme": {"scheme": "Bearer"}},
        },
        "security": [{"bearer": []}],
    }
    return card


# --- task store -------------------------------------------------------------


class TaskStore:
    """Bounded, thread-safe in-memory task store (oldest evicted first)."""

    def __init__(self, max_tasks: int = DEFAULT_MAX_TASKS) -> None:
        self._max = max(1, int(max_tasks))
        self._tasks: "OrderedDict[str, dict]" = OrderedDict()
        self._lock = threading.Lock()

    def put(self, task: dict) -> None:
        with self._lock:
            task_id = str(task.get("id", ""))
            if not task_id:
                return
            self._tasks[task_id] = task
            self._tasks.move_to_end(task_id)
            while len(self._tasks) > self._max:
                self._tasks.popitem(last=False)

    def get(self, task_id: str, history_length: Optional[int] = None) -> Optional[dict]:
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                return None
            task = json.loads(json.dumps(task))  # deep copy for safe mutation
            self._tasks.move_to_end(task_id)
        if history_length is not None:
            history = task.get("history") or []
            if history_length <= 0:
                task.pop("history", None)
            else:
                task["history"] = history[-history_length:]
        return task

    def clear(self) -> None:
        with self._lock:
            self._tasks.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._tasks)


# --- task request handed to the host callback -------------------------------


@dataclass
class StandardTaskRequest:
    """Inbound standard-protocol task, shaped like the signed Envelope API.

    Existing ``on_task`` callbacks read ``env.kind`` / ``env.payload``; this
    keeps that contract while making the transport origin explicit.
    """

    sender: str
    kind: str
    payload: dict
    transport: str = "a2a-v1.0"
    metadata: dict = field(default_factory=dict)


# --- text extraction --------------------------------------------------------


def extract_text(params: Any) -> str:
    """Concatenate text parts from a ``SendMessageRequest`` params object.

    Accepts v1.0 Parts (``{"text": ...}``) and v0.3 Parts
    (``{"kind": "text", "text": ...}``); non-text parts are ignored.
    """
    message = params.get("message") if isinstance(params, dict) else None
    if not isinstance(message, dict):
        return ""
    chunks = []
    for part in message.get("parts") or []:
        if isinstance(part, dict) and isinstance(part.get("text"), str):
            chunks.append(part["text"])
    return "\n".join(chunks).strip()


def _header(headers: Any, name: str) -> str:
    try:
        return (headers.get(name) or "").strip()
    except Exception:  # noqa: BLE001 - never fail a request on header access
        return ""


# --- service ----------------------------------------------------------------


class StandardA2AService:
    """JSON-RPC/HTTP binding for ``SendMessage`` and ``GetTask``."""

    def __init__(
        self,
        config: StandardA2AConfig,
        *,
        on_task: Optional[Callable[[StandardTaskRequest, dict], Any]] = None,
        task_store: Optional[TaskStore] = None,
        capability_check: Optional[Callable[[str], bool]] = None,
    ) -> None:
        self.config = config
        self.on_task = on_task
        self.tasks = task_store or TaskStore()
        self._capability_check = capability_check

    # -- authentication ----------------------------------------------------

    def authenticate(self, headers: Any) -> bool:
        """Constant-time check of ``Authorization: Bearer <token>``."""
        token = self.config.bearer_token
        if not token:
            return False
        header = _header(headers, "Authorization")
        scheme, _, presented = header.partition(" ")
        if scheme.lower() != "bearer" or not presented:
            return False
        return hmac.compare_digest(presented.strip().encode("utf-8"),
                                   token.encode("utf-8"))

    def has_capability(self, capability: str) -> bool:
        if self._capability_check is not None:
            try:
                return bool(self._capability_check(capability))
            except Exception:  # noqa: BLE001 - fail closed
                return False
        return capability in tuple(self.config.capabilities)

    # -- request handling --------------------------------------------------

    def handle(
        self,
        raw_body: bytes,
        headers: Any,
        *,
        base_url: str = "",
    ) -> Tuple[int, dict, Dict[str, str]]:
        """Handle one JSON-RPC request.

        Returns ``(http_status, jsonrpc_payload, extra_headers)``.
        """
        extra: Dict[str, str] = {}
        if not self.authenticate(headers):
            extra["WWW-Authenticate"] = 'Bearer realm="a2a"'
            return 401, jsonrpc_error(
                None, ERR_UNAUTHORIZED, "unauthorized",
                {"supportedSchemes": ["bearer"]},
            ), extra

        if len(raw_body) > MAX_BODY_BYTES:
            return 413, jsonrpc_error(None, ERR_INVALID_REQUEST,
                                      "request body too large"), extra
        try:
            request = json.loads(raw_body.decode("utf-8") or "{}")
        except Exception:  # noqa: BLE001 - malformed body is a client error
            return 400, jsonrpc_error(None, ERR_PARSE, "parse error"), extra

        if not isinstance(request, dict):
            return 400, jsonrpc_error(
                None, ERR_INVALID_REQUEST, "JSON-RPC request must be an object",
            ), extra

        req_id = request.get("id")
        if request.get("jsonrpc") != "2.0" or not isinstance(request.get("method"), str):
            return 400, jsonrpc_error(
                req_id, ERR_INVALID_REQUEST,
                "invalid JSON-RPC 2.0 request (jsonrpc + method required)",
            ), extra

        method = METHOD_ALIASES.get(request["method"], request["method"])
        params = request.get("params")
        if params is None:
            params = {}
        if not isinstance(params, dict):
            return 400, jsonrpc_error(req_id, ERR_INVALID_PARAMS,
                                      "params must be an object"), extra

        # A2A §3.2.6 version negotiation. Missing header => pre-1.0 client.
        version = _header(headers, "A2A-Version") or str(
            params.get("a2aVersion") or ""
        ).strip() or IMPLICIT_PROTOCOL_VERSION
        if version not in SUPPORTED_PROTOCOL_VERSIONS:
            return 400, jsonrpc_error(
                req_id, ERR_VERSION_NOT_SUPPORTED,
                f"unsupported A2A-Version: {version}",
                {"supportedVersions": sorted(SUPPORTED_PROTOCOL_VERSIONS)},
            ), extra

        if method not in SUPPORTED_METHODS:
            return 200, jsonrpc_error(
                req_id, ERR_METHOD_NOT_FOUND, f"method not found: {request['method']}",
                {"supportedMethods": sorted(SUPPORTED_METHODS)},
            ), extra

        if method == METHOD_SEND_MESSAGE:
            if not self.has_capability("task.ask"):
                # Authorization failure: the caller authenticated but may not
                # ask this node to run tasks (tool permissions are unchanged).
                return 403, jsonrpc_error(
                    req_id, ERR_UNAUTHORIZED, "capability not granted: task.ask",
                    {"requiredCapability": "task.ask"},
                ), extra
            status, payload = self._send_message(req_id, params, base_url=base_url)
            return status, payload, extra
        status, payload = self._get_task(req_id, params)
        return status, payload, extra

    # -- SendMessage -------------------------------------------------------

    def _send_message(self, req_id: Any, params: dict, *,
                      base_url: str = "") -> Tuple[int, dict]:
        message = params.get("message")
        if not isinstance(message, dict):
            return 200, jsonrpc_error(req_id, ERR_INVALID_PARAMS,
                                      "params.message is required")
        message_id = message.get("messageId")
        if not isinstance(message_id, str) or not message_id:
            return 200, jsonrpc_error(req_id, ERR_INVALID_PARAMS,
                                      "message.messageId is required")

        text = extract_text(params)
        if not text:
            return 200, jsonrpc_error(
                req_id, ERR_INVALID_PARAMS,
                "message.parts must contain at least one text part",
            )

        task_id = "task-" + uuid.uuid4().hex[:16]
        context_id = ""
        if isinstance(message.get("contextId"), str):
            context_id = message["contextId"].strip()
        context_id = context_id or "ctx-" + uuid.uuid4().hex[:16]

        user_message = {
            "messageId": message_id,
            "contextId": context_id,
            "role": ROLE_USER,
            "parts": [{"text": text, "mediaType": "text/plain"}],
        }
        if isinstance(message.get("taskId"), str) and message["taskId"]:
            user_message["taskId"] = message["taskId"]

        task, answer = self._run_task(
            task_id=task_id,
            context_id=context_id,
            user_message=user_message,
            text=text,
        )
        self.tasks.put(task)
        return 200, jsonrpc_result(req_id, {"task": task})

    def _run_task(self, *, task_id: str, context_id: str,
                  user_message: dict, text: str) -> Tuple[dict, str]:
        result: Any = None
        failure = ""
        if self.on_task is None:
            failure = "no task handler configured on this node"
        else:
            request = StandardTaskRequest(
                sender="a2a-standard",
                kind="ask",
                payload={"question": text},
            )
            try:
                result = self.on_task(request, {"transport": "a2a-v1.0"})
            except Exception as exc:  # noqa: BLE001 - surface, never crash the server
                failure = f"task handler failed: {exc}"

        answer = ""
        if not failure:
            if isinstance(result, dict):
                if result.get("error"):
                    failure = str(result["error"])
                answer = str(result.get("answer") or result.get("result") or "")
            elif result is not None:
                answer = str(result)

        terminal_state = TASK_STATE_FAILED if failure else TASK_STATE_COMPLETED
        agent_message = {
            "messageId": uuid.uuid4().hex,
            "contextId": context_id,
            "role": ROLE_AGENT,
            "parts": [{"text": failure or answer, "mediaType": "text/plain"}],
        }
        task: Dict[str, Any] = {
            "id": task_id,
            "contextId": context_id,
            "status": {
                "state": terminal_state,
                "timestamp": now_iso(),
            },
            "artifacts": [{
                "artifactId": "artifact-" + uuid.uuid4().hex[:16],
                "parts": [{"text": failure or answer, "mediaType": "text/plain"}],
            }],
            "history": [user_message, agent_message],
        }
        if failure:
            task["metadata"] = {"error": failure}
        return task, answer

    # -- GetTask -----------------------------------------------------------

    def _get_task(self, req_id: Any, params: dict) -> Tuple[int, dict]:
        task_id = params.get("id")
        if not isinstance(task_id, str) or not task_id:
            return 200, jsonrpc_error(req_id, ERR_INVALID_PARAMS,
                                      "params.id is required")
        history_length = params.get("historyLength")
        if history_length is not None and not isinstance(history_length, int):
            return 200, jsonrpc_error(req_id, ERR_INVALID_PARAMS,
                                      "params.historyLength must be an integer")
        task = self.tasks.get(task_id, history_length=history_length)
        if task is None:
            # A2A §5.4: TaskNotFoundError maps to HTTP 404.
            return 404, jsonrpc_error(req_id, ERR_TASK_NOT_FOUND,
                                      f"task not found: {task_id}")
        return 200, jsonrpc_result(req_id, task)


__all__ = [
    "PROTOCOL_VERSION",
    "SUPPORTED_PROTOCOL_VERSIONS",
    "StandardA2AConfig",
    "StandardA2AService",
    "StandardTaskRequest",
    "TaskStore",
    "build_agent_card",
    "extract_text",
    "jsonrpc_error",
    "jsonrpc_result",
    "now_iso",
]
