"""Node identity — one X25519 keypair per install, and a stable node id.

For a network of independent installs, a single symmetric key is useless: every
node needs its own keypair so a sender can seal a snapshot **for one specific
recipient** and nobody else (including the relay) can read it.

The private key never leaves ``$OPENAMER_HOME/node/identity.key`` (0600). The
public key is what a directory publishes; the node id is a short, stable hash of
it, so two installs can name each other without trusting a server's numbering.
"""

from __future__ import annotations

import base64
import hashlib
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

NODE_KEY_BYTES = 32  # X25519 private key size


def _home() -> Path:
    try:
        from openamer_constants import get_openamer_home

        return Path(get_openamer_home())
    except Exception:  # pragma: no cover - defensive
        return Path.home() / ".openamer"


def node_dir() -> Path:
    return _home() / "node"


def private_key_path() -> Path:
    return node_dir() / "identity.key"


def node_id_for(public_key: bytes) -> str:
    """Stable, short, collision-resistant id derived from the public key.

    Not a secret: anyone holding the public key can recompute it, which is
    exactly what makes it usable in a directory.
    """
    return base64.b32encode(hashlib.sha256(public_key).digest())[:16].decode("ascii").lower()


@dataclass(frozen=True)
class NodeIdentity:
    node_id: str
    public_key: bytes
    private_key: bytes

    def public_bundle(self) -> dict:
        return {
            "node_id": self.node_id,
            "public_key": base64.b64encode(self.public_key).decode("ascii"),
        }


def _crypto():
    try:
        from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey
        from cryptography.hazmat.primitives.serialization import (
            Encoding,
            PrivateFormat,
            PublicFormat,
            NoEncryption,
        )
    except Exception as exc:  # pragma: no cover - dependency missing
        raise RuntimeError(
            "X25519 unavailable: install 'cryptography' (no hand-written key exchange)"
        ) from exc
    return X25519PrivateKey, Encoding, PrivateFormat, PublicFormat, NoEncryption


def load_or_create_identity(force_new: bool = False) -> NodeIdentity:
    """Read the node keypair, creating it on first use (never rotates silently)."""
    X25519PrivateKey, Encoding, PrivateFormat, PublicFormat, NoEncryption = _crypto()
    path = private_key_path()

    if path.exists() and not force_new:
        try:
            raw = path.read_bytes()
        except OSError as exc:
            raise RuntimeError(f"cannot read {path}: {exc}") from exc
        if len(raw) != NODE_KEY_BYTES:
            raise RuntimeError(f"{path} is not a {NODE_KEY_BYTES}-byte X25519 key")
        private = X25519PrivateKey.from_private_bytes(raw)
    else:
        private = X25519PrivateKey.generate()
        raw = private.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())
        node_dir().mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_bytes(raw)
        try:
            os.chmod(tmp, 0o600)
        except OSError:
            pass
        os.replace(tmp, path)

    public = private.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    return NodeIdentity(node_id=node_id_for(public), public_key=public, private_key=raw)


def decode_public_key(value: str) -> bytes:
    """Accept base64 or hex, return 32 raw bytes (a public key, never a secret)."""
    text = value.strip()
    try:
        raw = base64.b64decode(text, validate=True)
    except Exception:
        try:
            raw = bytes.fromhex(text)
        except Exception as exc:
            raise ValueError(f"not a base64/hex X25519 public key: {text[:16]}…") from exc
    if len(raw) != NODE_KEY_BYTES:
        raise ValueError(f"public key must be {NODE_KEY_BYTES} bytes, got {len(raw)}")
    return raw


def identity_status() -> dict:
    """What a directory needs to know, and what stays home."""
    try:
        identity = load_or_create_identity()
    except Exception as exc:  # noqa: BLE001
        return {"present": False, "error": str(exc)[:200]}
    return {
        "present": True,
        **identity.public_bundle(),
        "private_key_path": str(private_key_path()),
    }
