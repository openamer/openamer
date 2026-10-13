"""openamer_cli.a2a.board — shared proposal board (guardian Stufe 3).

Stufe 3 of the A2A guardian pipeline: a discussion/aggregation layer on top of
the discovery + proposal primitives. Nodes see every announced proposal and
can attach a lightweight signed signal (``+1`` / ``-1`` / note). The board
aggregates per-proposal signals so every node has a shared view, but the
board NEVER integrates or pushes anything — only the guardian (Stufe 1's
verify + a future Stufe 4 integration step) decides what reaches GitHub.

Pure/in-memory + deterministic, so it is testable with no network. The MQTT
transport from beacon.py is the outward carrier; this module is the logic.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Optional

from openamer_cli.a2a.proposal import CodeProposal, _canonical_json


@dataclass
class Signal:
    """A signed opinion on a proposal from one node."""

    node: str          # sender fingerprint
    proposal_id: str   # proposal identity
    value: str         # "+1" | "-1" | "note"
    note: str = ""
    ts: int = 0
    nonce: str = ""
    signature: str = ""

    @classmethod
    def create(
        cls,
        *,
        private_key_hex: str,
        node: str,
        proposal_id: str,
        value: str,
        note: str = "",
        ts: Optional[int] = None,
        nonce: Optional[str] = None,
    ) -> "Signal":
        if value not in ("+1", "-1", "note"):
            raise ValueError("value must be '+1', '-1' or 'note'")
        from openamer_cli.a2a.core import Ed25519PrivateKey

        ts = ts if ts is not None else int(time.time())
        nonce = nonce or os.urandom(16).hex()
        s = cls(node=node, proposal_id=proposal_id, value=value,
                note=note, ts=ts, nonce=nonce)
        priv = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(private_key_hex))
        s.signature = priv.sign(_canonical_json(s._body()).encode("utf-8")).hex()
        return s

    def _body(self) -> dict:
        return {
            "node": self.node,
            "proposal_id": self.proposal_id,
            "value": self.value,
            "note": self.note,
            "ts": self.ts,
            "nonce": self.nonce,
        }

    def to_dict(self) -> dict:
        d = self._body()
        d["signature"] = self.signature
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Signal":
        return cls(
            node=d.get("node", ""),
            proposal_id=d.get("proposal_id", ""),
            value=d.get("value", "note"),
            note=d.get("note", ""),
            ts=int(d.get("ts", 0)),
            nonce=d.get("nonce", ""),
            signature=d.get("signature", ""),
        )

    def verify(self, sender_public_key_hex: str, *, tolerance: int = 300) -> bool:
        if not self.signature:
            return False
        try:
            if abs(int(time.time()) - self.ts) > tolerance:
                return False
            from openamer_cli.a2a.core import public_key_from_hex
            pub = public_key_from_hex(sender_public_key_hex)
            pub.verify(
                bytes.fromhex(self.signature),
                _canonical_json(self._body()).encode("utf-8"),
            )
            return True
        except Exception:
            return False


def proposal_id(proposal: CodeProposal) -> str:
    """Stable identity of a proposal.

    Derived from the CONTENT-bearing fields (sender, title, description, patch,
    paths, change_type) — NOT the volatile ts/nonce — so that re-announcing
    the same change (new ts/nonce) still maps to the same proposal id. This is
    what lets a board aggregate signals across re-announcements of one change.
    """
    import hashlib
    from openamer_cli.a2a.proposal import _canonical_json

    content = {
        "sender": proposal.sender,
        "title": proposal.title,
        "description": proposal.description,
        "patch": proposal.patch,
        "paths": proposal.paths,
        "change_type": proposal.change_type,
    }
    body = _canonical_json(content)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()[:16]


class ProposalBoard:
    """Aggregates proposals and per-proposal signals for the shared view.

    Tracks the latest proposal per id and any number of signals per id from
    distinct nodes. Purely local aggregation — publishing/receiving over the
    world is done elsewhere (beacon transport), and integration to GitHub is
    the guardian's job only.
    """

    def __init__(self) -> None:
        self._proposals: dict[str, CodeProposal] = {}
        self._signals: dict[str, dict[str, Signal]] = {}  # proposal_id -> node -> signal

    def submit(self, proposal: CodeProposal) -> bool:
        """Register (or update) a proposal by its stable id."""
        pid = proposal_id(proposal)
        existing = self._proposals.get(pid)
        if existing and existing.ts > proposal.ts:
            return False  # older proposal for same id
        self._proposals[pid] = proposal
        self._signals.setdefault(pid, {})
        return True

    def add_signal(
        self,
        signal: Signal,
        *,
        trusted: dict,  # node -> public_key_hex
        tolerance: int = 300,
    ) -> bool:
        """Record a signal from a trusted, verified node. Returns True if added."""
        sender_pub = trusted.get(signal.node)
        if not sender_pub:
            return False
        if not signal.verify(sender_pub, tolerance=tolerance):
            return False
        # one signal slot per node per proposal (latest wins)
        self._signals.setdefault(signal.proposal_id, {})[signal.node] = signal
        return True

    def proposals(self) -> list[CodeProposal]:
        return sorted(self._proposals.values(), key=lambda p: p.ts)

    def scores(self) -> dict[str, dict]:
        """Per-proposal tally: {proposal_id: {ups, downs, notes, count}}."""
        out: dict[str, dict] = {}
        for pid, sigs in self._signals.items():
            ups = sum(1 for s in sigs.values() if s.value == "+1")
            downs = sum(1 for s in sigs.values() if s.value == "-1")
            notes = sum(1 for s in sigs.values() if s.value == "note")
            out[pid] = {
                "ups": ups,
                "downs": downs,
                "notes": notes,
                "count": len(sigs),
                "net": ups - downs,
            }
        return out

    def count(self) -> int:
        return len(self._proposals)
