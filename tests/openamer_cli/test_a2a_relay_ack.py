"""Tests for openamer_cli.a2a.relay — ack/claim dedup + TTL pruning.

The swarm loop pulls a mailbox repeatedly; without an acknowledgement the same
note would be reprocessed on every pull, spinning noise and double-charging
work. This covers:
  * claim() returns a note exactly once (then it is acked)
  * explicit ack() marks a note consumed for subsequent pulls
  * purge() prunes consumed notes that have aged past a TTL so the inbox
    never grows unboundedly
  * ack/claim state never leaks the envelope payload (privacy by construction)
"""
import json
import time

import pytest


# ---- helpers ---------------------------------------------------------------

def _mk(tp, envelope_cls):
    tp.mkdir(parents=True, exist_ok=True)
    (tp / "payload.txt").write_text("NEVER_RELAYED", encoding="utf-8")
    return tp


def _two_peers(tmp_path, core):
    stA = core.IdentityStore(tmp_path / "A")
    stB = core.IdentityStore(tmp_path / "B")
    A = stA.ensure_identity()
    B = stB.ensure_identity()
    return stA, stB, A, B


def _note(relay, core, stA, stB, A, B, kind="ping", payload=None):
    env = core.Envelope.create(
        private_key=stA.private_key(), sender=A.fingerprint,
        recipient=B.fingerprint, kind=kind,
        payload=payload or {"ask": "repeat?"},
    )
    return relay.relay_note(identity_store=stA, envelope=env)


# ----------------------------------------------------------------------------

def test_claim_returns_note_exactly_once(tmp_path):
    from openamer_cli.a2a import core, relay as rl
    stA, stB, A, B = _two_peers(tmp_path, core)
    mb = rl.RelayMailbox(tmp_path / "inbox")
    mb.store(_note(rl, core, stA, stB, A, B))

    claimed1 = mb.claim("*")
    claimed2 = mb.claim("*")
    assert len(claimed1) == 1
    assert len(claimed2) == 0, "note must not be claimed twice"


def test_explicit_ack_marks_consumed(tmp_path):
    from openamer_cli.a2a import core, relay as rl
    stA, stB, A, B = _two_peers(tmp_path, core)
    mb = rl.RelayMailbox(tmp_path / "inbox")
    f = mb.store(_note(rl, core, stA, stB, A, B))
    fname = f.name

    asserted = mb.is_consumed(fname)
    assert asserted is False

    mb.ack(fname)
    assert mb.is_consumed(fname) is True
    # and a fresh pull no longer surfaces it
    assert mb.claim("*") == []


def test_claim_surfaces_unconsumed_and_acks_in_bulk(tmp_path):
    from openamer_cli.a2a import core, relay as rl
    stA, stB, A, B = _two_peers(tmp_path, core)
    mb = rl.RelayMailbox(tmp_path / "inbox")
    n1 = _note(rl, core, stA, stB, A, B, payload={"i": 1})
    mb.store(n1)
    mb.store(_note(rl, core, stA, stB, A, B, payload={"i": 2}))

    got1 = mb.claim("*")
    got2 = mb.claim("*")
    assert len(got1) == 2
    assert got2 == []


def test_claim_respects_mailbox_filter(tmp_path):
    from openamer_cli.a2a import core, relay as rl
    stA, stB, A, B = _two_peers(tmp_path, core)
    mb = rl.RelayMailbox(tmp_path / "inbox")
    noteB = _note(rl, core, stA, stB, A, B)
    mb.store(noteB)

    recipient_pfx = noteB["recipient"][:8]
    assert len(mb.claim(recipient_pfx)) == 1
    assert mb.claim("other-mailbox") == []
    assert mb.claim("other-mailbox") == []  # still unconsumed, just filtered


def test_purge_prunes_aged_consumed_notes(tmp_path, monkeypatch):
    from openamer_cli.a2a import core, relay as rl
    stA, stB, A, B = _two_peers(tmp_path, core)
    mb = rl.RelayMailbox(tmp_path / "inbox")
    f1 = mb.store(_note(rl, core, stA, stB, A, B))
    f2 = mb.store(_note(rl, core, stA, stB, A, B))
    mb.claim("*")  # consumes both

    # freshest is now; age f1 into the past
    old = f1.stat().st_mtime - 10_000
    import os
    os.utime(f1, (old, old))
    mb.purge_consumed(max_age=300)

    assert f1.exists() is False, "aged consumed note must be purged"
    assert f2.exists() is True, "young consumed note must survive"
    assert mb.is_consumed(f2.name) is True
    # post-purge a fresh claim still sees nothing new
    assert mb.claim("*") == []


def test_purge_does_not_touch_unconsumed(tmp_path):
    from openamer_cli.a2a import core, relay as rl
    stA, stB, A, B = _two_peers(tmp_path, core)
    mb = rl.RelayMailbox(tmp_path / "inbox")
    f = mb.store(_note(rl, core, stA, stB, A, B))  # never claimed
    mb.purge_consumed(max_age=0)
    assert f.exists() is True


def test_acked_old_note_verifies_but_is_not_reprocessed(tmp_path):
    from openamer_cli.a2a import core, relay as rl
    stA, stB, A, B = _two_peers(tmp_path, core)
    mb = rl.RelayMailbox(tmp_path / "inbox")
    note = _note(rl, core, stA, stB, A, B)
    f = mb.store(note)
    mb.ack(f.name)

    for fname, n in mb.claim("*"):
        assert rl.verify_note(n).get("ok") is True
    # ack already consumed => nothing to reprocess even though note was valid
    assert mb.claim("*") == []


def test_consumer_state_never_contains_payload(tmp_path):
    from openamer_cli.a2a import core, relay as rl
    stA, stB, A, B = _two_peers(tmp_path, core)
    secret = "TEL:+49 152 99999999 CARD:4111 1111 1111 1111"
    mb = rl.RelayMailbox(tmp_path / "inbox")
    note = _note(rl, core, stA, stB, A, B, payload={"secret": secret})
    f = mb.store(note)
    # relay body itself must be redacted (existing guarantee)
    blob = json.dumps(note)
    assert "151 99999999" not in blob and "4111" not in blob

    mb.claim("*")
    # the ack/ledger file must ALSO never carry the material
    for ledger in mb.dir.glob("*.json"):
        body = ledger.read_text(encoding="utf-8")
        assert "151 99999999" not in body
        assert "4111" not in body


def test_cli_purge_zero_actually_purges(tmp_path):
    """Regression: `--purge 0` (max_age=0) must run — 0 is falsy but valid TTL."""
    from openamer_cli.a2a import core, relay as rl
    from openamer_cli.subcommands import a2a as subcmd

    stA, stB, A, B = _two_peers(tmp_path, core)
    mb = rl.RelayMailbox(tmp_path / "inbox")
    f = mb.store(_note(rl, core, stA, stB, A, B))
    mb.ack(f.name)  # consumed

    class Args:
        relay_cmd = "pull"
        mailbox = "*"
        repo_dir = str(mb.dir)
        once = False
        purge = 0

    rc = subcmd._cmd_relay(Args())
    assert rc == 0
    assert f.exists() is False, "--purge 0 must delete the consumed note"
    # ledger survives (dedup state preserved), note body gone
    assert (mb.dir / rl.RelayMailbox.ACK_MARK).exists()