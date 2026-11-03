"""Browser Use provider contract tests over a REAL loopback HTTP server.

``tests/plugins/browser/test_browser_provider_plugins.py`` only covers plugin
registration and ``is_available()``; nothing exercised the session HTTP
contract, the managed-mode idempotency key, or what happens when the create
response is ambiguous. ``requests`` was never asked to serialize anything.

This module runs a threaded 127.0.0.1 server that implements the Browser Use
v3 shape the provider depends on (``POST /browsers``, ``PATCH /browsers/{id}
{"action": "stop"}``, ``X-Browser-Use-API-Key`` auth). Nothing leaves the
machine, no account is activated and no API bill is produced.
"""

from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

import plugins.browser.browser_use.provider as bu_provider
from plugins.browser.browser_use.provider import BrowserUseBrowserProvider


# ---------------------------------------------------------------------------
# Loopback fixture
# ---------------------------------------------------------------------------


class _BrowserUseState:
    def __init__(self, api_key: str = "loopback-browser-key"):
        self.api_key = api_key
        self.lock = threading.Lock()
        self.requests: list[dict] = []
        self.sessions: dict[str, str] = {}
        self.created_ids: list[str] = []
        self.stop_requests: list[str] = []
        self.create_status = 200
        self.create_payload: dict | None = None
        self.stop_status = 200
        self.create_delay = 0.0
        self.hold_creates_until = 0
        self._create_count = 0
        self._create_gate = threading.Event()
        self._seq = 0

    def requests_for(self, method: str, path_prefix: str = "/") -> list[dict]:
        with self.lock:
            return [
                r for r in self.requests
                if r["method"] == method and r["path"].startswith(path_prefix)
            ]

    def _next_id(self) -> str:
        with self.lock:
            self._seq += 1
            return f"bs-{self._seq}"

    def handle(self, method: str, path: str, body, headers: dict) -> tuple[int, dict]:
        if headers.get("x-browser-use-api-key") != self.api_key:
            return 401, {"detail": "invalid api key"}

        if method == "POST" and path == "/browsers":
            return self._create()

        if method == "PATCH" and path.startswith("/browsers/"):
            return self._patch(path.rsplit("/", 1)[-1], body or {})

        return 404, {"detail": "not found"}

    def _create(self) -> tuple[int, dict]:
        with self.lock:
            self._create_count += 1
            should_hold = self.hold_creates_until and self._create_count >= self.hold_creates_until
        if should_hold:
            # Rendezvous: release only once every expected caller has arrived,
            # so concurrent creators are genuinely in flight together.
            self._create_gate.set()
        if self.hold_creates_until:
            self._create_gate.wait(timeout=5)
        if self.create_delay:
            time.sleep(self.create_delay)

        if self.create_status != 200:
            return self.create_status, self.create_payload or {"detail": "error"}

        session_id = self._next_id()
        with self.lock:
            self.sessions[session_id] = "running"
            self.created_ids.append(session_id)
        payload = self.create_payload
        if payload is not None:
            return 200, payload
        return 200, {"id": session_id, "cdpUrl": f"http://127.0.0.1:9/cdp/{session_id}"}

    def _patch(self, session_id: str, body: dict) -> tuple[int, dict]:
        if body.get("action") != "stop":
            return 400, {"detail": "unsupported action"}
        if self.stop_status != 200:
            return self.stop_status, {"detail": "stop failed"}
        with self.lock:
            if session_id not in self.sessions:
                return 404, {"detail": "session not found"}
            self.sessions[session_id] = "stopped"
            self.stop_requests.append(session_id)
        return 200, {"id": session_id, "status": "stopped"}


class _BrowserUseHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "browser-use-loopback/1"

    def log_message(self, *args):
        pass

    def do_POST(self):  # noqa: N802
        self._dispatch("POST")

    def do_PATCH(self):  # noqa: N802
        self._dispatch("PATCH")

    def _dispatch(self, method: str) -> None:
        state: _BrowserUseState = self.server.state
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b""
        try:
            body = json.loads(raw) if raw else None
        except ValueError:
            body = {"_raw": raw.decode("utf-8", "replace")}
        headers = {k.lower(): v for k, v in self.headers.items()}
        with state.lock:
            state.requests.append(
                {"method": method, "path": self.path, "headers": headers, "body": body}
            )
        status, payload = state.handle(method, self.path, body, headers)
        encoded = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


class BrowserUseLoopbackServer:
    def __init__(self):
        self.state = _BrowserUseState()
        self._httpd = ThreadingHTTPServer(("127.0.0.1", 0), _BrowserUseHandler)
        self._httpd.state = self.state  # type: ignore[attr-defined]
        self._httpd.daemon_threads = True
        self._thread = threading.Thread(
            target=self._httpd.serve_forever, name="browser-use-loopback", daemon=True
        )

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self._httpd.server_address[1]}"

    def start(self) -> "BrowserUseLoopbackServer":
        self._thread.start()
        return self

    def stop(self) -> None:
        self._httpd.shutdown()
        self._httpd.server_close()
        self._thread.join(timeout=5)


@pytest.fixture
def server():
    srv = BrowserUseLoopbackServer().start()
    try:
        yield srv
    finally:
        srv.stop()


@pytest.fixture(autouse=True)
def _clean_pending_keys():
    bu_provider._pending_create_keys.clear()
    yield
    bu_provider._pending_create_keys.clear()


@pytest.fixture
def provider(server, monkeypatch):
    monkeypatch.setenv("BROWSER_USE_API_KEY", server.state.api_key)
    monkeypatch.delenv("TOOL_GATEWAY_DOMAIN", raising=False)
    monkeypatch.delenv("TOOL_GATEWAY_USER_TOKEN", raising=False)
    monkeypatch.setattr(bu_provider, "_BASE_URL", server.base_url)
    return BrowserUseBrowserProvider()


def _managed(provider, monkeypatch, server) -> None:
    """Force the managed-gateway path without touching auth/OAuth machinery."""
    monkeypatch.setattr(
        type(provider),
        "_get_config",
        lambda self: {
            "api_key": server.state.api_key,
            "base_url": server.base_url,
            "managed_mode": True,
        },
    )


# ---------------------------------------------------------------------------
# Session creation / serialization
# ---------------------------------------------------------------------------


def test_create_session_round_trip_over_the_wire(server, provider):
    session = provider.create_session("task-1")

    assert session["bb_session_id"] == "bs-1"
    assert session["cdp_url"] == "http://127.0.0.1:9/cdp/bs-1"
    assert session["session_name"].startswith("openamer_task-1_")

    req = server.state.requests_for("POST", "/browsers")[-1]
    assert req["headers"]["x-browser-use-api-key"] == server.state.api_key
    assert "authorizaton" not in req["headers"]
    assert "authorization" not in req["headers"]
    # Direct mode sends no billing payload.
    assert req["body"] == {}


def test_managed_mode_sends_the_bounded_session_payload_and_key(server, provider, monkeypatch):
    _managed(provider, monkeypatch, server)
    provider.create_session("task-2")

    req = server.state.requests_for("POST", "/browsers")[-1]
    assert req["body"] == {
        "timeout": bu_provider._DEFAULT_MANAGED_TIMEOUT_MINUTES,
        "proxyCountryCode": bu_provider._DEFAULT_MANAGED_PROXY_COUNTRY_CODE,
    }
    assert req["headers"]["x-idempotency-key"].startswith("browser-use-session-create:")
    # Success clears the pending key: the next create starts a fresh session.
    assert bu_provider._pending_create_keys == {}


# ---------------------------------------------------------------------------
# Ambiguous create responses (session-creation ambiguity)
# ---------------------------------------------------------------------------


def test_create_response_without_id_is_a_typed_error_not_a_keyerror(server, provider):
    server.state.create_payload = {"cdpUrl": "http://127.0.0.1:9/cdp/anon"}

    with pytest.raises(RuntimeError) as excinfo:
        provider.create_session("task-3")

    assert "ambiguous" in str(excinfo.value)
    assert len(server.state.requests_for("POST", "/browsers")) == 1


def test_create_response_without_cdp_url_is_stopped_instead_of_leaked(server, provider):
    """A session we cannot attach to must not be left running (and billing)."""
    server.state.create_payload = {"id": "bs-orphan"}

    with pytest.raises(RuntimeError) as excinfo:
        provider.create_session("task-4")

    assert "no CDP URL" in str(excinfo.value)
    stop = server.state.requests_for("PATCH", "/browsers/bs-orphan")
    assert len(stop) == 1
    assert (stop[0]["body"] or {}).get("action") == "stop"


def test_create_response_that_is_not_json_is_reported(server, provider):
    server.state.create_payload = None
    # A 200 with an HTML/plain body: response.json() raises ValueError.
    server.state.create_status = 200
    original = _BrowserUseHandler._dispatch

    def _plain(self, method):  # pragma: no cover - tiny inline override
        length = int(self.headers.get("Content-Length") or 0)
        self.rfile.read(length)
        payload = b"<html>gateway</html>"
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    try:
        _BrowserUseHandler._dispatch = _plain
        with pytest.raises(RuntimeError) as excinfo:
            provider.create_session("task-5")
        assert "not JSON" in str(excinfo.value)
    finally:
        _BrowserUseHandler._dispatch = original


# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------


def test_close_session_sends_stop_and_maps_outcomes(server, provider):
    session = provider.create_session("task-6")
    assert provider.close_session(session["bb_session_id"]) is True
    assert session["bb_session_id"] in server.state.stop_requests

    server.state.stop_status = 200
    assert provider.close_session("bs-does-not-exist") is False  # 404 -> False, no raise


def test_close_session_without_credentials_returns_false(server, monkeypatch):
    monkeypatch.delenv("BROWSER_USE_API_KEY", raising=False)
    p = BrowserUseBrowserProvider()
    assert p.close_session("bs-1") is False


def test_emergency_cleanup_never_raises_on_server_error(server, provider):
    session = provider.create_session("task-7")
    server.state.stop_status = 500
    provider.emergency_cleanup(session["bb_session_id"])  # must not raise
    assert server.state.sessions[session["bb_session_id"]] == "running"


# ---------------------------------------------------------------------------
# Managed-mode idempotency across retries
# ---------------------------------------------------------------------------


def test_managed_create_retry_reuses_the_key_and_clears_it_on_success(server, provider, monkeypatch):
    _managed(provider, monkeypatch, server)
    server.state.create_status = 409
    server.state.create_payload = {"error": {"message": "session creation already in progress"}}

    for _ in range(2):
        with pytest.raises(RuntimeError):
            provider.create_session("task-8")

    keys = [r["headers"].get("x-idempotency-key") for r in server.state.requests_for("POST", "/browsers")]
    assert keys[0] and keys[0] == keys[1]
    assert "task-8" in bu_provider._pending_create_keys

    server.state.create_status = 200
    server.state.create_payload = None
    provider.create_session("task-8")
    provider.create_session("task-8")

    keys = [r["headers"].get("x-idempotency-key") for r in server.state.requests_for("POST", "/browsers")]
    assert keys[-1] != keys[-2]


# ---------------------------------------------------------------------------
# The browser_tool session registry must not orphan the losing session
# ---------------------------------------------------------------------------


def test_concurrent_session_creation_closes_the_redundant_cloud_session(server, provider, monkeypatch):
    """Two threads racing for one task must not leave a paid browser running.

    ``_get_session_info`` creates the provider session outside ``_cleanup_lock``
    (network call), then re-checks the registry. The loser used to return the
    winner's entry and simply drop its own session, which stayed up until the
    provider's timeout.
    """
    from tools import browser_tool

    server.state.hold_creates_until = 2
    monkeypatch.setattr(browser_tool, "_get_cloud_provider", lambda: provider)
    monkeypatch.setattr(browser_tool, "_get_cdp_override", lambda: None)
    monkeypatch.setattr(browser_tool, "_ensure_cdp_supervisor", lambda task_id: None)
    monkeypatch.setattr(browser_tool, "_start_browser_cleanup_thread", lambda: None)
    browser_tool._active_sessions.clear()
    try:
        results, errors = [], []

        def worker():
            try:
                results.append(browser_tool._get_session_info("task-race"))
            except Exception as exc:  # pragma: no cover - failure path
                errors.append(exc)

        threads = [threading.Thread(target=worker, name=f"racer-{i}") for i in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert not errors, errors
        assert len(results) == 2
        assert len(server.state.created_ids) == 2, "both threads should have created a session"

        winner_id = browser_tool._active_sessions["task-race"]["bb_session_id"]
        assert {r["bb_session_id"] for r in results} == {winner_id}

        loser_ids = [sid for sid in server.state.created_ids if sid != winner_id]
        assert len(loser_ids) == 1
        assert server.state.stop_requests == loser_ids, (
            f"losing session(s) {loser_ids} were never stopped "
            f"(stopped: {server.state.stop_requests})"
        )
        assert server.state.sessions[winner_id] == "running"
    finally:
        browser_tool._active_sessions.clear()
