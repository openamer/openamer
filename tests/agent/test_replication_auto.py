"""Automatic replication: the tick delivers, not only proves.

"The tick proves the artifact" and "a replica exists on another machine" are two
different claims. These tests pin the second one: a registered peer triggers a
real push from the loop, a failed push is visible in the state, and the genesis
probe refuses to call DIR-01 satisfied until a push has actually landed.
"""

from __future__ import annotations

import json
import threading

import pytest

from agent import genesis_runtime as rt
from agent import replication as rep


@pytest.fixture()
def temp_home(tmp_path, monkeypatch):
    monkeypatch.setattr(rep, "_home", lambda: tmp_path)
    monkeypatch.setattr(rt, "_home", lambda: tmp_path)
    (tmp_path / "memory" / "self_model").mkdir(parents=True)
    (tmp_path / "memory" / "self_model" / "identity.md").write_text("# me\n", encoding="utf-8")
    (tmp_path / "config.yaml").write_text("model:\n  provider: test\n", encoding="utf-8")
    (tmp_path / "cron").mkdir()
    (tmp_path / "cron" / "jobs.json").write_text("[]", encoding="utf-8")
    return tmp_path


def test_push_without_peers_is_reported_not_faked(temp_home):
    report = rep.push_to_peers()

    assert report["ok"] is False
    assert report["peers"] == 0
    assert report["reason"] == "no peers registered"
    assert rep.status()["last_push_ok"] is False


def test_push_delivers_to_a_registered_peer(temp_home):
    server = rep.make_server("127.0.0.1", 0, temp_home / "peer", keep=3)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        rep.register_peer(f"http://127.0.0.1:{server.server_port}")
        report = rep.push_to_peers()

        assert report["ok"] is True, report
        assert report["results"][0]["ok"] is True
        assert list((temp_home / "peer").glob("replica-*.json")), "peer stored nothing"
        state = rep.status()
        assert state["last_push_ok"] is True
        assert state["last_push_peers"] == 1
    finally:
        server.shutdown()
        server.server_close()


def test_failed_push_keeps_dir01_partial(temp_home):
    # Port 9 is the discard port: a push there fails fast.
    rep.register_peer("http://127.0.0.1:9")
    rep.selftest()

    report = rep.push_to_peers(timeout=2.0)
    assert report["ok"] is False
    assert "error" in report["results"][0]

    probe = rt._probe_replication()
    assert probe.verdict == rt.PARTIAL
    assert "no successful push" in probe.detail


def test_successful_push_lets_the_probe_satisfy_dir01(temp_home):
    server = rep.make_server("127.0.0.1", 0, temp_home / "peer", keep=2)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        rep.register_peer(f"http://127.0.0.1:{server.server_port}")
        rep.selftest()
        rep.push_to_peers()

        probe = rt._probe_replication()
        assert probe.verdict == rt.SATISFIED, probe.detail
        assert probe.values["last_push_ok"] is True
    finally:
        server.shutdown()
        server.server_close()


def test_tick_pushes_when_a_peer_is_registered(temp_home, monkeypatch):
    calls = []

    def fake_push(*args, **kwargs):
        calls.append(kwargs)
        return {"ok": True, "peers": 1, "results": [{"ok": True}]}

    monkeypatch.setattr("agent.replication.push_to_peers", fake_push)
    rep.register_peer("http://127.0.0.1:9")

    rt.tick(now=1000.0)

    assert calls, "a registered peer must make the tick deliver a snapshot"


def test_tick_does_not_push_without_peers(temp_home, monkeypatch):
    calls = []
    monkeypatch.setattr("agent.replication.push_to_peers", lambda *a, **k: calls.append(1))

    rt.tick(now=1000.0)

    assert calls == [], "no peer registered means nothing to push to"


def test_selftest_does_not_clobber_a_recorded_push(temp_home):
    server = rep.make_server("127.0.0.1", 0, temp_home / "peer", keep=2)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        rep.register_peer(f"http://127.0.0.1:{server.server_port}")
        rep.push_to_peers()
        assert rep.status()["last_push_ok"] is True

        rep.selftest()  # must merge, not overwrite

        state = json.loads(rep.state_path().read_text(encoding="utf-8"))
        assert "last_push" in state, "selftest dropped the push record"
        assert rep.status()["last_push_ok"] is True
    finally:
        server.shutdown()
        server.server_close()
