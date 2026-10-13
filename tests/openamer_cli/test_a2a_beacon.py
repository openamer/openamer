"""Tests for node beacon / discovery (openamer_cli.a2a.beacon)."""

from __future__ import annotations

import time

import pytest

from openamer_cli.a2a.core import generate_identity, pubkey_fingerprint
from openamer_cli.a2a import beacon as b


def _id():
    priv, pub = generate_identity()
    fp = pubkey_fingerprint(pub)
    return priv, pub, fp


def test_beacon_round_trip_and_verify():
    priv, pub, fp = _id()
    bcn = b.NodeBeacon.create(
        private_key_hex=priv, node=fp, public_key=pub,
        endpoint="https://relay", caps=["a2a", "propose"],
    )
    assert bcn.verify()
    restored = b.NodeBeacon.from_dict(bcn.to_dict())
    assert restored.to_dict() == bcn.to_dict()
    assert restored.verify()


def test_beacon_json_round_trip():
    priv, pub, fp = _id()
    bcn = b.NodeBeacon.create(private_key_hex=priv, node=fp, public_key=pub)
    assert b.NodeBeacon.from_json(bcn.to_json()).verify()


def test_beacon_verify_rejects_tampered_endpoint():
    priv, pub, fp = _id()
    bcn = b.NodeBeacon.create(private_key_hex=priv, node=fp, public_key=pub, endpoint="ok")
    bcn.endpoint = "evil"
    assert not bcn.verify()


def test_beacon_verify_rejects_expired():
    priv, pub, fp = _id()
    old = int(time.time()) - 10_000
    bcn = b.NodeBeacon.create(
        private_key_hex=priv, node=fp, public_key=pub, ts=old
    )
    assert not bcn.verify(tolerance=300)


def test_discovery_accepts_verified_fresher():
    priv, pub, fp = _id()
    d = b.DiscoveryTable()
    b1 = b.NodeBeacon.create(private_key_hex=priv, node=fp, public_key=pub, endpoint="a")
    assert d.ingest(b1) is True
    assert d.count() == 1
    # same node, newer ts, wins
    b2 = b.NodeBeacon.create(private_key_hex=priv, node=fp, public_key=pub, endpoint="b")
    assert d.ingest(b2) is True
    assert d.get(fp).endpoint == "b"


def test_discovery_rejects_stale():
    priv, pub, fp = _id()
    d = b.DiscoveryTable()
    newer = b.NodeBeacon.create(
        private_key_hex=priv, node=fp, public_key=pub, endpoint="newer",
        ts=int(time.time()),
    )
    assert d.ingest(newer) is True
    older = b.NodeBeacon.create(
        private_key_hex=priv, node=fp, public_key=pub, endpoint="older",
        ts=int(time.time()) - 50,
    )
    assert d.ingest(older) is False  # stale, rejected
    assert d.get(fp).endpoint == "newer"


def test_discovery_rejects_bad_signature():
    priv, pub, fp = _id()
    d = b.DiscoveryTable()
    bcn = b.NodeBeacon.create(private_key_hex=priv, node=fp, public_key=pub)
    bcn.endpoint = "tampered"
    assert d.ingest(bcn) is False
    assert d.count() == 0


def test_discovery_sorts_and_clear():
    d = b.DiscoveryTable()
    for i in range(3):
        priv, pub, fp = _id()
        d.ingest(b.NodeBeacon.create(private_key_hex=priv, node=fp, public_key=pub))
    nodes = d.nodes()
    assert nodes == sorted(nodes, key=lambda x: x.node)
    d.clear()
    assert d.count() == 0


def test_mqtt_available_returns_bool():
    # Never raises; returns True/False based on paho presence.
    import builtins
    assert b._mqtt_client_available() in (True, False)


def test_connect_broker_requires_paho():
    if not b._mqtt_client_available():
        with pytest.raises(ImportError):
            b.connect_broker()
    else:
        # paho present — connection attempt will raise an OSError (no network
        # in tests) OR work; either way it must not raise ImportError.
        try:
            b.connect_broker()
        except ImportError:
            pytest.fail("connect_broker should not raise ImportError when paho is present")
        except Exception:
            pass  # network failure expected without broker