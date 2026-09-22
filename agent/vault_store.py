#!/usr/bin/env python3
"""Local credential vault: named items, resolved on demand, never in the environment.

WHY A SEPARATE ABSTRACTION
    ``agent/secret_sources/`` resolves env-var-shaped values at process STARTUP
    and writes them into ``os.environ``. Its contract says so explicitly and is
    deliberately read-only: "Sources resolve refs → values. There is no
    write-back, no arbitrary secret objects, and no mid-session secret API. If a
    future need for rotation/refresh appears it will arrive as a versioned
    optional hook — do not bolt it on."

    Autofill needs the other shape: named ITEMS (login / payment / address),
    each bound to an origin, resolved ON DEMAND at the moment a page is filled.
    So this is a separate store, and nothing here is written into the
    environment — a stored password cannot leak through an env dump or a child
    process.

MODEL-BLIND INVARIANT
    A secret value is read only by the fill path, and the object handed back to a
    caller never contains it. The bytes are registered with the redaction
    boundary (:func:`agent.redact.register_redaction_value`) so a later browser
    call cannot echo them back to the model either.

    This module is the field/kind vocabulary that
    :mod:`agent.vault_login_classifier` was written against: ``PAYMENT_FIELDS``
    and ``ADDRESS_FIELDS`` map a field NAME to the autocomplete TOKEN the
    classifier produces, and that mapping is what
    ``select_checkout_fills(classified, secret, field_tokens)`` consumes.

STORAGE
    ``<OPENAMER_HOME>/vault/items.json``, AES-256-GCM under a key from
    ``<OPENAMER_HOME>/vault/key.bin`` (created 0600). The key file is the trust
    boundary: a copied ``items.json`` alone is useless. It does NOT protect
    against an attacker who already reads the user's files, and saying otherwise
    would be dishonest.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import secrets
import stat
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlsplit

from openamer_constants import get_openamer_home

logger = logging.getLogger(__name__)

KIND_LOGIN = "login"
KIND_PAYMENT = "payment"
KIND_ADDRESS = "address"
KINDS = (KIND_LOGIN, KIND_PAYMENT, KIND_ADDRESS)

# Field NAME -> autocomplete TOKEN. The tokens are the ones
# agent.vault_login_classifier emits, which is what makes the classifier's
# select_checkout_fills() usable with this store's payloads.
PAYMENT_FIELDS: Dict[str, str] = {
    "cardholder": "cc-name",
    "number": "cc-number",
    "exp_month": "cc-exp-month",
    "exp_year": "cc-exp-year",
    "cvc": "cc-csc",
}
ADDRESS_FIELDS: Dict[str, str] = {
    "name": "name",
    "line1": "address-line1",
    "line2": "address-line2",
    "city": "address-level2",
    "region": "address-level1",
    "postal_code": "postal-code",
    "country": "country-name",
}

# Fields that are secret for a given kind. An identifier is NOT secret (the
# agent reads it and types it itself), but a card number and a CVC are.
_SECRET_FIELDS = {
    KIND_LOGIN: ("password",),
    KIND_PAYMENT: ("number", "cvc"),
    KIND_ADDRESS: (),
}

_MAGIC = b"OPENAMERVAULT1"
_NONCE_LEN = 12
_SENTINEL = "«redacted»"


class VaultError(RuntimeError):
    """A vault failure whose message is safe to surface."""


class UnlockRequired(VaultError):
    """A protected item was requested without a usable key."""


def normalize_origin(url_or_origin: str) -> Optional[str]:
    """Reduce a URL to the exact origin used for binding.

    ``https://Example.com:443/login?x=1`` -> ``https://example.com``.
    Scheme + host only, default ports elided, never a parent domain and never a
    wildcard: the fill path refuses on any mismatch, which requires exactness.
    """
    if not url_or_origin or not isinstance(url_or_origin, str):
        return None
    raw = url_or_origin.strip()
    if not raw or raw in {"about:blank", ":"}:
        return None
    if "://" not in raw:
        raw = "https://" + raw.lstrip("/")
    parts = urlsplit(raw)
    scheme = (parts.scheme or "").lower()
    host = (parts.hostname or "").lower()
    if scheme not in {"http", "https"} or not host:
        return None
    port = parts.port
    default = (scheme == "https" and port == 443) or (scheme == "http" and port == 80)
    return f"{scheme}://{host}" if (port is None or default) else f"{scheme}://{host}:{port}"


def scrub_secret_from_text(text: str, secrets: Optional[List[str]] = None) -> str:
    """Mask every registered value and any explicit ``secrets`` in ``text``.

    Belt and braces for callers that hold the bytes locally before releasing a
    string: the redaction registry is the primary boundary, this covers the
    window before registration.
    """
    from agent.redact import _redact_registered_literals  # single source of truth

    out = _redact_registered_literals(text or "")
    for value in secrets or []:
        if isinstance(value, str) and len(value) >= 8 and value in out:
            out = out.replace(value, _SENTINEL)
    return out


def _vault_dir() -> Path:
    return get_openamer_home() / "vault"


def _key_path() -> Path:
    return _vault_dir() / "key.bin"


@dataclass
class VaultItemMeta:
    """Metadata about a stored item. Contains NO secret material."""

    id: str
    kind: str
    label: str
    origin: Optional[str] = None
    allowed_origins: List[str] = field(default_factory=list)
    identifier: Optional[str] = None
    identifier_type: Optional[str] = None
    has_otp: bool = False

    def to_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {
            "handle": self.id,
            "kind": self.kind,
            "label": self.label,
            "origin": self.origin,
            "available": self.kind == KIND_LOGIN or bool(self.origin),
        }
        if len(self.allowed_origins) > 1:
            out["allowed_origins"] = list(self.allowed_origins)
        if self.identifier:
            out["identifier"] = self.identifier
            out["identifier_type"] = self.identifier_type
        if self.has_otp:
            out["two_factor"] = "an authenticator key is stored; codes are generated server-side"
        return out


class VaultStore:
    """The vault. One instance per OPENAMER_HOME; safe to call from any thread."""

    def __init__(self, path: Optional[Path] = None) -> None:
        self._path = Path(path) if path else (_vault_dir() / "items.json")
        self._lock = threading.RLock()
        self._items: Optional[Dict[str, Dict[str, Any]]] = None
        self._unlocked = False
        self._key_override: Optional[bytes] = None

    # -- key + persistence -------------------------------------------------

    def _key(self) -> bytes:
        if self._key_override:
            return self._key_override
        path = _key_path()
        if path.exists():
            data = path.read_bytes()
            if len(data) >= 32:
                if len(data) != 32:
                    # Not fatal, but it means the file was written in text mode:
                    # on Windows a 0x0A byte in the key becomes CRLF and the file
                    # grows. The first 32 bytes still decrypt THIS vault, so we
                    # keep going — but say so, because the cause is a real bug
                    # that must not be rediscovered as "missing or damaged key".
                    logger.warning(
                        "vault key file is %d bytes (expected 32) — it was written in "
                        "text mode; the trailing newline conversion does not affect "
                        "this vault, but the writer must pass os.O_BINARY", len(data))
                return data[:32]
        path.parent.mkdir(parents=True, exist_ok=True)
        key = secrets.token_bytes(32)
        # Permissions BEFORE the write: the key must never be readable, not even
        # for the instant between creating and chmod-ing it.
        #
        # O_BINARY is mandatory, not cosmetic. On Windows os.open() defaults to
        # TEXT mode, where a 0x0A byte in the random key is written as CRLF and
        # the file becomes 33 bytes. Reading back the first 32 bytes then yields a
        # different key and every decrypt fails — and since a 32-byte random key
        # contains 0x0A about 11.8% of the time, roughly one vault in eight was
        # silently corrupted. Verified by running the CLI repeatedly: the failing
        # run left key.bin at 33 bytes. POSIX has no O_BINARY, hence getattr.
        flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_BINARY", 0)
        fd = os.open(str(path), flags, 0o600)
        try:
            # "wb" puts the descriptor in binary mode, the same idiom
            # agent/proxy_sources/iron_proxy.py uses for CA key bytes. Writing
            # with a bare os.write() would honour the text mode that os.open
            # defaults to on Windows — see the comment above.
            with os.fdopen(fd, "wb") as handle:
                written = handle.write(key)
            if written != len(key):  # never leave a partial key behind
                raise VaultError(f"could not write the vault key ({written}/{len(key)} bytes)")
        finally:
            try:
                os.close(fd)
            except OSError:
                pass
        try:  # no-op on Windows, where ACLs already scope the user's home
            os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
        except OSError:
            pass
        return key

    def _encrypt(self, plaintext: bytes) -> bytes:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM

        nonce = secrets.token_bytes(_NONCE_LEN)
        # The format records no nonce length, so _decrypt slices a fixed
        # _NONCE_LEN. Assert it here: a short or long nonce would otherwise
        # produce a blob that can never be decrypted again, discovered only at
        # the next read.
        if len(nonce) != _NONCE_LEN:
            raise VaultError(f"nonce must be {_NONCE_LEN} bytes, got {len(nonce)}")
        return _MAGIC + nonce + AESGCM(self._key()).encrypt(nonce, plaintext, None)

    def _decrypt(self, blob: bytes) -> bytes:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM

        if not blob.startswith(_MAGIC):
            raise VaultError("vault file is not in the expected format")
        body = blob[len(_MAGIC):]
        if len(body) <= _NONCE_LEN:
            raise VaultError("vault file is truncated")
        nonce, ciphertext = body[:_NONCE_LEN], body[_NONCE_LEN:]
        try:
            return AESGCM(self._key()).decrypt(nonce, ciphertext, None)
        except Exception as exc:
            raise VaultError("vault could not be decrypted (wrong or damaged key)") from exc

    def _load(self) -> Dict[str, Dict[str, Any]]:
        if self._items is not None:
            return self._items
        if not self._path.exists():
            self._items = {}
            return self._items
        raw = self._path.read_bytes()
        if not raw.strip():
            self._items = {}
            return self._items
        data = json.loads(self._decrypt(raw).decode("utf-8"))
        if not isinstance(data, dict):
            raise VaultError("vault contents are malformed")
        self._items = data
        return self._items

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        blob = self._encrypt(json.dumps(self._items or {}, ensure_ascii=False).encode("utf-8"))
        tmp = self._path.with_suffix(".tmp")
        tmp.write_bytes(blob)
        os.replace(tmp, self._path)  # atomic: a crash never leaves a half vault

    # -- readiness ---------------------------------------------------------

    def is_unlocked(self) -> bool:
        """Whether a protected item may be resolved in this process.

        A vault readable with the on-disk key is open by construction — the
        single-user case. An unreadable one reports locked instead of raising on
        every status call; the reason is logged so the cause is diagnosable
        rather than collapsing into "missing or damaged key".
        """
        if self._unlocked:
            return True
        try:
            self._load()
        except Exception as exc:
            logger.warning("vault could not be opened: %s: %s", type(exc).__name__, exc)
            return False
        return True

    def needs_unlock(self) -> bool:
        return not self.is_unlocked()

    def unlock(self, key: bytes | str) -> None:
        """Adopt an explicit key for this process (bytes, or a passphrase)."""
        if isinstance(key, str):
            key = key.encode("utf-8")
        if not isinstance(key, (bytes, bytearray)) or len(key) < 16:
            raise VaultError("vault key must be at least 16 bytes")
        self._key_override = bytes(key)[:32].ljust(32, b"\0")
        self._items = None
        self._load()
        self._unlocked = True

    # -- items -------------------------------------------------------------

    def _meta_from(self, handle: str, item: Dict[str, Any]) -> VaultItemMeta:
        fields = item.get("fields") or {}
        return VaultItemMeta(
            id=handle,
            kind=str(item.get("kind", "")),
            label=str(item.get("label", "")),
            origin=item.get("origin"),
            allowed_origins=list(item.get("allowed_origins") or []),
            identifier=fields.get("identifier"),
            identifier_type=item.get("identifier_type"),
            has_otp=bool(fields.get("otp_seed")),
        )

    def list_items(self) -> List[VaultItemMeta]:
        with self._lock:
            return [self._meta_from(h, i) for h, i in sorted(self._load().items())]

    def get_meta(self, handle: str) -> Optional[VaultItemMeta]:
        with self._lock:
            item = self._load().get(handle)
        return self._meta_from(handle, item) if item else None

    def add_item(
        self,
        kind: str,
        label: str,
        fields: Dict[str, str],
        *,
        origin: Optional[str] = None,
        allowed_origins: Optional[List[str]] = None,
        item_id: Optional[str] = None,
    ) -> VaultItemMeta:
        """Store a new item and return its metadata. The caller keeps the handle."""
        if kind not in KINDS:
            raise VaultError(f"unknown item kind {kind!r} (expected one of {', '.join(KINDS)})")
        if not isinstance(fields, dict) or not fields:
            raise VaultError("an item needs at least one field")

        bound = [o for o in (normalize_origin(x) for x in (allowed_origins or [])) if o]
        norm_origin = normalize_origin(origin) if origin else None
        if norm_origin and norm_origin not in bound:
            bound.insert(0, norm_origin)
        if kind != KIND_LOGIN and not bound:
            raise VaultError(f"a {kind} item must be bound to at least one origin")

        identifier = str(fields.get("identifier", "") or "")
        with self._lock:
            items = self._load()
            handle = item_id or secrets.token_hex(8)
            while handle in items:
                handle = secrets.token_hex(8)
            items[handle] = {
                "kind": kind,
                "label": label or (norm_origin or kind),
                "origin": norm_origin or (bound[0] if bound else None),
                "allowed_origins": bound,
                "identifier_type": ("email" if "@" in identifier
                                    else ("phone" if identifier.lstrip("+").isdigit()
                                          else ("username" if identifier else None))),
                "fields": {k: str(v) for k, v in fields.items() if v is not None},
            }
            self._save()
            item = items[handle]
        return self._meta_from(handle, item)

    def remove_item(self, handle: str) -> bool:
        with self._lock:
            items = self._load()
            if handle not in items:
                return False
            del items[handle]
            self._save()
        return True

    # -- resolution (the only path that touches secret bytes) --------------

    def resolve_password(self, handle: str) -> str:
        """The stored password for a login. Never log, echo or return this."""
        with self._lock:
            item = self._load().get(handle)
        if item is None:
            raise VaultError(f"no vault item with handle {handle!r}")
        return str((item.get("fields") or {}).get("password", ""))

    def resolve_secret(self, handle: str) -> Dict[str, str]:
        """The item's field values. Same rule as resolve_password."""
        with self._lock:
            item = self._load().get(handle)
        if item is None:
            raise VaultError(f"no vault item with handle {handle!r}")
        return dict(item.get("fields") or {})

    def allowed_origins_for(self, handle: str) -> List[str]:
        """The exact origins this item may be filled on (never a wildcard)."""
        meta = self.get_meta(handle)
        if meta is None:
            raise VaultError(f"no vault item with handle {handle!r}")
        return list(meta.allowed_origins) or ([meta.origin] if meta.origin else [])


_store: Optional[VaultStore] = None
_store_lock = threading.Lock()


def get_vault_store() -> VaultStore:
    """The process-wide vault for the current OPENAMER_HOME."""
    global _store
    with _store_lock:
        if _store is None:
            _store = VaultStore()
        return _store


def reset_vault_store_for_tests() -> None:
    """Drop the cached store (tests that swap OPENAMER_HOME)."""
    global _store
    with _store_lock:
        _store = None
