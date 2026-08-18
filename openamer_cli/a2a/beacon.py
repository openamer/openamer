"""openamer_cli.a2a.beacon — world-reachable node discovery (guardian Stufe 2).

Stufe 2 of the A2A guardian pipeline: cost-free, world-wide node discovery
that does NOT require each node to hold a GitHub token. The protocol core here
(signed node announcement + rendezvous/discovery table) is pure and testable
with no network. The actual transport is a thin, optional MQTT adapter that
lazily imports ``paho.mqtt`` only when the broker list is used, so importing
this module never requires MQTT and never breaks when paho is absent.

How it works (conceptually)
---------------------------
Each node periodically publishes a signed :class:`NodeBeacon` to a shared,
public MQTT topic (rendezvous). A beacon carries the node's fingerprint,
public key, an advertised endpoint/URL (optional — e.g. a relay or tunnel),
and capabilities. Listeners collect beacons into a :class:`DiscoveryTable`,
verify each against the sender's public key, and keep the freshest known
peers. Trust for *execution* is still decided by the guardian via the trust
directory — discovery makes nodes findable; trust decides what is runnable.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Optional

KEY = "paho.mqtt"  # optional transport dependency (lazy import)


@dataclass
class NodeBeacon:
    """A signed, time-stamped node-ping for world-wide discovery."""

    node: str            # sender fingerprint
    ts: int              # unix seconds
    public_key: str      # sender Ed25519 public key (hex) — verifies signature
    endpoint: str = ""   # optional advertised endpoint/url (relay/tunnel/mqtt topic)
    caps: list[str] = field(default_factory=list)  # e.g. ["a2a", "propose"]
    nonce: str = ""
    signature: str = ""

    # ---- construction ------------------------------------------------------

    @classmethod
    def create(
        cls,
        *,
        private_key_hex: str,
        node: str,
        public_key: str,
        endpoint: str = "",
        caps: Optional[list[str]] = None,
        ts: Optional[int] = None,
        nonce: Optional[str] = None,
    ) -> "NodeBeacon":
        from openamer_cli.a2a.core import Ed25519PrivateKey

        ts = ts if ts is not None else int(time.time())
        nonce = nonce or os.urandom(16).hex()
        bcn = cls(
            node=node, ts=ts, public_key=public_key,
            endpoint=endpoint, caps=list(caps or []), nonce=nonce,
        )
        priv = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(private_key_hex))
        bcn.signature = priv.sign(bcn._canonical().encode("utf-8")).hex()
        return bcn

    def _canonical(self) -> str:
        from openamer_cli.a2a.proposal import _canonical_json
        return _canonical_json(self._body())

    def _body(self) -> dict:
        return {
            "node": self.node,
            "ts": self.ts,
            "public_key": self.public_key,
            "endpoint": self.endpoint,
            "caps": self.caps,
            "nonce": self.nonce,
        }

    def to_dict(self) -> dict:
        d = self._body()
        d["signature"] = self.signature
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "NodeBeacon":
        return cls(
            node=d.get("node", ""),
            ts=int(d.get("ts", 0)),
            public_key=d.get("public_key", ""),
            endpoint=d.get("endpoint", ""),
            caps=list(d.get("caps") or []),
            nonce=d.get("nonce", ""),
            signature=d.get("signature", ""),
        )

    def to_json(self) -> str:
        from openamer_cli.a2a.proposal import _canonical_json
        return _canonical_json(self.to_dict())

    @classmethod
    def from_json(cls, raw: str) -> "NodeBeacon":
        import json
        return cls.from_dict(json.loads(raw))

    def verify(self, *, tolerance: int = 300) -> bool:
        """Verify the beacon signature against its OWN embedded public key."""
        if not self.signature or not self.public_key:
            return False
        try:
            if abs(int(time.time()) - self.ts) > tolerance:
                return False
            from openamer_cli.a2a.core import public_key_from_hex
            pub = public_key_from_hex(self.public_key)
            pub.verify(
                bytes.fromhex(self.signature),
                self._canonical().encode("utf-8"),
            )
            return True
        except Exception:
            return False


class DiscoveryTable:
    """Collects and verifies node beacons from the shared rendezvous topic.

    Keeps the freshest verified beacon per node fingerprint. Pure/in-memory;
    persistence is out of scope here (a future Stufe may persist it).
    """

    def __init__(self) -> None:
        self._nodes: dict[str, NodeBeacon] = {}

    def ingest(self, beacon: NodeBeacon, *, tolerance: int = 300) -> bool:
        """Add a verified beacon. Returns True if it was accepted (verifies and
        is fresher than any existing beacon from the same node)."""
        if not beacon.verify(tolerance=tolerance):
            return False
        existing = self._nodes.get(beacon.node)
        if existing:
            # Reject only a strictly-staler beacon, or an exact duplicate
            # (same ts + same nonce). Two beacons created within the same
            # second (same int ts) but different nonce are both "fresh" — the
            # later one wins so a re-announcement isn't swallowed.
            if existing.ts > beacon.ts:
                return False
            if existing.ts == beacon.ts and existing.nonce == beacon.nonce:
                return False
        self._nodes[beacon.node] = beacon
        return True

    def nodes(self) -> list[NodeBeacon]:
        return sorted(self._nodes.values(), key=lambda b: b.node)

    def get(self, node: str) -> Optional[NodeBeacon]:
        return self._nodes.get(node)

    def count(self) -> int:
        return len(self._nodes)

    def clear(self) -> None:
        self._nodes.clear()


# --- optional MQTT transport (lazy, never required at import time) ---------

def _mqtt_client_available() -> bool:
    try:
        import paho.mqtt.client  # noqa: F401
        return True
    except Exception:
        return False


def connect_broker(
    broker: str = "broker.emqx.io",
    port: int = 1883,
    topic: str = "openamer/a2a/beacon",
    *,
    client_id: str = "",
) -> object:
    """Return a connected paho MQTT client bound to the beacon topic.

    Soml = optional: raises ImportError if paho.mqtt is not installed, so
    callers must guard on :func:`_mqtt_client_available`. ``client_id`` should
    be unique per node (e.g. the fingerprint) to avoid collisions on the
    shared public broker.
    """
    import paho.mqtt.client as mqtt

    cid = client_id or "openamer-" + os.urandom(4).hex()
    client = mqtt.Client(client_id=cid, protocol=mqtt.MQTTv311)
    client.connect(broker, port, keepalive=60)
    client.loop_start()
    client.subscribe(topic)
    return client
