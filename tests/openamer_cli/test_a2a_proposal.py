"""Tests for signed code proposals (openamer_cli.a2a.proposal)."""

from __future__ import annotations

import json

import pytest

from openamer_cli.a2a.core import generate_identity
from openamer_cli.a2a import proposal as p


def _identity():
    priv_hex, pub_hex = generate_identity()
    return priv_hex, pub_hex


def test_proposal_round_trip(tmp_path):
    priv_hex, pub_hex = _identity()
    prop = p.CodeProposal.create(
        private_key_hex=priv_hex,
        sender="nodeA",
        title="fix bug",
        description="fix the thing",
        patch="--- a/x\n+++ b/y\n",
        paths=["a/x", "b/y"],
    )
    d = prop.to_dict()
    restored = p.CodeProposal.from_dict(d)
    assert restored.to_dict() == d
    assert restored.verify(pub_hex)


def test_proposal_json_round_trip(tmp_path):
    priv_hex, pub_hex = _identity()
    prop = p.CodeProposal.create(
        private_key_hex=priv_hex, sender="s", title="t", description="d"
    )
    raw = prop.to_json()
    restored = p.CodeProposal.from_json(raw)
    assert restored.title == "t"
    assert restored.verify(pub_hex)


def test_verify_rejects_tampered_patch(tmp_path):
    priv_hex, pub_hex = _identity()
    prop = p.CodeProposal.create(
        private_key_hex=priv_hex, sender="s", title="t",
        description="d", patch="good",
    )
    assert prop.verify(pub_hex)
    # Tamper the patch -> signature no longer valid.
    prop.patch = "evil"
    assert not prop.verify(pub_hex)


def test_verify_rejects_wrong_key(tmp_path):
    priv_hex, _pub_hex = _identity()
    _, other_pub = _identity()
    prop = p.CodeProposal.create(private_key_hex=priv_hex, sender="s", title="t", description="d")
    assert not prop.verify(other_pub)


def test_verify_rejects_expired(tmp_path):
    priv_hex, pub_hex = _identity()
    # old ts -> outside tolerance
    prop = p.CodeProposal.create(
        private_key_hex=priv_hex, sender="s", title="t", description="d",
        ts=int(__import__("time").time()) - 1000,
    )
    assert not prop.verify(pub_hex, tolerance=300)


def test_verify_missing_signature_is_false(tmp_path):
    _, pub_hex = _identity()
    prop = p.CodeProposal.from_dict({
        "sender": "s", "ts": 1, "nonce": "n", "title": "t", "description": "d",
        "patch": "", "paths": [], "change_type": "patch", "signature": "",
    })
    assert not prop.verify(pub_hex)


def test_guardian_rejects_untrusted_sender(tmp_path):
    priv_hex, _pub_hex = _identity()
    prop = p.CodeProposal.create(private_key_hex=priv_hex, sender="stranger", title="t", description="d")
    ok, reason = p.verify_proposal_for_guardian(prop, trusted_peers={})
    assert ok is False
    assert "not in the trust directory" in reason


def test_guardian_accepts_trusted_verified(tmp_path):
    priv_hex, pub_hex = _identity()
    prop = p.CodeProposal.create(private_key_hex=priv_hex, sender="trusted", title="t", description="d")
    ok, reason = p.verify_proposal_for_guardian(
        prop, trusted_peers={"trusted": pub_hex}
    )
    assert ok is True
    assert reason == "verified"


def test_guardian_rejects_trusted_but_bad_sig(tmp_path):
    priv_hex, pub_hex = _identity()
    prop = p.CodeProposal.create(private_key_hex=priv_hex, sender="trusted", title="t", description="d")
    prop.patch = "tampered"
    ok, _reason = p.verify_proposal_for_guardian(
        prop, trusted_peers={"trusted": pub_hex}
    )
    assert ok is False


def test_canonical_json_is_deterministic():
    a = p._canonical_json({"b": 1, "a": [2, 1]})
    b = p._canonical_json({"a": [2, 1], "b": 1})
    assert a == b


def test_requires_private_key_to_sign():
    with pytest.raises(ValueError):
        p.CodeProposal.create(private_key_hex="", sender="s", title="t", description="d")
