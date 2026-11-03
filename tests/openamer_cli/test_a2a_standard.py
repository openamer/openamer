"""Loopback HTTP tests for the standard A2A v1.0 adapter.

These exercise real sockets (``ThreadingHTTPServer`` on 127.0.0.1) against
fixtures pinned to A2A v1.0.1 — no mocks around the transport, and no network
access beyond loopback.
"""
from __future__ import annotations

import json
import pathlib
import threading
import urllib.error
import urllib.request

import pytest

from openamer_cli.a2a import core, standard, transport

FIXTURES = pathlib.Path(__file__).resolve().parents[1] / "fixtures" / "a2a" / "v1.0"
TOKEN = "test-bearer-token"


def _fixture(name: str) -> dict:
    with open(FIXTURES / name, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def protocol() -> dict:
    return _fixture("protocol.json")


class _Node:
    def __init__(self, tmp_path, capabilities=("task.ask",), token=TOKEN, handler=None):
        self.calls = []
        self.answer = lambda req: {"answer": "echo:" + req.payload["question"]}

        def on_task(request, peer):
            self.calls.append(request)
            return (handler or self.answer)(request)

        config = standard.StandardA2AConfig(
            bearer_token=token,
            agent_name="OpenAmer Test Node",
            capabilities=capabilities,
        )
        self.service = standard.StandardA2AService(config, on_task=on_task)
        self.server = transport.A2ANodeServer(
            host="127.0.0.1", port=0, standard=self.service, on_task=on_task,
        )
        self.base = f"http://127.0.0.1:{self.server.port}"
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def close(self):
        self.server.shutdown()


@pytest.fixture
def node(tmp_path):
    n = _Node(tmp_path)
    yield n
    n.close()


def _http(method: str, url: str, *, body=None, headers=None, raw: bytes | None = None):
    data = raw if raw is not None else (
        json.dumps(body).encode("utf-8") if body is not None else None
    )
    req = urllib.request.Request(url, data=data, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8")), dict(resp.headers)
    except urllib.error.HTTPError as exc:
        payload = exc.read().decode("utf-8")
        return exc.code, (json.loads(payload) if payload else {}), dict(exc.headers)


def _rpc(node, body, *, token=TOKEN, version="1.0", path="/a2a"):
    headers = {"Content-Type": "application/json"}
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"
    if version is not None:
        headers["A2A-Version"] = version
    return _http("POST", node.base + path, body=body, headers=headers)


# --- discovery -------------------------------------------------------------


@pytest.mark.parametrize("path", ["/.well-known/agent-card.json", "/.well-known/agent.json"])
def test_agent_card_matches_v1_0_fixture(node, path, protocol):
    status, card, headers = _http("GET", node.base + path)
    assert status == 200
    assert headers.get("Content-Type", "").startswith("application/json")

    expected = _fixture("agent-card.json")
    expected = json.loads(json.dumps(expected).replace("<BASE_URL>", node.base))
    assert card == expected

    # Contract facts the fixture pins to the spec, not to this implementation.
    assert card["supportedInterfaces"][0]["protocolVersion"] == protocol["protocolVersion"]
    assert card["supportedInterfaces"][0]["protocolBinding"] == "JSONRPC"
    # Nothing beyond the implemented subset may be advertised.
    assert card["capabilities"]["streaming"] is False
    assert card["capabilities"]["pushNotifications"] is False
    assert "bearer" in card["securitySchemes"]


def test_standard_routes_absent_when_not_configured(tmp_path):
    server = transport.A2ANodeServer(host="127.0.0.1", port=0)
    th = threading.Thread(target=server.serve_forever, daemon=True)
    th.start()
    try:
        base = f"http://127.0.0.1:{server.port}"
        status, _, _ = _http("GET", base + "/.well-known/agent-card.json")
        assert status == 404
        status, body, _ = _rpc(
            type("N", (), {"base": base})(), {"jsonrpc": "2.0", "id": 1, "method": "SendMessage"}
        )
        assert status == 404
    finally:
        server.shutdown()


# --- SendMessage / GetTask -------------------------------------------------


def test_send_message_authenticated_roundtrip(node, protocol):
    request = _fixture("send-message.request.json")
    status, body, _ = _rpc(node, request)

    assert status == 200, body
    assert body["jsonrpc"] == "2.0"
    assert body["id"] == request["id"]

    task = body["result"]["task"]
    assert task["status"]["state"] == protocol["taskStates"]["completed"]
    assert task["contextId"]
    assert task["history"][0]["role"] == protocol["roles"]["user"]
    assert task["history"][1]["role"] == protocol["roles"]["agent"]
    assert task["artifacts"][0]["parts"][0]["text"] == "echo:what is 2+2?"
    # The handler received the same payload the signed channel would deliver.
    assert node.calls[0].kind == "ask"
    assert node.calls[0].payload["question"] == "what is 2+2?"

    # GetTask returns the stored task, and honours historyLength.
    get_req = {"jsonrpc": "2.0", "id": "g1", "method": "GetTask",
               "params": {"id": task["id"], "historyLength": 1}}
    status, fetched, _ = _rpc(node, get_req)
    assert status == 200
    assert fetched["result"]["id"] == task["id"]
    assert len(fetched["result"]["history"]) == 1


def test_legacy_slash_method_aliases_are_accepted(node):
    request = _fixture("send-message.request.json")
    request = dict(request, method="message/send")
    status, body, _ = _rpc(node, request)
    assert status == 200
    assert body["result"]["task"]["status"]["state"] == standard.TASK_STATE_COMPLETED


def test_get_task_unknown_returns_task_not_found(node, protocol):
    status, body, _ = _rpc(node, {
        "jsonrpc": "2.0", "id": "g2", "method": "GetTask",
        "params": {"id": "task-does-not-exist"},
    })
    assert status == 404
    assert body["error"]["code"] == protocol["errorCodes"]["taskNotFound"]


# --- authorization ---------------------------------------------------------


@pytest.mark.parametrize("headers", [
    {},
    {"Authorization": "Bearer wrong-token"},
    {"Authorization": "Basic dGVzdDp0ZXN0"},
    {"Authorization": "Bearer"},
])
def test_unauthorized_requests_rejected_without_side_effects(node, headers):
    request = _fixture("send-message.request.json")
    status, body, resp_headers = _http(
        "POST", node.base + "/a2a",
        body=request, headers={**headers, "Content-Type": "application/json",
                               "A2A-Version": "1.0"},
    )
    assert status == 401
    assert body["error"]["code"] == standard.ERR_UNAUTHORIZED
    assert resp_headers.get("WWW-Authenticate", "").lower().startswith("bearer")
    assert node.calls == [], "handler must never run for an unauthenticated caller"


def test_capability_grant_required(tmp_path):
    n = _Node(tmp_path, capabilities=())
    try:
        status, body, _ = _rpc(n, _fixture("send-message.request.json"))
        assert status == 403
        assert body["error"]["code"] == standard.ERR_UNAUTHORIZED
        assert body["error"]["data"]["requiredCapability"] == "task.ask"
        assert n.calls == [], "no task may run without the task.ask capability"
    finally:
        n.close()


# --- version negotiation ---------------------------------------------------


@pytest.mark.parametrize("version", ["0.3", "0.2", "2.0", "1.0.1"])
def test_unsupported_version_rejected_explicitly(node, version, protocol):
    status, body, _ = _rpc(node, _fixture("send-message.request.json"), version=version)
    assert status == 400
    assert body["error"]["code"] == protocol["errorCodes"]["versionNotSupported"]
    assert "supportedVersions" in body["error"]["data"]
    assert body["error"]["data"]["supportedVersions"] == ["1.0", "1.0.0"]
    assert node.calls == []


def test_missing_version_header_is_treated_as_pre_1_0(node):
    status, body, _ = _rpc(node, _fixture("send-message.request.json"), version=None)
    assert status == 400
    assert body["error"]["code"] == standard.ERR_VERSION_NOT_SUPPORTED
    assert "0.3" in body["error"]["message"]
    assert node.calls == []


# --- protocol errors -------------------------------------------------------


def test_unknown_method_is_method_not_found(node, protocol):
    status, body, _ = _rpc(node, {"jsonrpc": "2.0", "id": 7,
                                  "method": "SendStreamingMessage", "params": {}})
    assert status == 200
    assert body["error"]["code"] == protocol["errorCodes"]["methodNotFound"]


@pytest.mark.parametrize("raw", [b"{not json", b"", b"[]"])
def test_malformed_bodies_do_not_crash(node, raw):
    status, body, _ = _http(
        "POST", node.base + "/a2a", raw=raw,
        headers={"Authorization": f"Bearer {TOKEN}", "A2A-Version": "1.0"},
    )
    assert status == 400
    assert body["error"]["code"] in (standard.ERR_PARSE, standard.ERR_INVALID_REQUEST)
    assert node.calls == []


def test_missing_text_part_is_invalid_params(node):
    status, body, _ = _rpc(node, {
        "jsonrpc": "2.0", "id": "m1", "method": "SendMessage",
        "params": {"message": {"messageId": "x", "role": "ROLE_USER", "parts": []}},
    })
    assert status == 200
    assert body["error"]["code"] == standard.ERR_INVALID_PARAMS


# --- compatibility with the existing custom routes ------------------------


def test_custom_signed_routes_still_work_alongside_standard(node, tmp_path):
    # /card keeps its original, non-standard shape.
    status, card, _ = _http("GET", node.base + "/card")
    assert status == 200
    assert "agent_card" in card
    assert card["agent_card"]["fingerprint"]

    # /message still enforces the trust store (unsigned/unknown sender -> 403).
    sender = core.IdentityStore(tmp_path / "sender").ensure_identity()
    env = core.Envelope.create(
        private_key=core.IdentityStore(tmp_path / "sender").private_key(),
        sender=sender.fingerprint, recipient="x", kind="ping", payload={},
    )
    status, body, _ = _http(
        "POST", node.base + "/message",
        body={"type": "a2a.message", "envelope": env.to_dict()},
        headers={"Content-Type": "application/json"},
    )
    assert status == 403
    assert body["ok"] is False
