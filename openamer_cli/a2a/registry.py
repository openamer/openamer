"""openamer_cli.a2a.registry — signed node announcements for the a GitHub-mesh.

Phase 2 building block: a node can produce a *signed announcement* describing
itself (identity, advertised capabilities, one or more reachable endpoints).
These announcements are shared through the GitHub repo
(`github.com/openamer/openamer/directory/a2a/`) — the single familiar source —
or directly node-to-node. The registry core here does the crypto: sign a
node card, verify an announcement against a pinned public key, and list
announcements from the repo's `directory/a2a/` (read-only, no token needed to
*read*; publishing is a normal PR/commit by the operator).

Security: every announcement carries an Ed25519 signature over its canonical
JSON plus a timestamp window, so a stale or tampered card is rejected. Peers
that trust a node pin its public key; there is no global implicit trust.
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Optional
from urllib import request, error

from openamer_cli.a2a.core import IdentityStore, public_key_from_hex


@dataclass
class Announcement:
    """A signed self-description a node publishes to the mesh."""
    fingerprint: str
    public_key: str
    name: str = "OpenAmer node"
    endpoints: list = field(default_factory=list)      # e.g. ["https://host:port"]
    capabilities: list = field(default_factory=list)  # e.g. ["task.sum", "skill.peer"]
    ts: int = 0
    signature: str = ""

    @classmethod
    def create(cls, *, private_key, fingerprint: str, public_key: str,
               name: str = "OpenAmer node", endpoints: Optional[list] = None,
               capabilities: Optional[list] = None) -> "Announcement":
        a = cls(
            fingerprint=fingerprint, public_key=public_key, name=name,
            endpoints=endpoints or [], capabilities=capabilities or [],
            ts=int(time.time()),
        )
        a.signature = private_key.sign(a.canonical().encode("utf-8")).hex()
        return a

    def canonical(self) -> str:
        return json.dumps({
            "fingerprint": self.fingerprint,
            "public_key": self.public_key,
            "name": self.name,
            "endpoints": self.endpoints,
            "capabilities": self.capabilities,
            "ts": self.ts,
        }, sort_keys=True, separators=(",", ":"))

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Announcement":
        return cls(**{k: d.get(k) for k in
                      ("fingerprint","public_key","name","endpoints",
                       "capabilities","ts","signature")})

    # ---- verification ------------------------------------------------------

    def verify(self, trusted_pubkey_hex: Optional[str] = None,
               tolerance: int = 300) -> bool:
        """Verify signature. If trusted_pubkey_hex given, must ALSO match that
        pinned key (i.e. the announcement is from the peer we trust)."""
        if not self.signature:
            return False
        try:
            pub = public_key_from_hex(self.public_key)
            pub.verify(bytes.fromhex(self.signature), self.canonical().encode("utf-8"))
        except Exception:
            return False
        if trusted_pubkey_hex and self.public_key != trusted_pubkey_hex:
            return False
        if abs(int(time.time()) - int(self.ts)) > tolerance:
            return False
        return True

    def fingerprint_matches(self) -> bool:
        from openamer_cli.a2a.core import pubkey_fingerprint
        return pubkey_fingerprint(self.public_key) == self.fingerprint


def sign_announcement(home: Optional[Path] = None, *,
                      name: str = "OpenAmer node", endpoints=None,
                      capabilities=None) -> Announcement:
    """Create + sign an announcement for THIS node's identity."""
    store = IdentityStore(home)
    ident = store.ensure_identity()
    priv = store.private_key()
    return Announcement.create(
        private_key=priv, fingerprint=ident.fingerprint,
        public_key=ident.public_key, name=name,
        endpoints=endpoints, capabilities=capabilities,
    )


REPO_BASE = "https://raw.githubusercontent.com/openamer/openamer/main/directory/a2a"


def fetch_announcement(fingerprint: str, repo_base: str = REPO_BASE,
                       timeout: float = 20.0) -> Optional[Announcement]:
    """Fetch + verify a signed announcement by its fingerprint from the GitHub
    registry directory (read-only, public — no token needed)."""
    url = f"{repo_base.rstrip('/')}/{fingerprint}.json"
    try:
        with request.urlopen(request.Request(url), timeout=timeout) as r:
            raw = r.read().decode("utf-8")
            data = json.loads(raw)
    except error.HTTPError:
        return None
    except Exception:
        return None
    ann = Announcement.from_dict(data)
    if ann.verify() and ann.ts > 0:
        return ann
    return None


def local_announcements_dir(home: Optional[Path] = None) -> Path:
    """Local stage dir where a node writes signed announcements it wants to
    publish (operator then commits it to directory/a2a/ in the repo)."""
    base = Path(home or os.environ.get("OPENAMER_HOME", "") or (Path.home()/".openamer"))
    d = Path(base) / "a2a" / "publish"
    d.mkdir(parents=True, exist_ok=True)
    return d


def save_announcement(ann: Announcement, home: Optional[Path] = None) -> Path:
    d = local_announcements_dir(home)
    out = d / f"{ann.fingerprint}.json"
    out.write_text(json.dumps(ann.to_dict(), indent=2), encoding="utf-8")
    return out