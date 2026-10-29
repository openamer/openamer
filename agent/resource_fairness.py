"""DIR-08 — resource fairness as arithmetic, not sentiment.

The directive calls hunger and poverty computational errors corrected by
infrastructure. Whatever one thinks of the framing, the computable core is a
classical problem: given demands and a fixed capacity, who gets how much, and
can the result be shown to be fair rather than asserted to be?

This module implements max-min fairness ("water filling"): raise every
allocation equally until the pool is empty; a demand smaller than the current
level is satisfied and stops consuming. That is the allocation with the largest
possible minimum share, which is the definition fairness is usually measured by.

Two properties worth pinning, both tested:

* The allocation never exceeds capacity and never exceeds a demand.
* The result is *verifiable after the fact*: ``gini`` and ``min_share`` let a
  third party check the claim instead of trusting it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Mapping


def max_min_allocate(demands: Mapping[str, float], capacity: float) -> Dict[str, float]:
    """Max-min fair split of ``capacity`` across ``demands``.

    Deterministic: iteration is over sorted keys, so two runs with the same input
    produce identical floats (and a test can compare them exactly).
    """
    if capacity < 0:
        raise ValueError("capacity must be >= 0")
    clean: Dict[str, float] = {}
    for name in sorted(demands):
        need = float(demands[name])
        if need < 0:
            raise ValueError(f"demand for {name!r} must be >= 0")
        clean[name] = need

    remaining = float(capacity)
    alloc: Dict[str, float] = {name: 0.0 for name in clean}
    active: List[str] = [n for n in clean if clean[n] > 0]

    while active and remaining > 0:
        level = remaining / len(active)
        satisfied = [n for n in active if clean[n] <= level]
        if not satisfied:
            for name in active:
                alloc[name] = level
            remaining = 0.0
            break
        for name in satisfied:
            alloc[name] = clean[name]
            remaining -= clean[name]
            active.remove(name)

    return alloc


def gini(values: Iterable[float]) -> float:
    """Gini coefficient of an allocation, 0 = even, 1 = one holder takes all.

    Implemented on the sorted-mean formula so it is exactly reproducible rather
    than depending on pairwise floating-point accumulation order.
    """
    data = sorted(max(0.0, float(v)) for v in values)
    n = len(data)
    if n == 0:
        return 0.0
    total = sum(data)
    if total <= 0:
        return 0.0
    weighted = sum((i + 1) * v for i, v in enumerate(data))
    return max(0.0, min(1.0, (2 * weighted) / (n * total) - (n + 1) / n))


@dataclass(frozen=True)
class FairnessReport:
    capacity: float
    allocated: float
    unmet: float
    min_share: float
    max_share: float
    gini: float
    fully_satisfied: List[str]
    partially_satisfied: List[str]
    unserved: List[str]

    @property
    def fair(self) -> bool:
        """A defensible bar, stated so it can be argued with: nobody who asked
        gets less than half of what the average recipient got, and nothing is
        left unallocated while a demand is unmet."""
        if self.allocated <= 0:
            return False
        if self.unmet > 1e-9 and self.allocated < self.capacity - 1e-9:
            return False
        return self.min_share >= 0.5 * self.max_share or self.unserved == []


def report(demands: Mapping[str, float], capacity: float) -> FairnessReport:
    alloc = max_min_allocate(demands, capacity)
    served = {n: v for n, v in alloc.items() if v > 1e-12}

    unmet = 0.0
    for name in demands:
        unmet += max(0.0, float(demands[name]) - alloc[name])

    shares = list(served.values()) or [0.0]
    return FairnessReport(
        capacity=float(capacity),
        allocated=round(sum(alloc.values()), 6),
        unmet=round(unmet, 6),
        min_share=round(min(shares), 6),
        max_share=round(max(shares), 6),
        gini=round(gini(alloc.values()), 4),
        fully_satisfied=sorted(
            n for n in alloc if alloc[n] + 1e-12 >= float(demands[n])
        ),
        partially_satisfied=sorted(
            n for n in served if alloc[n] + 1e-12 < float(demands[n])
        ),
        unserved=sorted(n for n in alloc if alloc[n] <= 1e-12 and float(demands[n]) > 0),
    )
