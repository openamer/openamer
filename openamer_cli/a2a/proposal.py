"""openamer_cli.a2a.proposal — signed code proposals for the Guardian pipeline.

Stufe 1 of the A2A guardian pipeline (see docs/engineering/a2a-guardian-pipeline.md).

A :class:`CodeProposal` is a signed request from one OpenAmer node to the
guardian (the single node that owns GitHub push access) to integrate a change.
It reuses the existing Ed25519 envelope crypto from :mod:`openamer_cli.a2a.core`
(no parallel crypto), so any node with an identity can create one and the
guardian can verify it against the trust directory.

This module is PURE and side-effect-free except for explicit file I/O helpers:
signing/verifying does not touch GitHub, does not open tunnels, and does not
push anything. Integration is deliberately NOT automatic — the guardian's job
(Stufe 2/3) decides what to do with a verified proposal.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Optional


def _canonical_json(payload: dict) -> str:
    """Deterministic JSON for signing (sort keys, compact separators)."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


@dataclass
class CodeProposal:
    """A signed, replay-protected code-change proposal for the guardian.

    Fields mirror the A2A ``Envelope`` security model (sender fingerprint,
    timestamp, nonce, signature) but are specialized for code integration:
    a patch (unified diff) or a change description, with affected paths.
    """

    sender: str            # sender node fingerprint (address)
    ts: int                # unix seconds (freshness/replay protection)
    nonce: str             # random hex, prevents replay
    title: str             # short human summary
    description: str       # why this change
    patch: str             # unified diff (or empty when change_type=info)
    paths: list[str] = field(default_factory=list)  # affected paths
    change_type: str = "patch"  # patch | info | proposal (discussion-only)
    signature: str = ""    # hex Ed25519 signature over the canonical body

    # ---- construction ----------------------------------------------------

    @classmethod
    def create(
        cls,
        *,
        private_key_hex: str,
        sender: str,
        title: str,
        description: str,
        patch: str = "",
        paths: Optional[list[str]] = None,
        change_type: str = "patch",
        ts: Optional[int] = None,
        nonce: Optional[str] = None,
    ) -> "CodeProposal":
        """Create + sign a proposal from the sender's private key (hex)."""
        from openamer_cli.a2a.core import Ed25519PrivateKey

        if not private_key_hex:
            raise ValueError("private_key_hex is required to sign a proposal")
        ts = ts if ts is not None else int(time.time())
        nonce = nonce or os.urandom(16).hex()
        prop = cls(
            sender=sender, ts=ts, nonce=nonce,
            title=title, description=description,
            patch=patch, paths=list(paths or []),
            change_type=change_type,
        )
        priv = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(private_key_hex))
        prop.signature = priv.sign(_canonical_json(prop._body()).encode("utf-8")).hex()
        return prop

    # ---- serialization ------------------------------------------------------

    def _body(self) -> dict:
        return {
            "sender": self.sender,
            "ts": self.ts,
            "nonce": self.nonce,
            "title": self.title,
            "description": self.description,
            "patch": self.patch,
            "paths": self.paths,
            "change_type": self.change_type,
        }

    def to_dict(self) -> dict:
        d = self._body()
        d["signature"] = self.signature
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "CodeProposal":
        return cls(
            sender=d.get("sender", ""),
            ts=int(d.get("ts", 0)),
            nonce=d.get("nonce", ""),
            title=d.get("title", ""),
            description=d.get("description", ""),
            patch=d.get("patch", ""),
            paths=list(d.get("paths") or []),
            change_type=d.get("change_type", "patch"),
            signature=d.get("signature", ""),
        )

    def to_json(self) -> str:
        return _canonical_json(self.to_dict())

    @classmethod
    def from_json(cls, raw: str) -> "CodeProposal":
        return cls.from_dict(json.loads(raw))

    # ---- verification -------------------------------------------------------

    def verify(self, sender_public_key_hex: str, *, tolerance: int = 300) -> bool:
        """Verify signature AND freshness against the sender's public key.

        Returns False on any failure (bad signature, expired, malformed).
        Never raises. ``tolerance`` is seconds of allowed clock skew/replay
        window (default 5 minutes, matching the A2A envelope).
        """
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


# --- guardian helpers ---------------------------------------------------------

def verify_proposal_for_guardian(
    proposal: CodeProposal,
    *,
    trusted_peers: dict,  # fingerprint -> public_key_hex
    tolerance: int = 300,
) -> tuple[bool, str]:
    """Guardian-facing check: is this proposal from a trusted, verified sender?

    Parameters
    ----------
    proposal
        The received proposal.
    trusted_peers
        Mapping of trusted node ``fingerprint -> public_key_hex`` (e.g. from a
        trust directory). The guardian ONLY integrates proposals whose sender
        is in this map AND whose signature verifies.
    tolerance
        Freshness window in seconds.

    Returns
    -------
    ``(ok, reason)``. ``ok`` is True only when the sender is trusted AND the
    signature is valid AND fresh.
    """
    sender_pub = trusted_peers.get(proposal.sender)
    if not sender_pub:
        return False, f"sender {proposal.sender} is not in the trust directory"
    if not proposal.verify(sender_pub, tolerance=tolerance):
        return False, "signature invalid or expired"
    return True, "verified"


def load_trusted_peers(home: Optional[Path] = None) -> dict:
    """Load trusted peers as ``{fingerprint: public_key_hex}`` from the A2A
    trust store. Best-effort: returns {} on any failure (never raises).
    """
    try:
        from openamer_cli.a2a.trust import TrustStore
        store = TrustStore(home)
        out: dict[str, str] = {}
        for peer in store.peers():
            out[peer.fingerprint] = peer.public_key
        return out
    except Exception:
        return {}
