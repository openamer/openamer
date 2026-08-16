"""Tests for openamer_cli.a2a — identity, envelope, trust, transport, registry.

These exercise real crypto (Ed25519) with no network. They mirror the repo's
pytest style and give durable verification for the A2A feature.
"""
import json
import pathlib
import tempfile
import threading
from http.server import ThreadingHTTPServer

import pytest

from openamer_cli import a2a  # noqa: F401  (package import)
from openamer_cli.a2a import core, trust, transport, registry


# --- identity --------------------------------------------------------------

def test_identity_generate_roundtrip():
    priv, pub = core.generate_identity()
    assert len(priv) == 64 and len(pub) == 64
    ident = core.NodeIdentity(public_key=pub, fingerprint="")
    assert ident.fingerprint == core.pubkey_fingerprint(pub)
    assert len(ident.fingerprint) == 16


def test_identity_store_persists(tmp_path):
    store = core.IdentityStore(tmp_path)
    a = store.ensure_identity()
    b = store.load()
    assert a.public_key == b.public_key
    assert store.exists()


# --- envelope --------------------------------------------------------------

def test_envelope_verify_authentic(tmp_path):
    store_a = core.IdentityStore(tmp_path / "a")
    a = store_a.ensure_identity()
    env = core.Envelope.create(
        private_key=store_a.private_key(), sender=a.fingerprint,
        recipient="peer", kind="ping", payload={"hi": "ok"},
    )
    assert env.verify(a.public_key)


def test_envelope_reject_tamper(tmp_path):
    store_a = core.IdentityStore(tmp_path / "a")
    a = store_a.ensure_identity()
    env = core.Envelope.create(
        private_key=store_a.private_key(), sender=a.fingerprint,
        recipient="peer", kind="ping", payload={"hi": "ok"},
    )
    d = core.Envelope.from_dict(env.to_dict())
    d.payload = {"hi": "MODIFIED"}
    assert d.verify(a.public_key) is False


def test_envelope_reject_future():
    # build a private key directly; deterministic via IdentityStore in temp
    with tempfile.TemporaryDirectory() as td:
        store = core.IdentityStore(pathlib.Path(td))
        ident = store.ensure_identity()
        env = core.Envelope.create(
            private_key=store.private_key(), sender=ident.fingerprint,
            recipient="x", kind="ping", payload={}, ts=9999999999,
        )
        assert env.verify(ident.public_key) is False


# --- trust -----------------------------------------------------------------

def test_trust_grant_flow(tmp_path):
    ts = trust.TrustStore(tmp_path)
    ts.add_peer("fp1", "k" * 64, name="n1")
    assert ts.trusted("fp1") is not None
    g = ts.grant("fp1", "task.sum", budget=0)
    assert g.capability == "task.sum"
    assert ts.has_grant("fp1", "task.sum")
    assert not ts.has_grant("fp1", "task.other")
    assert ts.revoke("fp1", "task.sum") == 1
    assert not ts.has_grant("fp1", "task.sum")


def test_trust_persists(tmp_path):
    tv = trust.TrustStore(tmp_path)
    tv.add_peer("fp", "p" * 64)
    tv2 = trust.TrustStore(tmp_path)
    assert tv2.trusted("fp") is not None


# --- registry --------------------------------------------------------------

def test_registry_announcement_sign_verify(tmp_path):
    store = core.IdentityStore(tmp_path)
    ident = store.ensure_identity()
    ann = registry.Announcement.create(
        private_key=store.private_key(), fingerprint=ident.fingerprint,
        public_key=ident.public_key, name="n", endpoints=["https://x"],
        capabilities=["task.sum"],
    )
    assert ann.verify() is True
    # wrong pin -> reject
    other = core.IdentityStore(tmp_path / "o").ensure_identity()
    assert ann.verify(trusted_pubkey_hex=other.public_key) is False
    # tamper -> reject
    tampered = registry.Announcement.from_dict(ann.to_dict())
    tampered.name = "HACK"
    assert tampered.verify() is False


def test_registry_sign_announcement(tmp_path):
    ann = registry.sign_announcement(home=tmp_path, capabilities=["task.sum"])
    assert ann.verify()
    assert "task.sum" in ann.capabilities


# --- transport -------------------------------------------------------------

def _start_node(tmp_path):
    ts = trust.TrustStore(tmp_path)
    ident_store = core.IdentityStore(tmp_path)
    srv = transport.A2ANodeServer(host="127.0.0.1", port=0, trust=ts,
                                  identity=ident_store,
                                  on_task=lambda env, pd=None: {"got": env.kind})
    return srv, ts, ident_store


def test_transport_e2e_grant_and_reject(tmp_path):
    # two homes: server (A) node, client (B) node
    homeA = pathlib.Path(tmp_path) / "A"; homeB = pathlib.Path(tmp_path) / "B"
    idA = core.IdentityStore(homeA); a = idA.ensure_identity()
    idB = core.IdentityStore(homeB); b = idB.ensure_identity()
    tsA = trust.TrustStore(homeA)
    srv = transport.A2ANodeServer(host="127.0.0.1", port=0, trust=tsA,
                                  identity=idA,
                                  on_task=lambda env, pd=None: {"kind": env.kind})
    th = threading.Thread(target=srv.serve_forever, daemon=True); th.start()
    base = f"http://127.0.0.1:{srv.port}"
    # card
    card = transport.fetch_card(f"{base}/card")
    assert card["agent_card"]["fingerprint"] == a.fingerprint
    # untrusted ping -> 403
    env = core.Envelope.create(private_key=idB.private_key(), sender=b.fingerprint,
                               recipient=a.fingerprint, kind="ping", payload={})
    r = transport.send_message(f"{base}/message", env)
    assert "not trusted" in r.get("error", r.get("http_status") and "403")
    # trust B, no grant -> 403
    tsA.add_peer(b.fingerprint, b.public_key, name="B")
    env2 = core.Envelope.create(private_key=idB.private_key(), sender=b.fingerprint,
                                recipient=a.fingerprint, kind="sum", payload={"a": 2, "b": 3})
    r2 = transport.send_message(f"{base}/message", env2)
    assert "no grant" in r2.get("error", r2.get("http_status") and "403")
    # grant task.sum -> 200
    tsA.grant(b.fingerprint, "task.sum")
    r3 = transport.send_message(f"{base}/message", env2)
    assert r3.get("ok") is True and r3.get("kind") == "sum"
    srv.shutdown()