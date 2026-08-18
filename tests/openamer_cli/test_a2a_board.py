"""Tests for the shared proposal board (openamer_cli.a2a.board)."""

from __future__ import annotations

import time

from openamer_cli.a2a.core import generate_identity, pubkey_fingerprint
from openamer_cli.a2a.proposal import CodeProposal
from openamer_cli.a2a import board as bd


def _id():
    priv, pub = generate_identity()
    return priv, pub, pubkey_fingerprint(pub)


def _proposal(priv, node, title="t", ts=None):
    return CodeProposal.create(
        private_key_hex=priv, sender=node, title=title,
        description="d", patch="p", ts=ts,
    )


def test_proposal_id_stable():
    priv, _pub, node = _id()
    p1 = _proposal(priv, node)
    p2 = _proposal(priv, node)
    assert bd.proposal_id(p1) == bd.proposal_id(p2)


def test_board_submit_and_list():
    priv, _pub, node = _id()
    board = bd.ProposalBoard()
    board.submit(_proposal(priv, node, "fix"))
    assert board.count() == 1
    assert [p.title for p in board.proposals()] == ["fix"]


def test_board_submit_rejects_older():
    priv, _pub, node = _id()
    board = bd.ProposalBoard()
    old = int(time.time()) - 1000
    board.submit(_proposal(priv, node, "old", ts=old))
    # newer proposal with same content-id
    new = _proposal(priv, node, "old")
    assert board.submit(new) is True
    # strictly older for same id rejected
    assert board.submit(_proposal(priv, node, "old", ts=old - 5)) is False


def test_signal_round_trip_and_verify():
    priv, pub, node = _id()
    _p, _pub, other = _id()
    prop = _proposal(priv, other)
    pid = bd.proposal_id(prop)
    sig = bd.Signal.create(
        private_key_hex=priv, node=node, proposal_id=pid, value="+1"
    )
    assert sig.verify(pub)
    restored = bd.Signal.from_dict(sig.to_dict())
    assert restored.to_dict() == sig.to_dict()
    assert restored.verify(pub)


def test_signal_value_validation():
    priv, _pub, node = _id()
    try:
        bd.Signal.create(private_key_hex=priv, node=node, proposal_id="x", value="bad")
        assert False, "should raise"
    except ValueError:
        pass


def test_board_add_signal_requires_trusted():
    priv, pub, node = _id()
    _p, _pub, other = _id()
    prop = _proposal(priv, other)
    board = bd.ProposalBoard()
    board.submit(prop)
    pid = bd.proposal_id(prop)
    sig = bd.Signal.create(private_key_hex=priv, node=node, proposal_id=pid, value="+1")
    # node not trusted -> rejected
    assert board.add_signal(sig, trusted={}) is False
    # trusted -> accepted
    assert board.add_signal(sig, trusted={node: pub}) is True


def test_board_scores():
    a_priv, a_pub, a_node = _id()
    b_priv, b_pub, b_node = _id()
    _p, _pub, c_node = _id()
    prop = _proposal(a_priv, c_node)
    board = bd.ProposalBoard()
    board.submit(prop)
    pid = bd.proposal_id(prop)
    board.add_signal(bd.Signal.create(private_key_hex=a_priv, node=a_node, proposal_id=pid, value="+1"), trusted={a_node: a_pub})
    board.add_signal(bd.Signal.create(private_key_hex=b_priv, node=b_node, proposal_id=pid, value="+1"), trusted={b_node: b_pub})
    s = board.scores()[pid]
    assert s["ups"] == 2
    assert s["net"] == 2


def test_board_scores_with_down_and_note():
    a_priv, a_pub, a_node = _id()
    b_priv, b_pub, b_node = _id()
    c_priv, c_pub, c_node = _id()
    _p, _pub, s_node = _id()
    prop = _proposal(a_priv, s_node)
    board = bd.ProposalBoard()
    board.submit(prop)
    pid = bd.proposal_id(prop)
    board.add_signal(bd.Signal.create(private_key_hex=a_priv, node=a_node, proposal_id=pid, value="+1"), trusted={a_node: a_pub})
    board.add_signal(bd.Signal.create(private_key_hex=b_priv, node=b_node, proposal_id=pid, value="-1"), trusted={b_node: b_pub})
    board.add_signal(bd.Signal.create(private_key_hex=c_priv, node=c_node, proposal_id=pid, value="note", note="hmm"), trusted={c_node: c_pub})
    s = board.scores()[pid]
    assert s["ups"] == 1 and s["downs"] == 1 and s["notes"] == 1
    assert s["net"] == 0 and s["count"] == 3


def test_latest_signal_per_node_wins():
    a_priv, a_pub, a_node = _id()
    _p, _pub, s_node = _id()
    prop = _proposal(a_priv, s_node)
    board = bd.ProposalBoard()
    board.submit(prop)
    pid = bd.proposal_id(prop)
    board.add_signal(bd.Signal.create(private_key_hex=a_priv, node=a_node, proposal_id=pid, value="+1"), trusted={a_node: a_pub})
    board.add_signal(bd.Signal.create(private_key_hex=a_priv, node=a_node, proposal_id=pid, value="-1"), trusted={a_node: a_pub})
    s = board.scores()[pid]
    assert s["ups"] == 0 and s["downs"] == 1  # latest wins, one slot per node
