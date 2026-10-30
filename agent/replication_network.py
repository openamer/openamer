"""Replication over the public internet — per-recipient sealing and a directory.

DIR-01 says replication must work across the internet, not on one machine. The
local module (``agent/replication.py``) proves the artifact and the transport;
this module adds the two things a *network of independent installs* needs:

1. **Per-recipient encryption.** A single shared key would mean every install
   can read every other install's state. Instead each snapshot gets a random
   content key, and that key is wrapped individually for each recipient with
   X25519 + HKDF + AES-GCM. A relay or a third install holds ciphertext it
   cannot open; a recipient can open only what was sealed for it.

2. **A directory to find each other.** Installs come from GitHub, so the network
   needs a rendezvous: a small document that maps ``node_id → {url, public_key}``.
   The protocol is plain HTTP/JSON and can be served by anything (a static file
   on GitHub Pages, a tiny service, a peer). ``DIRECTORY_URL`` or
   ``OPENAMER_REPLICATION_DIRECTORY`` points at it.

**Consent first.** Replicating state to strangers is a decision, not a default:
nothing here runs unless ``OPENAMER_REPLICATION_NETWORK=1`` is set (or the
``replication.network_enabled`` config flag), and a node only ever pushes to
peers it discovered *and* sealed for explicitly.
"""

from __future__ import annotations

import base64
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from agent import node_identity as identity_mod
from agent import replication as rep

PROTOCOL = "openamer-replication-v2"
KDF_INFO = b"openamer-replication-v2-kek"
ENVELOPE_VERSION = 2
MAX_DIRECTORY_BYTES = 4 * 1024 * 1024


# ── consent ────────────────────────────────────────────────────────────────────

def network_enabled() -> bool:
    """Off unless the owner turned it on. A replication network is opt-in."""
    env = os.environ.get("OPENAMER_REPLICATION_NETWORK", "").strip().lower()
    if env in ("1", "true", "yes", "on"):
        return True
    if env in ("0", "false", "no", "off"):
        return False
    try:
        import yaml

        cfg = yaml.safe_load((identity_mod._home() / "config.yaml").read_text(encoding="utf-8"))
    except Exception:
        return False
    node = (cfg or {}).get("replication") if isinstance(cfg, dict) else None
    return bool(isinstance(node, dict) and node.get("network_enabled"))


def directory_url() -> str:
    """Where the rendezvous document lives. Empty means "no directory configured"."""
    value = os.environ.get("OPENAMER_REPLICATION_DIRECTORY", "").strip()
    if value:
        return value.rstrip("/")
    try:
        import yaml

        cfg = yaml.safe_load((identity_mod._home() / "config.yaml").read_text(encoding="utf-8"))
    except Exception:
        return ""
    node = (cfg or {}).get("replication") if isinstance(cfg, dict) else None
    url = node.get("directory_url") if isinstance(node, dict) else ""
    return str(url).rstrip("/") if url else ""


# ── crypto: seal for recipients ────────────────────────────────────────────────

def _x25519():
    from cryptography.hazmat.primitives.asymmetric.x25519 import (
        X25519PrivateKey,
        X25519PublicKey,
    )

    return X25519PrivateKey, X25519PublicKey


def _hkdf(shared: bytes, salt: bytes) -> bytes:
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.hkdf import HKDF

    return HKDF(algorithm=hashes.SHA256(), length=32, salt=salt, info=KDF_INFO).derive(shared)


def _aesgcm(key: bytes):
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    return AESGCM(key)


def seal_for(
    bundle: bytes,
    entries: List[dict],
    recipients: Iterable[dict],
    *,
    sender_id: str = "",
) -> bytes:
    """Encrypt a bundle once, wrap the key for every recipient.

    ``recipients`` items: ``{"node_id": str, "public_key": base64|hex|bytes}``.
    Returns a v2 envelope carrying no plaintext manifest *content* — only names,
    sizes and hashes, which a peer needs to verify what it stores.
    """
    recipient_keys = []
    for item in recipients:
        raw = item["public_key"]
        if isinstance(raw, str):
            raw = identity_mod.decode_public_key(raw)
        recipient_keys.append((item.get("node_id") or identity_mod.node_id_for(raw), raw))
    if not recipient_keys:
        raise rep.ReplicationError("seal_for needs at least one recipient")

    X25519PrivateKey, X25519PublicKey = _x25519()
    content_key = os.urandom(32)
    manifest_sha = rep._manifest_digest(entries)

    header: dict = {
        "format": ENVELOPE_VERSION,
        "protocol": PROTOCOL,
        "cipher": "AES-256-GCM",
        "sender": sender_id,
        "manifest_sha256": manifest_sha.hex(),
        "entries": len(entries),
        "recipients": [],
    }
    # The associated data binds the parts a peer must not be able to rewrite
    # (format, protocol, manifest digest, entry count) to the ciphertext.
    aad_header = json.dumps(
        [header["format"], header["protocol"], header["manifest_sha256"], header["entries"]],
        separators=(",", ":"),
    ).encode("utf-8")

    for node_id, public_raw in recipient_keys:
        ephemeral = X25519PrivateKey.generate()
        from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

        ephemeral_public = ephemeral.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
        shared = ephemeral.exchange(X25519PublicKey.from_public_bytes(public_raw))
        kek = _hkdf(shared, salt=ephemeral_public)
        wrap_nonce = os.urandom(12)
        wrapped = _aesgcm(kek).encrypt(wrap_nonce, content_key, aad_header)
        header["recipients"].append(
            {
                "node_id": node_id,
                "ephemeral_public_key": base64.b64encode(ephemeral_public).decode("ascii"),
                "wrap_nonce": base64.b64encode(wrap_nonce).decode("ascii"),
                "wrapped_key": base64.b64encode(wrapped).decode("ascii"),
            }
        )

    content_nonce = os.urandom(12)
    header["content_nonce"] = base64.b64encode(content_nonce).decode("ascii")
    ciphertext = _aesgcm(content_key).encrypt(content_nonce, bundle, aad_header)

    envelope = {
        "header": header,
        "ciphertext": base64.b64encode(ciphertext).decode("ascii"),
        "manifest": entries,
    }
    return json.dumps(envelope, sort_keys=True, separators=(",", ":")).encode("utf-8")


def open_as(envelope: bytes, node: identity_mod.NodeIdentity) -> tuple[bytes, List[dict], dict]:
    """Open an envelope sealed for ``node``. Refuses if it was sealed for others."""
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

    X25519PrivateKey, X25519PublicKey = _x25519()

    try:
        payload = json.loads(envelope.decode("utf-8"))
        header = payload["header"]
        entries = payload["manifest"]
    except Exception as exc:
        raise rep.IntegrityError(f"malformed envelope: {exc}") from exc

    if header.get("format") != ENVELOPE_VERSION:
        raise rep.ReplicationError(f"not a v2 envelope: {header.get('format')!r}")
    if rep._manifest_digest(entries).hex() != header.get("manifest_sha256"):
        raise rep.IntegrityError("manifest does not match the header digest")

    aad_header = json.dumps(
        [header["format"], header["protocol"], header["manifest_sha256"], header["entries"]],
        separators=(",", ":"),
    ).encode("utf-8")

    private = X25519PrivateKey.from_private_bytes(node.private_key)
    candidates = [r for r in header.get("recipients", []) if r.get("node_id") == node.node_id]
    if not candidates:
        raise rep.IntegrityError(
            f"envelope is not addressed to node {node.node_id} "
            f"(recipients: {[r.get('node_id') for r in header.get('recipients', [])]})"
        )

    content_key = None
    for entry in candidates:
        try:
            ephemeral_public = base64.b64decode(entry["ephemeral_public_key"])
            wrap_nonce = base64.b64decode(entry["wrap_nonce"])
            wrapped = base64.b64decode(entry["wrapped_key"])
            shared = private.exchange(X25519PublicKey.from_public_bytes(ephemeral_public))
            kek = _hkdf(shared, salt=ephemeral_public)
            content_key = _aesgcm(kek).decrypt(wrap_nonce, wrapped, aad_header)
            break
        except Exception:
            continue
    if content_key is None:
        raise rep.IntegrityError("no recipient key could be unwrapped with this node key")

    content_nonce = base64.b64decode(header["content_nonce"])
    try:
        bundle = _aesgcm(content_key).decrypt(content_nonce, base64.b64decode(payload["ciphertext"]), aad_header)
    except Exception as exc:
        raise rep.IntegrityError("content authentication failed") from exc

    return bundle, entries, header


# ── directory protocol ────────────────────────────────────────────────────────

def _http_json(url: str, *, payload: Optional[dict] = None, timeout: float = 20.0) -> dict:
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers, method="POST" if data else "GET")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        blob = response.read(MAX_DIRECTORY_BYTES)
    parsed = json.loads(blob.decode("utf-8"))
    if not isinstance(parsed, dict):
        raise rep.ReplicationError(f"directory returned {type(parsed).__name__}, expected an object")
    return parsed


def announce(advertised_url: str, *, directory: Optional[str] = None, timeout: float = 20.0) -> dict:
    """Publish this node (id, public key, reachable URL) to the directory."""
    base = (directory or directory_url()).rstrip("/")
    if not base:
        raise rep.ReplicationError(
            "no replication directory configured — set OPENAMER_REPLICATION_DIRECTORY "
            "or replication.directory_url in config.yaml"
        )
    if not network_enabled():
        raise rep.ReplicationError(
            "replication network is disabled — set OPENAMER_REPLICATION_NETWORK=1 "
            "(publishing a node address is a deliberate opt-in)"
        )
    identity = identity_mod.load_or_create_identity()
    body = {
        "node_id": identity.node_id,
        "public_key": base64.b64encode(identity.public_key).decode("ascii"),
        "url": advertised_url.rstrip("/"),
        "announced_at": int(time.time()),
        "protocol": PROTOCOL,
    }
    response = _http_json(f"{base}/nodes", payload=body, timeout=timeout)
    return {"announced": body["node_id"], "directory": base, "response": response}


def discover(*, directory: Optional[str] = None, exclude_self: bool = True, timeout: float = 20.0) -> List[dict]:
    """Read the directory and return usable peers (http(s) URLs with a public key)."""
    base = (directory or directory_url()).rstrip("/")
    if not base:
        return []
    try:
        payload = _http_json(f"{base}/nodes", timeout=timeout)
    except (urllib.error.URLError, rep.ReplicationError, json.JSONDecodeError):
        return []

    nodes = payload.get("nodes")
    if not isinstance(nodes, list):
        return []
    me = identity_mod.load_or_create_identity().node_id if exclude_self else None
    usable = []
    for node in nodes:
        if not isinstance(node, dict) or not node.get("url") or not node.get("public_key"):
            continue
        if exclude_self and node.get("node_id") == me:
            continue
        usable.append(node)
    return usable


def announce_and_sync(
    advertised_url: str,
    *,
    directory: Optional[str] = None,
    max_peers: int = 5,
    timeout: float = 20.0,
) -> dict:
    """Announce, discover, seal one snapshot for every peer, deliver it.

    This is the internet-wide counterpart of ``replication.push_to_peers()``: the
    same fast snapshot, but each peer gets its own sealed copy it alone can open.
    """
    if not network_enabled():
        return {"ok": False, "reason": "replication network disabled (opt-in)"}

    announced = announce(advertised_url, directory=directory, timeout=timeout)
    peers = discover(directory=directory, timeout=timeout)[:max_peers]
    if not peers:
        return {"ok": False, "announced": announced["announced"], "peers": 0, "results": []}

    home = identity_mod._home()
    sources = [home / part for part in rep.FAST_SOURCES if (home / part).exists()]
    if not sources:
        return {"ok": False, "reason": "no sources to snapshot", "peers": len(peers), "results": []}

    skipped: List[dict] = []
    bundle, entries = rep.build_bundle(sources, base=home, skipped_out=skipped)
    identity = identity_mod.load_or_create_identity()

    results = []
    for peer in peers:
        try:
            envelope = seal_for(bundle, entries, [peer], sender_id=identity.node_id)
            pushed = rep.push(envelope, peer["url"], timeout=timeout)
            results.append(
                {
                    "peer": peer.get("node_id"),
                    "url": peer["url"],
                    "ok": pushed["status"] == 200,
                    "status": pushed["status"],
                    "envelope_bytes": len(envelope),
                }
            )
        except Exception as exc:  # noqa: BLE001 - one bad peer must not stop the rest
            results.append({"peer": peer.get("node_id"), "url": peer.get("url"), "ok": False, "error": str(exc)[:200]})

    report = {
        "ok": bool(results) and all(item["ok"] for item in results),
        "at": time.time(),
        "announced": announced["announced"],
        "peers": len(peers),
        "files": len(entries),
        "results": results,
    }
    _record(report)
    return report


def _record(report: dict) -> None:
    try:
        path = identity_mod.node_dir() / "network-state.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    except OSError:
        pass


def network_status() -> dict:
    """Everything an operator needs, and the honest "off" when it is off."""
    try:
        state = json.loads((identity_mod.node_dir() / "network-state.json").read_text(encoding="utf-8"))
    except Exception:
        state = {}
    identity = identity_mod.identity_status()
    return {
        "enabled": network_enabled(),
        "directory": directory_url() or None,
        "node_id": identity.get("node_id"),
        "public_key": identity.get("public_key"),
        "last_sync_ok": bool(state.get("ok")),
        "last_sync_peers": state.get("peers", 0),
        "last_sync_age_s": (
            round(time.time() - float(state["at"])) if isinstance(state.get("at"), (int, float)) else None
        ),
    }


# ── a minimal directory server (so a peer or a static host can serve it) ──────

def make_directory_server(store_path: Optional[Path] = None, *, host: str = "127.0.0.1", port: int = 8767):
    """HTTP directory: ``POST /nodes`` registers, ``GET /nodes`` lists.

    Deliberately dumb: it stores what a node claims and returns it. It cannot
    verify a URL — the only claim that matters is the public key, and that is
    verified by the recipient when it opens an envelope.
    """
    import http.server

    store = Path(store_path or (identity_mod.node_dir() / "directory.json"))

    class Handler(http.server.BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def _json(self, code: int, body: dict) -> None:
            blob = json.dumps(body).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(blob)))
            self.end_headers()
            self.wfile.write(blob)

        def _load(self) -> Dict[str, dict]:
            try:
                data = json.loads(store.read_text(encoding="utf-8"))
            except Exception:
                return {}
            return data if isinstance(data, dict) else {}

        def do_POST(self):  # noqa: N802 - http.server API
            if self.path.rstrip("/") != "/nodes":
                self._json(404, {"error": "unknown endpoint"})
                return
            length = int(self.headers.get("Content-Length") or 0)
            if length <= 0 or length > 64 * 1024:
                self._json(400, {"error": "bad length"})
                return
            try:
                body = json.loads(self.rfile.read(length).decode("utf-8"))
            except Exception:
                self._json(400, {"error": "invalid json"})
                return
            if not isinstance(body, dict) or not body.get("node_id") or not body.get("url"):
                self._json(400, {"error": "node_id and url are required"})
                return
            try:
                identity_mod.decode_public_key(str(body.get("public_key", "")))
            except ValueError as exc:
                self._json(400, {"error": str(exc)})
                return
            nodes = self._load()
            nodes[str(body["node_id"])] = body
            store.parent.mkdir(parents=True, exist_ok=True)
            tmp = store.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(nodes, indent=2), encoding="utf-8")
            os.replace(tmp, store)
            self._json(200, {"nodes": len(nodes)})

        def do_GET(self):  # noqa: N802 - http.server API
            if self.path.rstrip("/") != "/nodes":
                self._json(404, {"error": "unknown endpoint"})
                return
            nodes = self._load()
            self._json(200, {"protocol": PROTOCOL, "nodes": list(nodes.values())})

        def log_message(self, *args):
            return

    return http.server.ThreadingHTTPServer((host, port), Handler)
