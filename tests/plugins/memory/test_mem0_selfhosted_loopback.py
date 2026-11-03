"""Contract tests for the mem0 self-hosted (HTTP) backend over a REAL loopback server.

The existing ``test_mem0_backend.py`` drives :class:`SelfHostedBackend` through
``httpx.MockTransport``, which never opens a socket: header propagation,
content-type, connection reuse, concurrent prefetch requests and the actual
4xx/5xx responses a deployed Mem0 server emits are all invisible there.

This module runs a threaded :class:`http.server.ThreadingHTTPServer` on
127.0.0.1 (ephemeral port) that implements the routes/DTOs of the self-hosted
Mem0 FastAPI app at the pinned ``mem0ai==2.0.10`` tag (``server/main.py``):

  * ``POST /memories``  (MemoryCreate: messages/user_id/agent_id/infer/metadata)
  * ``POST /search``    (SearchRequest: query/top_k/``filters``; top-level
    ``user_id`` is deprecated server-side)
  * ``PUT`` / ``DELETE /memories/{memory_id}``
  * ``X-API-Key`` auth (``verify_auth``)
  * client errors as 4xx (``_client_error``), upstream failures as 5xx
    (``upstream_error``) — the distinction the plugin's circuit breaker must
    honour.

Nothing here talks to a cloud endpoint, activates an account, or reads chat
history: every byte is 127.0.0.1.
"""

from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

import plugins.memory.mem0 as mem0_plugin
from plugins.memory.mem0 import Mem0MemoryProvider


# ---------------------------------------------------------------------------
# Loopback fixture: the self-hosted Mem0 server contract
# ---------------------------------------------------------------------------


def _wait_for(predicate, timeout: float = 5.0, interval: float = 0.01) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return False


class _Mem0State:
    """Request handling + assertions surface shared with the test bodies."""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.lock = threading.Lock()
        self.memories: dict[str, dict] = {}
        self.requests: list[dict] = []
        self.search_delay = 0.0
        self.error_status: int | None = None
        self.reject_text_over: int | None = None
        self.unscoped_searches = 0
        self.active = 0
        self.max_active = 0
        self._seq = 0

    # -- helpers used by tests ------------------------------------------
    def requests_for(self, method: str, path_prefix: str = "/") -> list[dict]:
        with self.lock:
            return [
                r for r in self.requests
                if r["method"] == method and r["path"].startswith(path_prefix)
            ]

    def search_requests(self) -> list[dict]:
        return self.requests_for("POST", "/search")

    def _next_id(self) -> str:
        with self.lock:
            self._seq += 1
            return f"mem-{self._seq}"

    # -- routing --------------------------------------------------------
    def handle(self, method: str, path: str, body, headers: dict) -> tuple[int, dict]:
        if self.api_key and headers.get("x-api-key") != self.api_key:
            return 401, {"detail": "Invalid API key"}

        if self.error_status:
            # server/main.py raises 5xx for upstream failures (upstream_error)
            return self.error_status, {"detail": "injected provider failure"}

        if path == "/memories" and method == "POST":
            return self._add(body)
        if path == "/search" and method == "POST":
            return self._search(body)
        if path.startswith("/memories/") and method in ("PUT", "DELETE"):
            return self._mutate(method, path, body)
        return 404, {"detail": "not found"}

    def _add(self, body) -> tuple[int, dict]:
        body = body or {}
        messages = body.get("messages") or []
        identifier = any(body.get(k) for k in ("user_id", "agent_id", "run_id"))
        if not identifier:
            return 400, {
                "detail": "At least one identifier (user_id, agent_id, run_id) is required."
            }
        text = str(messages[0].get("content", "")) if messages else ""
        memory_id = self._next_id()
        with self.lock:
            self.memories[memory_id] = {
                "id": memory_id,
                "memory": text,
                "user_id": body.get("user_id"),
                "agent_id": body.get("agent_id"),
                "metadata": body.get("metadata") or {},
            }
        return 200, {"results": [{"id": memory_id, "memory": text, "event": "ADD"}]}

    def _search(self, body) -> tuple[int, dict]:
        body = body or {}
        if self.search_delay:
            time.sleep(self.search_delay)
        filters = body.get("filters") or {}
        user_id = filters.get("user_id")
        with self.lock:
            rows = [dict(m) for m in self.memories.values()]
            if user_id is None:
                # Real mem0 treats an entity-less filter dict as "every
                # memory everywhere". Counted so tests can assert we never
                # send an unscoped read.
                self.unscoped_searches += 1
        if user_id is not None:
            rows = [r for r in rows if r["user_id"] == user_id]
        query = str(body.get("query") or "").lower()
        hits = [r for r in rows if query in r["memory"].lower()] or rows
        top_k = int(body.get("top_k") or 10)
        return 200, {
            "results": [{**r, "score": 0.9} for r in hits[:top_k]]
        }

    def _mutate(self, method: str, path: str, body) -> tuple[int, dict]:
        memory_id = path.rsplit("/", 1)[-1]
        if method == "PUT":
            text = (body or {}).get("text")
            if self.reject_text_over and text and len(str(text)) > self.reject_text_over:
                # _client_error(ValueError(...)) -> 400, not 404
                return 400, {"detail": "text exceeds the maximum allowed length"}
            with self.lock:
                row = self.memories.get(memory_id)
                if row is None:
                    return 404, {"detail": f"Memory with id {memory_id} not found"}
                row["memory"] = text
            return 200, {"message": "Memory updated successfully"}
        with self.lock:
            if self.memories.pop(memory_id, None) is None:
                return 404, {"detail": f"Memory with id {memory_id} not found"}
        return 200, {"message": "Memory deleted successfully"}


class _Mem0Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "mem0-loopback/1"

    def log_message(self, *args):  # keep pytest output clean
        pass

    def do_POST(self):  # noqa: N802 - BaseHTTPRequestHandler API
        self._dispatch("POST")

    def do_PUT(self):  # noqa: N802
        self._dispatch("PUT")

    def do_DELETE(self):  # noqa: N802
        self._dispatch("DELETE")

    def _dispatch(self, method: str) -> None:
        state: _Mem0State = self.server.state
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b""
        try:
            body = json.loads(raw) if raw else None
        except ValueError:
            body = {"_raw": raw.decode("utf-8", "replace")}
        headers = {k.lower(): v for k, v in self.headers.items()}
        record = {"method": method, "path": self.path, "headers": headers, "body": body}

        with state.lock:
            state.requests.append(record)
            state.active += 1
            state.max_active = max(state.max_active, state.active)
        try:
            status, payload = state.handle(method, self.path, body, headers)
        finally:
            with state.lock:
                state.active -= 1

        encoded = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


class Mem0LoopbackServer:
    def __init__(self, api_key: str = "loopback-admin-key"):
        self.state = _Mem0State(api_key)
        self._httpd = ThreadingHTTPServer(("127.0.0.1", 0), _Mem0Handler)
        self._httpd.state = self.state  # type: ignore[attr-defined]
        self._httpd.daemon_threads = True
        self._thread = threading.Thread(
            target=self._httpd.serve_forever, name="mem0-loopback", daemon=True
        )

    @property
    def host(self) -> str:
        return f"http://127.0.0.1:{self._httpd.server_address[1]}"

    def start(self) -> "Mem0LoopbackServer":
        self._thread.start()
        return self

    def stop(self) -> None:
        self._httpd.shutdown()
        self._httpd.server_close()
        self._thread.join(timeout=5)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def server():
    srv = Mem0LoopbackServer().start()
    try:
        yield srv
    finally:
        srv.stop()


def _make_provider(monkeypatch, host: str, api_key: str, user_id: str) -> Mem0MemoryProvider:
    monkeypatch.setenv("MEM0_MODE", "platform")
    monkeypatch.setenv("MEM0_HOST", host)
    monkeypatch.setenv("MEM0_API_KEY", api_key)
    monkeypatch.delenv("MEM0_USER_ID", raising=False)
    # The plugin lazily pip-installs the mem0ai SDK before building a backend.
    # Self-hosted mode only needs httpx, and tests must never touch the network.
    monkeypatch.setattr("tools.lazy_deps.ensure", lambda *a, **k: None)
    provider = Mem0MemoryProvider()
    provider.initialize("loopback-session", user_id=user_id, platform="cli")
    assert provider._backend is not None, "self-hosted backend failed to initialize"
    return provider


@pytest.fixture
def alice(server, monkeypatch):
    provider = _make_provider(monkeypatch, server.host, server.state.api_key, "u-alice")
    try:
        yield provider
    finally:
        provider.shutdown()


@pytest.fixture
def bob(server, monkeypatch):
    provider = _make_provider(monkeypatch, server.host, server.state.api_key, "u-bob")
    try:
        yield provider
    finally:
        provider.shutdown()


def _call(provider: Mem0MemoryProvider, tool: str, args: dict) -> dict:
    return json.loads(provider.handle_tool_call(tool, args))


# ---------------------------------------------------------------------------
# The tests import the worktree's code, not an installed CLI
# ---------------------------------------------------------------------------


def test_plugin_modules_resolve_inside_the_checkout():
    """Guards the "imports come from the worktree" rule for this file."""
    repo_root = Path(__file__).resolve().parents[3]
    for mod in (mem0_plugin, __import__("plugins.memory.mem0._backend", fromlist=["x"])):
        assert Path(mod.__file__).resolve().is_relative_to(repo_root), mod.__file__


# ---------------------------------------------------------------------------
# Wire-level contract (real socket, real headers, real JSON)
# ---------------------------------------------------------------------------


def test_add_writes_over_the_wire_with_identity_and_channel(server, alice):
    alice._channel = "telegram"
    out = _call(alice, "mem0_add", {"content": "alice likes tea"})
    assert "error" not in out, out

    req = server.state.requests_for("POST", "/memories")[-1]
    assert req["path"] == "/memories"
    assert req["headers"]["x-api-key"] == server.state.api_key
    assert "authorization" not in req["headers"]
    assert req["headers"]["content-type"] == "application/json"
    assert req["body"] == {
        "messages": [{"role": "user", "content": "alice likes tea"}],
        "user_id": "u-alice",
        "agent_id": "openamer",
        "infer": False,
        "metadata": {"channel": "telegram"},
    }


def test_search_sends_identity_inside_filters(server, alice):
    _call(alice, "mem0_add", {"content": "alice likes tea"})
    out = _call(alice, "mem0_search", {"query": "tea"})
    assert out["count"] == 1, out

    req = server.state.search_requests()[-1]
    assert req["body"]["filters"] == {"user_id": "u-alice"}
    assert req["body"]["top_k"] == 10
    # mem0's deprecated top-level user_id must not be used — filters is the
    # supported shape and the only one that stays scoped.
    assert "user_id" not in req["body"]


# ---------------------------------------------------------------------------
# Identity / profile isolation
# ---------------------------------------------------------------------------


def test_identity_isolation_between_two_users(server, alice, bob):
    _call(alice, "mem0_add", {"content": "alice likes tea"})
    _call(bob, "mem0_add", {"content": "bob likes coffee"})

    alice_hits = _call(alice, "mem0_search", {"query": "likes"})
    bob_hits = _call(bob, "mem0_search", {"query": "likes"})

    assert [r["memory"] for r in alice_hits["results"]] == ["alice likes tea"]
    assert [r["memory"] for r in bob_hits["results"]] == ["bob likes coffee"]
    # No read ever left the server unscoped (i.e. a cross-user leak).
    assert server.state.unscoped_searches == 0
    assert {r["body"]["filters"]["user_id"] for r in server.state.search_requests()} == {
        "u-alice", "u-bob"
    }


def test_gateway_native_identity_is_used_when_no_override_configured(server, monkeypatch):
    """No MEM0_USER_ID → the gateway-native id scopes the store, not a shared bucket."""
    provider = _make_provider(monkeypatch, server.host, server.state.api_key, "tg-987654")
    try:
        _call(provider, "mem0_add", {"content": "telegram fact"})
        assert server.state.search_requests() == []
        _call(provider, "mem0_search", {"query": "fact"})
        assert server.state.search_requests()[-1]["body"]["filters"] == {"user_id": "tg-987654"}
    finally:
        provider.shutdown()


# ---------------------------------------------------------------------------
# Correction / delete
# ---------------------------------------------------------------------------


def test_correction_replaces_the_stored_fact(server, alice):
    _call(alice, "mem0_add", {"content": "alice lives in Berlin"})
    hit = _call(alice, "mem0_search", {"query": "Berlin"})["results"][0]

    out = _call(alice, "mem0_update", {"memory_id": hit["id"], "text": "alice lives in Lisbon"})
    assert out == {"result": "Memory updated.", "memory_id": hit["id"]}

    corrected = _call(alice, "mem0_search", {"query": "alice"})
    assert [r["memory"] for r in corrected["results"]] == ["alice lives in Lisbon"]
    # in-place correction, not an append
    assert len(server.state.memories) == 1
    put = server.state.requests_for("PUT", "/memories/")[-1]
    assert put["body"] == {"text": "alice lives in Lisbon"}


def test_delete_removes_the_memory_and_reports_not_found_afterwards(server, alice):
    _call(alice, "mem0_add", {"content": "alice has a dog"})
    hit = _call(alice, "mem0_search", {"query": "dog"})["results"][0]

    assert _call(alice, "mem0_delete", {"memory_id": hit["id"]}) == {
        "result": "Memory deleted.", "memory_id": hit["id"],
    }
    assert _call(alice, "mem0_search", {"query": "dog"}) == {
        "result": "No relevant memories found."
    }
    assert server.state.memories == {}

    again = _call(alice, "mem0_delete", {"memory_id": hit["id"]})
    assert again["error"] == f"Memory not found: {hit['id']}"


# ---------------------------------------------------------------------------
# Error isolation: only provider-side failures may open the breaker
# ---------------------------------------------------------------------------


def test_client_errors_do_not_open_the_circuit_breaker(server, alice):
    """A 4xx from mem0 is the *request's* fault; retrying can't fix it.

    mem0's server maps validation failures to 4xx (``_client_error``) and keeps
    5xx for upstream outages. Treating 4xx as a provider failure tripped the
    global breaker after five bad requests, so every memory call — including
    valid ones — went dark for the 120s cooldown.
    """
    server.state.reject_text_over = 10
    _call(alice, "mem0_add", {"content": "alice likes tea"})

    for _ in range(mem0_plugin._BREAKER_THRESHOLD + 2):
        out = _call(alice, "mem0_update", {"memory_id": "mem-1", "text": "x" * 200})
        assert "error" in out, out

    assert alice._consecutive_failures == 0
    assert alice._is_breaker_open() is False

    # A valid call still reaches the server instead of being short-circuited.
    before = len(server.state.requests)
    out = _call(alice, "mem0_search", {"query": "tea"})
    assert out["count"] == 1, out
    assert len(server.state.requests) > before


def test_provider_failures_open_the_circuit_breaker(server, alice):
    server.state.error_status = 503
    for _ in range(mem0_plugin._BREAKER_THRESHOLD):
        out = _call(alice, "mem0_search", {"query": "tea"})
        assert "error" in out, out

    assert alice._is_breaker_open() is True
    before = len(server.state.requests)
    blocked = _call(alice, "mem0_search", {"query": "tea"})
    assert "temporarily unavailable" in blocked["error"]
    assert len(server.state.requests) == before  # no request left the process


def test_failure_classification_is_structural_not_substring(server, alice):
    """Regression: ``"404" in str(exc)`` matched ids/hosts, not just statuses.

    With a 5xx whose URL merely *contains* "404" (here: the memory id), the
    old substring check classified a hard outage as a client error, so the
    breaker never opened and every call kept hammering the dead server.
    """
    server.state.error_status = 503
    for _ in range(mem0_plugin._BREAKER_THRESHOLD):
        out = _call(alice, "mem0_delete", {"memory_id": "mem-404-dead"})
        assert "error" in out, out

    assert alice._is_breaker_open() is True


def test_missing_api_key_is_rejected_by_the_server_and_never_silently_retried(server, monkeypatch):
    provider = _make_provider(monkeypatch, server.host, "wrong-key", "u-alice")
    try:
        out = _call(provider, "mem0_search", {"query": "tea"})
        assert "error" in out
        assert "401" in out["error"]
        # 401 is a credential problem: no breaker, no retry storm.
        assert provider._consecutive_failures == 0
    finally:
        provider.shutdown()


class _SdkError(Exception):
    """Stand-in for the Platform SDK's generated ``ApiException`` (``.status``)."""

    def __init__(self, status: int, body: str):
        super().__init__(body)
        self.status = status


@pytest.mark.parametrize(
    "status,expected",
    [(400, True), (401, True), (404, True), (408, False), (429, False), (500, False), (503, False)],
)
def test_error_classification_covers_sdk_exceptions_with_a_status_attribute(status, expected):
    """The Platform SDK attaches ``.status``, not ``.response.status_code``."""
    assert mem0_plugin._is_client_error(_SdkError(status, "boom")) is expected


def test_error_classification_falls_back_to_names_and_text_without_a_status():
    class MemoryNotFoundError(Exception):
        pass

    class ValidationError(Exception):
        pass

    assert mem0_plugin._is_client_error(MemoryNotFoundError("gone")) is True
    assert mem0_plugin._is_client_error(ValidationError("bad payload")) is True
    assert mem0_plugin._is_client_error(Exception("memory not found")) is True
    assert mem0_plugin._is_client_error(Exception("connection reset by peer")) is False


# ---------------------------------------------------------------------------
# Bounded concurrency / cleanup (prefetch)
# ---------------------------------------------------------------------------


def test_prefetch_is_single_flight_against_a_slow_server(server, alice):
    """One hung recall per provider instance, not one per turn.

    A stalled server holds each request for the client timeout (30s). Before
    single-flight, every new query wording started another recall thread and
    socket, so a single hung backend accumulated connections and made shutdown
    wait on all of them.
    """
    server.state.search_delay = 0.5
    alice._start_prefetch("first wording")
    assert _wait_for(lambda: len(server.state.search_requests()) == 1, timeout=3.0)

    for wording in ("second wording", "third wording", "fourth wording", "fifth"):
        alice._start_prefetch(wording)

    time.sleep(0.2)
    assert len(server.state.search_requests()) == 1
    assert server.state.max_active == 1
    alive = [t for t in threading.enumerate() if t.name == "mem0-prefetch" and t.is_alive()]
    assert len(alive) <= 1

    alice._prefetch_thread.join(timeout=5)
    assert len(server.state.search_requests()) == 1


def test_prefetch_result_is_injected_for_the_matching_turn(server, alice):
    _call(alice, "mem0_add", {"content": "alice prefers window seats"})
    alice.on_turn_start(1, "what seat do I like?")
    injected = alice.prefetch("what seat do I like?")
    assert "alice prefers window seats" in injected
    # Consumed once — a second call for the same turn does not re-inject.
    assert alice._consume_prefetch_result("what seat do I like?") is None
