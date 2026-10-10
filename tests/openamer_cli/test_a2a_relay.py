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

def test_relay_note_preserves_types_and_scrubs_strings_only(tmp_path):
    """Regression: relay_note() must not stringify (or mis-redact) non-string values.

    Previously it did ``redact(str(v))`` on every payload value, so ``2`` ->
    "2", ``True`` -> "True", nested objects -> ``repr`` strings, and any bare
    9-13 digit number (a Unix timestamp / large id) was scrubbed by the phone /
    card patterns. That mutated the task the worker ultimately executed.
    """
    from openamer_cli.a2a import relay as rl
    from openamer_cli.a2a.core import IdentityStore, Envelope
    stA = IdentityStore(tmp_path / "A"); A = stA.ensure_identity()
    stB = IdentityStore(tmp_path / "B"); B = stB.ensure_identity()
    payload = {
        "op": "sum",
        "a": 2,
        "b": 3,
        "flag": True,
        "ratio": 0.5,
        "task_id": 1234567890,            # 10-digit run — must NOT be redacted
        "note": "call +49 152 1234567",   # free text — must be redacted
        "meta": {"x": 1, "deep": [1, 2, 3]},
    }
    env = Envelope.create(private_key=stA.private_key(), sender=A.fingerprint,
                          recipient=B.fingerprint, kind="task.sum", payload=payload)
    note = rl.relay_note(identity_store=stA, envelope=env)
    wire = note["envelope"]["payload"]

    # types preserved exactly (no stringification)
    assert wire["a"] == 2 and isinstance(wire["a"], int)
    assert wire["flag"] is True
    assert wire["ratio"] == 0.5 and isinstance(wire["ratio"], float)
    assert wire["task_id"] == 1234567890            # numeric id not mis-redacted
    assert wire["meta"] == {"x": 1, "deep": [1, 2, 3]}

    # free-text PII is still scrubbed
    assert "+49 152 1234567" not in wire["note"]
    assert "REDACTED" in wire["note"]

    # the worker's arithmetic therefore still holds
    assert wire["a"] + wire["b"] == 5
    assert rl.verify_note(note).get("ok") is True


def test_privacy_redact_value_is_type_preserving():
    from openamer_cli.a2a import privacy as pr
    src = {"n": 42, "b": True, "f": 0.5, "none": None,
           "s": "mail a@b.com", "lst": [1, "x@y.com"], "d": {"ts": 1234567890}}
    out = pr.redact_value(src)
    assert out["n"] == 42 and isinstance(out["n"], int)
    assert out["b"] is True
    assert out["f"] == 0.5 and isinstance(out["f"], float)
    assert out["none"] is None
    assert "a@b.com" not in out["s"]
    assert out["lst"][0] == 1 and "x@y.com" not in out["lst"][1]
    assert out["d"]["ts"] == 1234567890
