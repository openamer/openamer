"""openamer_cli.a2a.transport — real HTTP transport for A2A.

Implements the two endpoints a peer needs:
    GET  /card        -> AgentCard (identity, name, capabilities)
    POST /message     -> receive + verify a signed Envelope; grants a task

Plus a client (`send_message`) that signs and POSTs an Envelope to a peer.
Uses only the Python standard library (http.server) so a node needs no extra
runtime dependency. This is Phase 1: verified, signed, node-to-node exchange.

Security model:
  - Every incoming message must carry a valid Ed25519 signature from a peer the
    operator has `trust add`ed.
  - Execution of a task additionally requires a capability the peer has been
    `grant`ed. Without a grant we return 403 and never run anything.
  - Replay protection via the envelope timestamp (5 min window).
"""
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable, Optional
from urllib import request, error

from openamer_cli.a2a.core import IdentityStore, Envelope, public_key_from_hex
from openamer_cli.a2a.trust import TrustStore


class A2AHandler(BaseHTTPRequestHandler):
    # injected by the server wrapper
    trust: "TrustStore" = None
    identity: "IdentityStore" = None
    server_name: str = "OpenAmer"

    # on_task is stored WITHOUT being a class attribute bound to `self`, because
    # `self.on_task(...)` would bind the handler instance as the first arg.
    # We keep it in a module-level dict and call it plainly below.
    _shared_state: dict = {"on_task": None}

    # ---- helpers ----------------------------------------------------------

    def _json(self, code: int, data: dict) -> None:
        body = json.dumps(data).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):  # quieter
        return

    # ---- routes -----------------------------------------------------------

    def do_GET(self):
        if self.path.rstrip("/").endswith("/card"):
            return self._handle_card()
        self._json(404, {"error": "not found"})

    def do_POST(self):
        if self.path.rstrip("/").endswith("/message"):
            return self._handle_message()
        self._json(404, {"error": "not found"})

    def _handle_card(self):
        ident = self.identity.ensure_identity()
        caps = self._advertised_capabilities()
        self._json(200, {
            "agent_card": {
                "name": self.server_name,
                "identity": f"{ident.fingerprint}@openamer",
                "fingerprint": ident.fingerprint,
                "public_key": ident.public_key,
            },
            "capabilities": caps,
        })

    def _advertised_capabilities(self):
        """Stable, non-sensitive capabilities this node advertises on /card
        for peer discovery. (We don't expose the per-peer grant list to
        anonymous callers.)"""
        return ["task.ping", "task.card"]

    def _handle_message(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length)
            data = json.loads(raw.decode("utf-8"))
        except Exception as e:
            return self._json(400, {"ok": False, "error": f"bad request: {e}"})

        if data.get("type") != "a2a.message":
            return self._json(400, {"ok": False, "error": "expected type=a2a.message"})
        env = Envelope.from_dict(data.get("envelope", {}))

        # 1. Is the sender trusted?
        peer = self.trust.trusted(env.sender)
        if not peer:
            return self._json(403, {"ok": False, "error": "sender not trusted"})

        # 2. Signature valid + fresh?
        if not env.verify(peer.public_key):
            return self._json(403, {"ok": False, "error": "invalid signature or stale"})

        # 3. (for tasks) does the peer hold a grant for the kind's capability?
        cap = f"task.{env.kind}"
        if env.kind not in ("ping", "card"):
            if not self.trust.has_grant(env.sender, cap):
                return self._json(403, {"ok": False, "error": f"no grant for {cap}"})

        result = {}
        on_task = A2AHandler._shared_state.get("on_task")
        if on_task and env.kind != "ping":
            try:
                # Pass (envelope, peer_dict); callbacks that take extra kwargs
                # via ** obey a tolerant contract so handlers aren't brittle.
                peer_dict = {}
                if peer is not None:
                    peer_dict = {"fingerprint": peer.fingerprint,
                                 "name": getattr(peer, "name", "")}
                result = on_task(env, peer_dict)
            except Exception as e:  # surface, don't crash the connection
                result = {"error": str(e)}
        return self._json(200, {"ok": True, "kind": env.kind, "sender": env.sender,
                                "result": result})


class A2ANodeServer:
    def __init__(self, host: str = "127.0.0.1", port: int = 0,
                 trust: Optional[TrustStore] = None,
                 identity: Optional[IdentityStore] = None,
                 server_name: str = "OpenAmer",
                 on_task: Optional[Callable] = None):
        self.trust = trust or TrustStore()
        self.identity = identity or IdentityStore()
        self.server_name = server_name
        A2AHandler.trust = self.trust
        A2AHandler.identity = self.identity
        A2AHandler._shared_state["on_task"] = on_task
        A2AHandler.server_name = server_name
        self._httpd = ThreadingHTTPServer((host, port), A2AHandler)
        self.port = self._httpd.server_address[1]

    def serve_forever(self) -> None:
        print(f"A2A node listening on http://127.0.0.1:{self.port}/card")
        print(f"  identity : {self.identity.ensure_identity().fingerprint}@openamer")
        self._httpd.serve_forever()

    def shutdown(self) -> None:
        self._httpd.shutdown()


# --- client ---------------------------------------------------------------

def send_message(url: str, env: Envelope, timeout: float = 30.0) -> dict:
    """POST a signed envelope to a peer's /message endpoint."""
    payload = json.dumps({"type": "a2a.message", "envelope": env.to_dict()}).encode()
    req = request.Request(url, data=payload,
                          headers={"Content-Type": "application/json"})
    try:
        with request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except error.HTTPError as e:
        # 4xx from the peer carries a JSON body we must surface (e.g. 403).
        body = e.read().decode("utf-8", "replace")
        try:
            data = json.loads(body)
        except Exception:
            data = {"ok": False, "error": body, "http_status": e.code}
        data["http_status"] = e.code
        return data


def fetch_card(url: str, timeout: float = 20.0) -> dict:
    req = request.Request(url, method="GET")
    try:
        with request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        try:
            data = json.loads(body)
        except Exception:
            data = {"error": body}
        data["http_status"] = e.code
        return data


def ask(identity: IdentityStore, trust: TrustStore, peer_url: str,
        question: str, kind: str = "ask", timeout: float = 60.0) -> dict:
    """Ask a trusted remote node a question.

    Flow (all verified): fetch the peer's /card -> confirm its fingerprint is a
    peer we `trust add`ed -> build a signed Envelope carrying the question ->
    POST to the peer's /message -> return its answer.

    The semantic "switchable" question text is wrapped as a task the peer runs
    under a capability grant. This is Node-to-Node A2A routing: a node can ask
    a peer it trusts, and the peer's own operator must have granted the relevant
    capability.
    """
    # 1) discover peer
    card = fetch_card(peer_url.rstrip("/") + "/card")
    if not card or "agent_card" not in card:
        return {"ok": False, "error": "could not fetch peer card"}
    agent = card["agent_card"]
    remote_fp = agent.get("fingerprint", "")
    remote_pub = agent.get("public_key", "")
    # 2) is this peer trusted (by fingerprint)?
    peer = trust.trusted(remote_fp)
    if not peer:
        return {"ok": False, "error": f"peer {remote_fp} is not trusted"}
    # 3) build signed envelope from OUR identity
    local = identity.ensure_identity()
    env = Envelope.create(
        private_key=identity.private_key(),
        sender=local.fingerprint,
        recipient=remote_fp,
        kind=kind,
        payload={"question": question},
    )
    # 4) send
    return send_message(peer_url.rstrip("/") + "/message", env, timeout=timeout)


def ask_many(identity, trust, peer_urls, question, kind: str = "ask",
             timeout: float = 60.0, concurrency: int = 3) -> dict:
    """Ask several trusted peers the same question and collect their answers.

    This is collective-swarm routing: the node fans the question out to every
    peer URL it trusts, then bundles all verified answers into one result so
    the agent can reason over the swarm's view (majority, corroboration, or the
    best single answer). Non-trusted / unresponsive peers are reported, never
    fatal.

    Returns: {ok, total, answered, answers: [ {peer, ok, result|error}, ... ]}
    """
    import threading
    from queue import Queue
    results = []
    lock = threading.Lock()

    def worker(url):
        try:
            r = ask(identity, trust, url, question, kind=kind, timeout=timeout)
            with lock:
                results.append({"peer": url, "ok": bool(r.get("ok")), "result": r.get("result") or r.get("error") or r})
        except Exception as e:  # noqa: BLE001 - report any peer failure
            with lock:
                results.append({"peer": url, "ok": False, "result": f"error: {e}"})

    threads = []
    # bounded concurrency to be polite to peers
    idx = 0
    while idx < len(peer_urls):
        batch = peer_urls[idx:idx+concurrency]
        for u in batch:
            th = threading.Thread(target=worker, args=(u,), daemon=True)
            th.start(); threads.append(th)
        for th in threads[-concurrency:]: th.join(max(timeout, 5))  # wait batch
        idx += concurrency
    for th in threads: th.join()

    answered = [r for r in results if r.get("ok")]
    return {
        "ok": len(answered) > 0,
        "total": len(results),
        "answered": len(answered),
        "answers": results,
    }
