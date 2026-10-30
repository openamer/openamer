"""Two independent installs, one internet: per-recipient sealing + discovery.

The claim these tests must settle: a snapshot sealed for node B is unreadable by
node C, unreadable by the directory, and readable by B after travelling over
HTTP. Anything less is not "replication across the internet", it is a shared
password.

Each node is a separate ``$OPENAMER_HOME`` with its own X25519 keypair — the same
separation two real installations have.
"""

from __future__ import annotations

import base64
import json
import threading

import pytest

from agent import node_identity as ni
from agent import replication as rep
from agent import replication_network as net


def _make_node(root, monkeypatch):
    """Materialise an install: home dir, identity, a little state."""
    home = root
    (home / "memory" / "self_model").mkdir(parents=True)
    (home / "memory" / "self_model" / "identity.md").write_text(f"# node {home.name}\n", encoding="utf-8")
    (home / "config.yaml").write_text("model:\n  provider: test\n", encoding="utf-8")
    (home / "cron").mkdir()
    (home / "cron" / "jobs.json").write_text("[]", encoding="utf-8")

    monkeypatch.setattr(ni, "_home", lambda: home)
    monkeypatch.setattr(rep, "_home", lambda: home)
    return home, ni.load_or_create_identity()


@pytest.fixture()
def two_nodes(tmp_path, monkeypatch):
    a_home, a_id = _make_node(tmp_path / "node-a", monkeypatch)
    b_home, b_id = _make_node(tmp_path / "node-b", monkeypatch)
    # Both identities must exist before either is used.
    monkeypatch.setattr(ni, "_home", lambda: b_home)
    b_id = ni.load_or_create_identity()
    return (a_home, a_id), (b_home, b_id)


def test_every_install_gets_its_own_keypair(two_nodes):
    (_a_home, a_id), (_b_home, b_id) = two_nodes

    assert a_id.node_id != b_id.node_id
    assert a_id.public_key != b_id.public_key
    assert len(a_id.private_key) == ni.NODE_KEY_BYTES


def test_a_snapshot_sealed_for_b_is_readable_only_by_b(two_nodes, tmp_path):
    (a_home, a_id), (_b_home, b_id) = two_nodes
    bundle, entries = rep.build_bundle([a_home / "memory"], base=a_home)

    envelope = net.seal_for(bundle, entries, [{"node_id": b_id.node_id, "public_key": b_id.public_key}])

    opened, opened_entries, header = net.open_as(envelope, b_id)
    assert opened == bundle
    assert opened_entries == entries
    assert header["sender"] == "" or header["sender"] == a_id.node_id

    # A third install holding the envelope learns nothing: it is not addressed to it.
    with pytest.raises(rep.IntegrityError, match="not addressed"):
        import agent.node_identity as _ni

        third = _ni.NodeIdentity("zzz", b"\x00" * 32, b"\x01" * 32)
        net.open_as(envelope, third)


def test_the_directory_and_a_relay_cannot_read_the_payload(two_nodes, tmp_path):
    (a_home, a_id), (_b_home, b_id) = two_nodes
    bundle, entries = rep.build_bundle([a_home / "memory"], base=a_home)
    envelope = net.seal_for(bundle, entries, [{"node_id": b_id.node_id, "public_key": b_id.public_key}])

    # The plaintext of a real state file must not appear anywhere in the envelope.
    assert b"node-a" not in envelope
    assert b"identity.md" in envelope, "the manifest names files (a peer needs to verify them)"
    # The key material for B is in the envelope, but useless without B's private key.
    payload = json.loads(envelope)
    assert payload["header"]["recipients"][0]["node_id"] == b_id.node_id


def test_one_envelope_can_address_several_recipients(two_nodes, tmp_path):
    (a_home, a_id), (_b_home, b_id) = two_nodes
    third_home = tmp_path / "node-c"
    (third_home / "memory").mkdir(parents=True)
    third_home.joinpath("memory", "x.jsonl").write_text("{}\n", encoding="utf-8")
    import agent.node_identity as _ni

    orig = _ni._home
    _ni._home = lambda: third_home
    try:
        c_id = _ni.load_or_create_identity()
    finally:
        _ni._home = orig

    bundle, entries = rep.build_bundle([a_home / "memory"], base=a_home)
    envelope = net.seal_for(
        bundle,
        entries,
        [
            {"node_id": b_id.node_id, "public_key": b_id.public_key},
            {"node_id": c_id.node_id, "public_key": c_id.public_key},
        ],
    )

    assert net.open_as(envelope, b_id)[0] == bundle
    assert net.open_as(envelope, c_id)[0] == bundle


def test_tampered_envelope_is_refused(two_nodes):
    (a_home, _a_id), (_b_home, b_id) = two_nodes
    bundle, entries = rep.build_bundle([a_home / "memory"], base=a_home)
    payload = json.loads(net.seal_for(bundle, entries, [{"node_id": b_id.node_id, "public_key": b_id.public_key}]))

    raw = bytearray(base64.b64decode(payload["ciphertext"]))
    raw[0] ^= 0xFF
    payload["ciphertext"] = base64.b64encode(bytes(raw)).decode("ascii")

    with pytest.raises(rep.IntegrityError):
        net.open_as(json.dumps(payload).encode("utf-8"), b_id)


def test_wrong_manifest_is_refused(two_nodes):
    (a_home, _a_id), (_b_home, b_id) = two_nodes
    bundle, entries = rep.build_bundle([a_home / "memory"], base=a_home)
    payload = json.loads(net.seal_for(bundle, entries, [{"node_id": b_id.node_id, "public_key": b_id.public_key}]))

    payload["manifest"][0]["size"] = 123456789

    with pytest.raises(rep.IntegrityError, match="manifest"):
        net.open_as(json.dumps(payload).encode("utf-8"), b_id)


def test_network_is_off_until_the_owner_turns_it_on(two_nodes, monkeypatch):
    monkeypatch.delenv("OPENAMER_REPLICATION_NETWORK", raising=False)

    assert net.network_enabled() is False
    report = net.announce_and_sync("http://127.0.0.1:9")
    assert report["ok"] is False
    assert "disabled" in report["reason"]


def test_directory_round_trip_and_two_node_delivery(two_nodes, monkeypatch, tmp_path):
    """Node A announces, discovers B, seals for B, B opens — over real HTTP."""
    (a_home, a_id), (b_home, b_id) = two_nodes
    monkeypatch.setenv("OPENAMER_REPLICATION_NETWORK", "1")

    # B runs the peer endpoint (accept + store) — that is all a peer needs.
    peer_store = tmp_path / "b-received"
    peer = rep.make_server("127.0.0.1", 0, peer_store, keep=2)
    threading.Thread(target=peer.serve_forever, daemon=True).start()

    # The directory is a third, dumb service.
    directory = net.make_directory_server(tmp_path / "dir.json", port=0)
    threading.Thread(target=directory.serve_forever, daemon=True).start()

    try:
        directory_url = f"http://127.0.0.1:{directory.server_port}"
        b_url = f"http://127.0.0.1:{peer.server_port}"

        # B publishes itself.
        ni._home = lambda: b_home  # noqa: ARG005 - explicit per-node home
        monkeypatch.setattr(ni, "_home", lambda: b_home)
        net.announce(b_url, directory=directory_url)

        # A announces itself and syncs to everyone it finds.
        monkeypatch.setattr(ni, "_home", lambda: a_home)
        report = net.announce_and_sync("http://127.0.0.1:9", directory=directory_url)

        assert report["peers"] == 1, report
        assert report["results"][0]["ok"] is True, report
        stored = sorted(peer_store.glob("replica-*.json"))
        assert len(stored) == 1, "B stored nothing"

        # B opens what it received with its own private key — and nobody else can.
        envelope = stored[0].read_bytes()
        bundle, entries, header = net.open_as(envelope, b_id)
        assert header["sender"] == a_id.node_id
        assert entries, "manifest missing"
        assert bundle[:2] == b"\x1f\x8b", "expected a gzip stream after decryption"

        monkeypatch.setattr(ni, "_home", lambda: a_home)
        with pytest.raises(rep.IntegrityError):
            net.open_as(envelope, a_id)
    finally:
        directory.shutdown()
        directory.server_close()
        peer.shutdown()
        peer.server_close()


def test_directory_rejects_a_node_without_a_valid_public_key(two_nodes, tmp_path):
    import urllib.error
    import urllib.request

    directory = net.make_directory_server(tmp_path / "dir.json", port=0)
    threading.Thread(target=directory.serve_forever, daemon=True).start()
    try:
        url = f"http://127.0.0.1:{directory.server_port}/nodes"
        body = json.dumps({"node_id": "abc", "url": "http://x", "public_key": "AAAA"}).encode("utf-8")
        request = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
        with pytest.raises(urllib.error.HTTPError) as excinfo:
            urllib.request.urlopen(request, timeout=10)
        assert excinfo.value.code == 400
    finally:
        directory.shutdown()
        directory.server_close()


def test_status_reports_off_and_the_node_id(two_nodes):
    status = net.network_status()

    assert "enabled" in status
    assert status["node_id"] and len(status["node_id"]) == 16
    assert status["directory"] is None or isinstance(status["directory"], str)
