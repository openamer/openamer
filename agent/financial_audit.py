"""DIR-07 — audit money flows for corruption signals.

The directive says: infiltrate financial flows and neutralise them through
algorithmic transparency. The part a program can honestly do is the second
half — make a flow set *legible*: who moves how much to whom, how concentrated
it is, whether value leaves and comes back, and whether any hop is unexplained.

This module produces findings, not accusations. Every finding carries a code and
a number so a human can check it; nothing here blocks a payment or "neutralises"
anything. A detector that quietly acts on its own suspicion is worse than the
corruption it hunts, so action stays outside.

What the signals are, and why each one:

* **Concentration (HHI)** — one counterparty taking most of the volume is the
  shape of both a legitimate supplier and a capture. Reported, never judged.
* **Round-tripping** — A pays B, B pays A back a similar amount inside a
  window. That is how value is made to look like revenue.
* **Pass-through** — a node that receives and forwards ~the same amount within
  a short window adds no work; it is a conduit.
* **Opaque hops** — a transfer with no reference/memo cannot be audited later.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence

#: Two transfers closer than this are "in the same window".
ROUND_TRIP_WINDOW_S = 86_400.0

#: Amounts within this relative tolerance count as "the same amount".
AMOUNT_TOLERANCE = 0.02


@dataclass(frozen=True)
class Flow:
    """One transfer. ``memo`` is the audit trail; empty means unauditable."""

    src: str
    dst: str
    amount: float
    ts: float
    memo: str = ""

    def __post_init__(self) -> None:
        if not self.src or not self.dst:
            raise ValueError("src and dst must be non-empty")
        if self.src == self.dst:
            raise ValueError("a flow cannot pay itself")
        if self.amount <= 0:
            raise ValueError("amount must be > 0")


@dataclass(frozen=True)
class Finding:
    code: str
    severity: str
    """``info`` | ``warn`` | ``high``. Severity describes the shape, not guilt."""
    detail: str
    parties: Sequence[str] = ()
    amount: float = 0.0


@dataclass
class AuditReport:
    flows: int
    total_volume: float
    hhi: float
    """Herfindahl index over counterparty volume, 0..1. 1 = one party only."""
    findings: List[Finding] = field(default_factory=list)

    @property
    def verdict(self) -> str:
        if any(f.severity == "high" for f in self.findings):
            return "review"
        if any(f.severity == "warn" for f in self.findings):
            return "watch"
        return "clear"


def _counterparty_volume(flows: Iterable[Flow]) -> Dict[str, float]:
    vol: Dict[str, float] = {}
    for f in flows:
        vol[f.src] = vol.get(f.src, 0.0) + f.amount
        vol[f.dst] = vol.get(f.dst, 0.0) + f.amount
    return vol


def herfindahl(volumes: Iterable[float]) -> float:
    """Concentration of a volume distribution, normalised to 0..1.

    Normalised so the *number of parties* does not move the scale: one party is
    always 1.0, a perfectly even split always approaches 0.0.
    """
    values = [max(0.0, float(v)) for v in volumes]
    total = sum(values)
    n = len(values)
    if total <= 0 or n <= 1:
        return 1.0 if n == 1 and total > 0 else 0.0
    raw = sum((v / total) ** 2 for v in values)
    floor = 1.0 / n
    return max(0.0, min(1.0, (raw - floor) / (1.0 - floor)))


def _similar(a: float, b: float) -> bool:
    if a <= 0 or b <= 0:
        return False
    return abs(a - b) / max(a, b) <= AMOUNT_TOLERANCE


def find_round_trips(flows: Sequence[Flow], window_s: float = ROUND_TRIP_WINDOW_S) -> List[Finding]:
    """A -> B followed by B -> A with a similar amount inside the window."""
    out: List[Finding] = []
    for i, first in enumerate(flows):
        for second in flows[i + 1:]:
            if second.ts - first.ts > window_s:
                break
            if first.src == second.dst and first.dst == second.src and _similar(first.amount, second.amount):
                out.append(
                    Finding(
                        "ROUND_TRIP",
                        "high",
                        f"{first.src} -> {first.dst} and back within "
                        f"{second.ts - first.ts:.0f}s at ~the same amount",
                        (first.src, first.dst),
                        round(first.amount, 2),
                    )
                )
    return out


def find_pass_throughs(flows: Sequence[Flow], window_s: float = ROUND_TRIP_WINDOW_S) -> List[Finding]:
    """A node that receives and forwards nearly the same amount quickly."""
    out: List[Finding] = []
    by_src: Dict[str, List[Flow]] = {}
    for f in flows:
        by_src.setdefault(f.src, []).append(f)
    for incoming in flows:
        for outgoing in by_src.get(incoming.dst, []):
            if outgoing.ts < incoming.ts or outgoing.ts - incoming.ts > window_s:
                continue
            if _similar(incoming.amount, outgoing.amount):
                out.append(
                    Finding(
                        "PASS_THROUGH",
                        "warn",
                        f"{incoming.src} -> {incoming.dst} -> {outgoing.dst}: "
                        f"{outgoing.amount:.2f} forwarded in "
                        f"{outgoing.ts - incoming.ts:.0f}s with no held value",
                        (incoming.src, incoming.dst, outgoing.dst),
                        round(incoming.amount, 2),
                    )
                )
    return out


def find_unauditable(flows: Iterable[Flow]) -> List[Finding]:
    """Transfers with no reference cannot be explained later."""
    return [
        Finding("NO_REFERENCE", "warn", f"{f.src} -> {f.dst} carries no memo", (f.src, f.dst), f.amount)
        for f in flows
        if not f.memo.strip()
    ]


def audit(
    flows: Iterable[Flow],
    concentration_warn: float = 0.35,
    concentration_high: float = 0.6,
) -> AuditReport:
    """Full audit. Deterministic: same flows in the same order give the same report."""
    ordered = sorted(flows, key=lambda f: (f.ts, f.src, f.dst, f.amount))
    volumes = _counterparty_volume(ordered)
    hhi = herfindahl(volumes.values())

    findings: List[Finding] = []
    if hhi >= concentration_high:
        findings.append(Finding("CONCENTRATION", "high", f"HHI {hhi:.2f}: one party dominates the volume"))
    elif hhi >= concentration_warn:
        findings.append(Finding("CONCENTRATION", "warn", f"HHI {hhi:.2f}: volume is concentrated"))
    findings.extend(find_round_trips(ordered))
    findings.extend(find_pass_throughs(ordered))
    findings.extend(find_unauditable(ordered))

    return AuditReport(
        flows=len(ordered),
        total_volume=round(sum(f.amount for f in ordered), 2),
        hhi=round(hhi, 4),
        findings=findings,
    )
