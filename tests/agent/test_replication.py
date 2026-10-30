"""Tests for the replication module (DIR-01's own half).

What must be true before this may be called "encrypted replication":

- a sealed snapshot restores byte-identically (hash per file, not "it opened");
- a tampered envelope is refused *before* anything is written;
- a wrong key is refused;
- a hostile archive cannot escape the restore target;
- credentials and the multi-GB state DB are not silently included;
- the transport works against a real HTTP endpoint (loopback), and refuses
  plain HTTP to anything that is not loopback.

The peer half of DIR-01 needs a second machine; these tests therefore prove the
artifact and the transport, never "redundancy achieved".
"""

from __future__ import annotations

import http.server
import json
import threading
from pathlib import Path

import pytest

from agent import replication as rep


@pytest.fixture()
def temp_home(tmp_path, monkeypatch):
    monkeypatch.setattr(rep, "_home", lambda: tmp_path)
    home = tmp_path
    (home / "memory" / "self_model").mkdir(parents=True)
    (home / "memory" / "self_model" / "identity.md").write_text("# me\n", encoding="utf-8")
    (home / "memory" / "genesis").mkdir(parents=True)
    (home / "memory" / "genesis" / "state.json").write_text("{}", encoding="utf-8")
    (home / "memory" / "episode.jsonl").write_text('{"a":1}\n', encoding="utf-8")
    (home / "config.yaml").write_text("model:\n  provider: test\n", encoding="utf-8")
    (home / "cron").mkdir()
    (home / "cron" / "jobs.json").write_text("[]", encoding="utf-8")
    return home


def test_selftest_round_trips_a_real_snapshot(temp_home):
    result = rep.selftest()

    assert result["ok"] is True
    assert result["files"] >= 3
    assert result["bytes"] > 0
    assert result["envelope_bytes"] > result["bytes"] // 4


def test_restore_reproduces_bytes_exactly(temp_home):
    key = rep.load_or_create_key()
    sources = [temp_home / "memory", temp_home / "config.yaml"]
    bundle, entries = rep.build_bundle(sources, base=temp_home)
    envelope = rep.seal(bundle, entries, key)

    target = temp_home / "restored"
    report = rep.restore(envelope, key, target)

    assert report["restored"] == len(entries)
    for entry in entries:
        original = temp_home / entry["path"]
        assert (target / entry["path"]).read_bytes() == original.read_bytes()


def test_tampered_ciphertext_is_refused(temp_home):
    key = rep.load_or_create_key()
    bundle, entries = rep.build_bundle([temp_home / "memory"], base=temp_home)
    envelope = json.loads(rep.seal(bundle, entries, key).decode("utf-8"))

    cipher = bytearray(bytes.fromhex(envelope["ciphertext"]))
    cipher[0] ^= 0xFF
    envelope["ciphertext"] = cipher.hex()

    with pytest.raises(rep.IntegrityError):
        rep.open_sealed(json.dumps(envelope).encode("utf-8"), key)


def test_wrong_key_is_refused(temp_home):
    bundle, entries = rep.build_bundle([temp_home / "memory"], base=temp_home)
    envelope = rep.seal(bundle, entries, rep.load_or_create_key())

    with pytest.raises(rep.IntegrityError):
        rep.open_sealed(envelope, b"\x01" * rep.KEY_BYTES)


def test_manifest_digest_mismatch_is_refused(temp_home):
    key = rep.load_or_create_key()
    bundle, entries = rep.build_bundle([temp_home / "memory"], base=temp_home)
    payload = json.loads(rep.seal(bundle, entries, key).decode("utf-8"))

    payload["manifest"][0]["size"] = 999_999  # lie about the manifest, keep the header

    with pytest.raises(rep.IntegrityError, match="manifest"):
        rep.open_sealed(json.dumps(payload).encode("utf-8"), key)


def test_unsafe_archive_member_is_refused(temp_home):
    import io
    import tarfile

    key = rep.load_or_create_key()
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as tar:
        data = b"pwned"
        info = tarfile.TarInfo("../escape.txt")
        info.size = len(data)
        tar.addfile(info, io.BytesIO(data))
    entries = [{"path": "../escape.txt", "size": len(data), "sha256": rep.hashlib.sha256(data).hexdigest()}]
    envelope = rep.seal(buffer.getvalue(), entries, key)

    with pytest.raises(rep.IntegrityError, match="unsafe"):
        rep.restore(envelope, key, temp_home / "out")


def test_secrets_and_state_db_are_excluded(temp_home):
    (temp_home / ".env").write_text("SECRET=1", encoding="utf-8")
    (temp_home / "memory" / "identity.key").write_bytes(b"k" * 32)
    (temp_home / "state.db").write_bytes(b"x" * 1024)

    _bundle, entries = rep.build_bundle([temp_home], base=temp_home)

    paths = {entry["path"] for entry in entries}
    assert ".env" not in paths
    assert not any(p.endswith("identity.key") for p in paths)
    assert "state.db" not in paths


def test_key_is_stable_and_32_bytes(temp_home):
    first = rep.load_or_create_key()
    second = rep.load_or_create_key()

    assert len(first) == rep.KEY_BYTES
    assert first == second, "an existing key must not be replaced"
    assert rep.key_path().exists()


def test_scrypt_derivation_is_deterministic():
    salt = b"0" * 16
    assert rep.derive_key("pw", salt) == rep.derive_key("pw", salt)
    assert rep.derive_key("pw", salt) != rep.derive_key("pw", b"1" * 16)


def test_status_reports_module_selftest_and_peers(temp_home):
    assert rep.status()["peers"] == 0
    assert rep.status()["last_selftest_ok"] is False

    rep.selftest()
    status = rep.status()

    assert status["module"] is True
    assert status["last_selftest_ok"] is True
    assert status["last_selftest_files"] >= 3
    assert status["peers"] == 0, "one machine has no peers — the gate stays shut"


def test_register_peer_persists_but_does_not_claim_reachability(temp_home):
    rep.register_peer("http://127.0.0.1:9/", name="loopback")

    status = rep.status()
    assert status["peers"] == 1
    assert rep.load_peers()[0]["name"] == "loopback"


class _Collector(http.server.BaseHTTPRequestHandler):
    received: list[bytes] = []

    def do_POST(self):  # noqa: N802 - http.server API
        length = int(self.headers.get("Content-Length", "0"))
        type(self).received.append(self.rfile.read(length))
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"stored")

    def log_message(self, *args):  # keep test output quiet
        return


def test_push_to_a_real_loopback_peer_and_open_it_there(temp_home):
    _Collector.received = []
    server = http.server.HTTPServer(("127.0.0.1", 0), _Collector)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        key = rep.load_or_create_key()
        bundle, entries = rep.build_bundle([temp_home / "memory"], base=temp_home)
        envelope = rep.seal(bundle, entries, key)

        result = rep.push(envelope, f"http://127.0.0.1:{server.server_port}")

        assert result["status"] == 200
        assert _Collector.received, "peer received nothing"
        # The peer can open it with the shared key: transport + artifact agree.
        restored_bundle, restored_entries, _header = rep.open_sealed(_Collector.received[0], key)
        assert restored_entries == entries
        assert restored_bundle == bundle
    finally:
        server.shutdown()
        server.server_close()


def test_push_refuses_plain_http_to_a_remote_host(temp_home):
    bundle, entries = rep.build_bundle([temp_home / "memory"], base=temp_home)
    envelope = rep.seal(bundle, entries, rep.load_or_create_key())

    with pytest.raises(rep.ReplicationError, match="non-loopback"):
        rep.push(envelope, "http://example.com")


def test_deterministic_bundle_same_tree_same_digest(temp_home):
    first, entries_first = rep.build_bundle([temp_home / "memory"], base=temp_home)
    second, entries_second = rep.build_bundle([temp_home / "memory"], base=temp_home)

    assert entries_first == entries_second
    assert first == second, "same input must seal to the same bytes (mtime is zeroed)"
