"""openamer_cli.a2a.trust — explicit trust & capability grants for A2A.

Phase 1: a persisted, opt-in trust store. A node only accepts and executes
remote work from peers that the operator has explicitly `trust add`ed, and only
for capabilities that have been granted (bounded scope + budget). Nothing runs
untrusted; nothing is auto-granted.
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional


@dataclass
class Peer:
    fingerprint: str
    public_key: str
    name: str = ""
    added_ts: int = 0

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Peer":
        return cls(
            fingerprint=d.get("fingerprint", ""),
            public_key=d.get("public_key", ""),
            name=d.get("name", ""),
            added_ts=d.get("added_ts", 0),
        )


@dataclass
class Grant:
    """A bounded capability granted to a peer."""
    peer: str          # peer fingerprint
    capability: str    # e.g. terminal.read, network.fetch, model.reason
    scope: str = "*"   # path/domain/type restriction
    budget: float = 0  # max bytes / cents / seconds; 0 = unlimited
    expires_ts: int = 0  # 0 = no expiry

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Grant":
        return cls(
            peer=d.get("peer", ""),
            capability=d.get("capability", ""),
            scope=d.get("scope", "*"),
            budget=float(d.get("budget", 0)),
            expires_ts=int(d.get("expires_ts", 0)),
        )


class TrustStore:
    """Persisted peers + grants under <home>/a2a/trust.json."""

    def __init__(self, home: Path | None = None):
        base = Path(home or os.environ.get("OPENAMER_HOME", "") or (Path.home() / ".openamer"))
        if str(base).strip() in ("", "."):
            base = Path.home() / ".openamer"
        self._dir = Path(base) / "a2a"
        self._path = self._dir / "trust.json"
        self._dir.mkdir(parents=True, exist_ok=True)
        self._peers: dict[str, Peer] = {}
        self._grants: dict[str, list[Grant]] = {}
        self._load()

    # ---- persistence ------------------------------------------------------

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            self._peers = {
                k: Peer.from_dict(v) for k, v in data.get("peers", {}).items()
            }
            self._grants = {
                k: [Grant.from_dict(g) for g in v]
                for k, v in data.get("grants", {}).items()
            }
        except Exception:
            pass

    def _save(self) -> None:
        data = {
            "peers": {k: v.to_dict() for k, v in self._peers.items()},
            "grants": {k: [g.to_dict() for g in v] for k, v in self._grants.items()},
        }
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        try:
            os.chmod(tmp, 0o600)
        except OSError:
            pass
        tmp.replace(self._path)

    # ---- peers ------------------------------------------------------------

    def add_peer(self, fingerprint: str, public_key: str, name: str = "") -> Peer:
        peer = Peer(fingerprint=fingerprint, public_key=public_key, name=name,
                    added_ts=int(time.time()))
        self._peers[fingerprint] = peer
        self._save()
        return peer

    def remove_peer(self, fingerprint: str) -> bool:
        removed = self._peers.pop(fingerprint, None) is not None
        self._grants.pop(fingerprint, None)
        if removed:
            self._save()
        return removed

    def trusted(self, fingerprint: str) -> Optional[Peer]:
        return self._peers.get(fingerprint)

    def peers(self) -> list[Peer]:
        return sorted(self._peers.values(), key=lambda p: p.fingerprint)

    # ---- grants -----------------------------------------------------------

    def grant(self, peer: str, capability: str, scope: str = "*",
              budget: float = 0, expires_ts: int = 0) -> Grant:
        """Grant a bounded capability to a trusted peer."""
        if not self.trusted(peer):
            raise ValueError(f"peer {peer} is not trusted; add it first")
        g = Grant(peer=peer, capability=capability, scope=scope,
                  budget=budget, expires_ts=expires_ts)
        self._grants.setdefault(peer, []).append(g)
        self._save()
        return g

    def has_grant(self, peer: str, capability: str) -> bool:
        if not self.trusted(peer):
            return False
        now = int(time.time())
        for g in self._grants.get(peer, []):
            if g.capability != capability:
                continue
            if g.expires_ts and now > g.expires_ts:
                continue
            return True
        return False

    def grants_for(self, peer: str) -> list[Grant]:
        now = int(time.time())
        return [g for g in self._grants.get(peer, [])
                if not (g.expires_ts and now > g.expires_ts)]

    def revoke(self, peer: str, capability: str | None = None) -> int:
        if peer not in self._grants:
            return 0
        if capability is None:
            n = len(self._grants[peer])
            del self._grants[peer]
            self._save()
            return n
        before = len(self._grants[peer])
        self._grants[peer] = [g for g in self._grants[peer] if g.capability != capability]
        after = len(self._grants[peer])
        self._save()
        return before - after


# convenience alias used by the CLI
def load_trust(home: Path | None = None) -> TrustStore:
    return TrustStore(home)