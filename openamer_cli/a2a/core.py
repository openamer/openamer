"""openamer_a2a.core — Agent-to-Agent core primitives for OpenAmer.

Phase 0: node identity (Ed25519) and a signed, replay-protected message envelope.
This is the security- and protocol-critical foundation everything else builds on.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Optional

try:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ed25519
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PrivateKey, Ed25519PublicKey,
    )
    _HAVE_CRYPTO = True
except Exception:  # pragma: no cover - cryptography is always installed
    _HAVE_CRYPTO = False
    Ed25519PrivateKey = None
    Ed25519PublicKey = None


# --- identity -----------------------------------------------------------------

@dataclass
class NodeIdentity:
    """A node's public identity. The fingerprint doubles as the address."""
    public_key: str            # hex-encoded Ed25519 public key (32 bytes -> 64 hex chars)
    fingerprint: str           # short address-like id: first 16 hex chars of sha256(pubkey)

    def __post_init__(self) -> None:
        if not self.public_key:
            raise ValueError("NodeIdentity requires a public key")
        if not self.fingerprint:
            self.fingerprint = pubkey_fingerprint(self.public_key)


def _public_key_hex(pub: Ed25519PublicKey) -> str:
    raw = pub.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return raw.hex()


def pubkey_fingerprint(pubkey_hex: str) -> str:
    """Short address id: sha256(pubkey hex)[:16]."""
    return hashlib.sha256(pubkey_hex.encode("ascii")).hexdigest()[:16]


def generate_identity() -> tuple[str, str]:
    """Generate a fresh keypair. Returns (private_key_hex, public_key_hex)."""
    if not _HAVE_CRYPTO:
        raise RuntimeError("cryptography not available")
    priv = Ed25519PrivateKey.generate()
    raw = priv.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )
    pub = _public_key_hex(priv.public_key())
    return raw.hex(), pub


class IdentityStore:
    """Stores the node's private key on disk (0600) and loads identity."""

    def __init__(self, home: Path | None = None):
        base = home or Path(os.environ.get("OPENAMER_HOME", "") or "").expanduser()
        if base == Path(".") or not base.is_absolute() or base == Path():
            # fall back to a per-user default
            base = Path(os.environ.get("OPENAMER_HOME", str(Path.home() / ".openamer")))
        if not str(base).strip():
            base = Path.home() / ".openamer"
        self._dir = Path(base)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._path = self._dir / "a2a" / "identity.json"

    def exists(self) -> bool:
        return self._path.exists()

    def ensure_identity(self) -> NodeIdentity:
        if self._path.exists():
            return self.load()
        return self.create()

    def create(self) -> NodeIdentity:
        priv_hex, pub_hex = generate_identity()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps({"private_key_hex": priv_hex, "public_key_hex": pub_hex})
        # secure perms on POSIX; best-effort on Windows
        with open(self._path, "w", encoding="utf-8") as f:
            f.write(payload)
        try:
            os.chmod(self._path, 0o600)
        except OSError:
            pass
        return NodeIdentity(public_key=pub_hex, fingerprint=pubkey_fingerprint(pub_hex))

    def load(self) -> NodeIdentity:
        with open(self._path, "r", encoding="utf-8") as f:
            data = json.load(f)
        pub = data["public_key_hex"]
        return NodeIdentity(public_key=pub, fingerprint=pubkey_fingerprint(pub))

    def private_key(self) -> Ed25519PrivateKey:
        with open(self._path, "r", encoding="utf-8") as f:
            data = json.load(f)
        raw = bytes.fromhex(data["private_key_hex"])
        return Ed25519PrivateKey.from_private_bytes(raw)


# --- signed envelope ----------------------------------------------------------

_REPLAY_TOLERANCE_SECONDS = 300  # messages must be signed within last 5 minutes


@dataclass
class Envelope:
    """A signed, replay-protected A2A message."""

    sender: str          # fingerprint
    recipient: str       # fingerprint
    kind: str            # e.g. "task", "answer", "skill.proposal", "ping"
    payload: object
    nonce: str
    ts: int              # unix seconds
    signature: str = ""  # hex signature over the canonical bytes

    # --- constructor helpers --------------------------------------------------

    @classmethod
    def create(
        cls,
        *,
        private_key: Ed25519PrivateKey,
        sender: str,
        recipient: str,
        kind: str,
        payload: object,
        ts: Optional[int] = None,
    ) -> "Envelope":
        ts = ts if ts is not None else int(time.time())
        nonce = os.urandom(16).hex()
        env = cls(
            sender=sender, recipient=recipient, kind=kind,
            payload=payload, nonce=nonce, ts=ts,
        )
        env.signature = env._sign(private_key)
        return env

    # --- serialization --------------------------------------------------------

    def _body(self) -> str:
        return json.dumps(
            {
                "sender": self.sender,
                "recipient": self.recipient,
                "kind": self.kind,
                "payload": self.payload,
                "nonce": self.nonce,
                "ts": self.ts,
            },
            sort_keys=True, separators=(",", ":"),
        )

    def _sign(self, private_key: Ed25519PrivateKey) -> str:
        return private_key.sign(self._body().encode("utf-8")).hex()

    def to_dict(self) -> dict:
        return {
            "sender": self.sender,
            "recipient": self.recipient,
            "kind": self.kind,
            "payload": self.payload,
            "nonce": self.nonce,
            "ts": self.ts,
            "signature": self.signature,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Envelope":
        return cls(
            sender=d["sender"], recipient=d["recipient"], kind=d["kind"],
            payload=d.get("payload"), nonce=d["nonce"], ts=d["ts"],
            signature=d.get("signature", ""),
        )

    # --- verification ---------------------------------------------------------

    def verify(self, sender_public_key_hex: str) -> bool:
        """Verify signature + freshness. Returns True if authentic & fresh."""
        if not self.signature:
            return False
        try:
            return self._verify_signature(sender_public_key_hex) and self._fresh()
        except Exception:
            return False

    def _verify_signature(self, sender_public_key_hex: str) -> bool:
        pub = public_key_from_hex(sender_public_key_hex)
        try:
            pub.verify(bytes.fromhex(self.signature), self._body().encode("utf-8"))
            return True
        except Exception:
            return False

    def _fresh(self) -> bool:
        now = int(time.time())
        return abs(now - self.ts) <= _REPLAY_TOLERANCE_SECONDS


def public_key_from_hex(hex_str: str) -> Ed25519PublicKey:
    return Ed25519PublicKey.from_public_bytes(bytes.fromhex(hex_str))


# --- robustness ---------------------------------------------------------------

@lru_cache(maxsize=128)
def _pub_hex_to_obj(pub_hex: str) -> Ed25519PublicKey:
    return Ed25519PublicKey.from_public_bytes(bytes.fromhex(pub_hex))