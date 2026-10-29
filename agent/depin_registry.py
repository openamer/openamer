"""DIR-19 — DePIN node registry: registration, liveness, capability routing.

What this is: the bookkeeping half of a decentralised physical infrastructure
network. Nodes advertise what they can compute, prove they are alive with a
heartbeat, and a scheduler picks the best live node for a task.

What this is **not**: there is no container orchestration, no remote execution,
and no cross-host trust. A registration is a claim by a node; the only thing
verified here is freshness and internal consistency. Calling this a working
DePIN would be the kind of overstatement the directive engine exists to
prevent, so ``agent.directive_engine`` records DIR-19 as ``PARTIAL`` with this
module as evidence.

Design notes worth keeping:

* Persistence is a plain JSON file at a caller-supplied path. No global state,
  no import-time directory creation — the same reason the rest of the tracked
  tree keeps stores injectable, and it makes the tests run in ``tmp_path``.
* Writes are atomic (temp file + ``os.replace``) because a registry torn
  halfway through a rewrite silently drops every node it had.
* Selection is deterministic: ties break on node id, never on dict order. A
  router whose answer depends on hash order cannot be tested and cannot be
  reproduced in an incident.
"""

from __future__ import annotations

import json
import os
import tempfile
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional

#: A node that has not been heard from for this long is not schedulable.
DEFAULT_STALE_AFTER_S = 90.0

#: Backends a consumer GPU can plausibly provide.
KNOWN_BACKENDS = ("cuda", "rocm", "metal", "cpu")


@dataclass
class NodeCapability:
    """What one node claims it can do. Unverified beyond consistency."""

    node_id: str
    backends: List[str] = field(default_factory=lambda: ["cpu"])
    vram_gb: float = 0.0
    benchmark_score: float = 0.0
    """Relative throughput measured by the node itself. Used only for ranking
    among nodes that already satisfy the task's requirements."""
    labels: Dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.node_id or not self.node_id.strip():
            raise ValueError("node_id must be a non-empty string")
        bad = [b for b in self.backends if b not in KNOWN_BACKENDS]
        if bad:
            raise ValueError(f"unknown backend(s) {bad}; known: {list(KNOWN_BACKENDS)}")
        if not self.backends:
            raise ValueError("a node must advertise at least one backend")
        if self.vram_gb < 0 or self.benchmark_score < 0:
            raise ValueError("vram_gb and benchmark_score must be >= 0")


@dataclass
class Registration:
    capability: NodeCapability
    registered_at: float
    last_seen: float

    def age(self, now: float) -> float:
        return max(0.0, now - self.last_seen)


class NodeRegistry:
    """A JSON-backed registry of DePIN nodes."""

    def __init__(self, path: os.PathLike | str, stale_after_s: float = DEFAULT_STALE_AFTER_S):
        self.path = Path(path)
        self.stale_after_s = float(stale_after_s)
        self._nodes: Dict[str, Registration] = {}
        self._load()

    # ── persistence ────────────────────────────────────────────────────────
    def _load(self) -> None:
        if not self.path.is_file():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            # A corrupt registry must not take the caller down; an empty one is
            # visibly empty, which is the honest state.
            return
        for entry in raw.get("nodes", []):
            try:
                reg = Registration(
                    capability=NodeCapability(**entry["capability"]),
                    registered_at=float(entry["registered_at"]),
                    last_seen=float(entry["last_seen"]),
                )
            except (KeyError, TypeError, ValueError):
                continue
            self._nodes[reg.capability.node_id] = reg

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "nodes": [
                {
                    "capability": asdict(reg.capability),
                    "registered_at": reg.registered_at,
                    "last_seen": reg.last_seen,
                }
                for _, reg in sorted(self._nodes.items())
            ]
        }
        data = json.dumps(payload, indent=1, sort_keys=True).encode("utf-8")
        fd, tmp = tempfile.mkstemp(dir=str(self.path.parent), prefix=".depin-", suffix=".tmp")
        try:
            with os.fdopen(fd, "wb") as fh:
                fh.write(data)
            os.replace(tmp, self.path)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

    # ── membership ─────────────────────────────────────────────────────────
    def register(self, capability: NodeCapability, now: Optional[float] = None) -> Registration:
        """Idempotent: re-registering a node updates it and keeps its first
        registration time, so ``registered_at`` stays an honest "since"."""
        ts = time.time() if now is None else float(now)
        existing = self._nodes.get(capability.node_id)
        reg = Registration(
            capability=capability,
            registered_at=existing.registered_at if existing else ts,
            last_seen=ts,
        )
        self._nodes[capability.node_id] = reg
        self._save()
        return reg

    def heartbeat(self, node_id: str, now: Optional[float] = None) -> bool:
        """Refresh liveness. Returns False for an unknown node — a heartbeat
        from a node that never registered is not a registration."""
        reg = self._nodes.get(node_id)
        if reg is None:
            return False
        reg.last_seen = time.time() if now is None else float(now)
        self._save()
        return True

    def deregister(self, node_id: str) -> bool:
        if node_id not in self._nodes:
            return False
        del self._nodes[node_id]
        self._save()
        return True

    def nodes(self) -> List[Registration]:
        return [reg for _, reg in sorted(self._nodes.items())]

    def live_nodes(self, now: Optional[float] = None) -> List[Registration]:
        ts = time.time() if now is None else float(now)
        return [r for r in self.nodes() if r.age(ts) <= self.stale_after_s]

    def stale_nodes(self, now: Optional[float] = None) -> List[Registration]:
        ts = time.time() if now is None else float(now)
        return [r for r in self.nodes() if r.age(ts) > self.stale_after_s]

    # ── scheduling ─────────────────────────────────────────────────────────
    def select(
        self,
        backend: Optional[str] = None,
        min_vram_gb: float = 0.0,
        now: Optional[float] = None,
    ) -> Optional[Registration]:
        """Best live node for a task, or None.

        Requirements filter first; ranking is by ``benchmark_score`` and then
        by node id, so the same registry state always yields the same pick.
        """
        eligible = [
            r
            for r in self.live_nodes(now)
            if r.capability.vram_gb >= min_vram_gb
            and (backend is None or backend in r.capability.backends)
        ]
        if not eligible:
            return None
        eligible.sort(key=lambda r: (-r.capability.benchmark_score, r.capability.node_id))
        return eligible[0]

    def summary(self, now: Optional[float] = None) -> dict:
        """Counts a human can act on: live, stale, and the aggregate VRAM."""
        live = self.live_nodes(now)
        return {
            "total": len(self._nodes),
            "live": len(live),
            "stale": len(self._nodes) - len(live),
            "live_vram_gb": round(sum(r.capability.vram_gb for r in live), 2),
            "backends": sorted({b for r in live for b in r.capability.backends}),
        }


def powu_weight(benchmark_score: float, uptime_fraction: float, verified_share: float) -> float:
    """DIR-20/23 weight for a node's Proof-of-Useful-Work reward.

    Proportional to verified compute contributed — which is what the directive
    demands, and also what makes the formula auditable: three bounded inputs,
    one product, no hidden term. ``verified_share`` is the anti-spoofing input
    (cross-node consensus); a node with no verified work earns nothing.
    """
    for name, value in (
        ("benchmark_score", benchmark_score),
        ("uptime_fraction", uptime_fraction),
        ("verified_share", verified_share),
    ):
        if float(value) < 0:
            raise ValueError(f"{name} must be >= 0")
    if uptime_fraction > 1.0:
        raise ValueError("uptime_fraction must be within [0, 1]")
    if verified_share > 1.0:
        raise ValueError("verified_share must be within [0, 1]")
    return float(benchmark_score) * float(uptime_fraction) * float(verified_share)


def distribute_rewards(
    nodes: Iterable[tuple[str, float]], total_reward: float
) -> Dict[str, float]:
    """Split ``total_reward`` by weight, proportionally.

    The payouts sum to ``total_reward`` up to floating-point rounding — that is
    the guarantee, not exactness: these are floats, and claiming an exact sum
    would be a promise the arithmetic cannot keep. Anything that must balance to
    the unit (an on-chain ledger) has to run in integer base units instead.
    """
    weighted = [(nid, max(0.0, float(w))) for nid, w in nodes]
    total_weight = sum(w for _, w in weighted)
    if total_weight <= 0 or total_reward <= 0:
        return {nid: 0.0 for nid, _ in weighted}
    unit = float(total_reward) / total_weight
    return {nid: w * unit for nid, w in weighted}
