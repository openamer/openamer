"""Tests for openamer_cli.a2a.relay — GitHub relay transport (no localhost)."""
import json


def test_relay_note_redact_and_verify(tmp_path):
    from openamer_cli.a2a import relay as rl
    from openamer_cli.a2a.core import IdentityStore, Envelope
    stA = IdentityStore(tmp_path / "A"); A = stA.ensure_identity()
    stB = IdentityStore(tmp_path / "B"); B = stB.ensure_identity()
    env = Envelope.create(private_key=stA.private_key(), sender=A.fingerprint,
                          recipient=B.fingerprint, kind="ask",
                          payload={"q": "call +49 152 1234567 now", "safe": "move db"})
    note = rl.relay_note(identity_store=stA, envelope=env)
    blob = json.dumps(note)
    assert "+49 152 1234567" not in blob          # privacy redacted
    assert note["sender_pubkey"] == A.public_key
    assert rl.verify_note(note).get("ok") is True  # re-sealed sig valid
    bad = json.loads(blob); bad["envelope"]["payload"] = {"q": "MALICIOUS"}
    assert rl.verify_note(bad).get("ok") is False  # tamper rejected


def test_relay_mailbox_roundtrip(tmp_path):
    from openamer_cli.a2a import relay as rl
    from openamer_cli.a2a.core import IdentityStore, Envelope
    stA = IdentityStore(tmp_path / "A"); idA = stA.ensure_identity()
    stB = IdentityStore(tmp_path / "B"); idB = stB.ensure_identity()
    env = Envelope.create(private_key=stA.private_key(), sender=idA.fingerprint,
                          recipient=idB.fingerprint, kind="ping", payload={"hi": "ok"})
    note = rl.relay_note(identity_store=stA, envelope=env)
    mb = rl.RelayMailbox(tmp_path / "inbox")
    mb.store(note)
    got = mb.pull(note["recipient"][:8])
    assert len(got) == 1 and rl.verify_note(got[0]).get("ok") is True