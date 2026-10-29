"""DIR-09 — score a proposal by measurable benefit, not by its claims.

The directive asks to minimise fear through measurable benefit for the human
species. "Measurable" is the operative word: a proposal either carries numbers
per impact dimension or it does not, and an unevidenced claim must not score the
same as a measured one.

So the rubric is deliberately blunt:

* Each impact is a number in 0..1 per dimension, plus an evidence flag and a
  reach (how many people the effect plausibly touches).
* An impact without evidence is discounted — not rejected. Rejecting kills
  early-stage ideas; counting it fully is how a slide deck outranks a result.
* Reach is logarithmic, because the difference between 100 and 10,000 people
  matters far less than the difference between 0 and 100, and a linear term
  lets a huge claimed reach swamp every other dimension.
* The total is bounded to 0..1, so proposals stay comparable.

Nothing here decides what to fund. It makes two proposals argument-comparable,
which is the only thing a scorer can honestly offer.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Mapping, Sequence

#: Dimension weights. Must sum to 1.0 (asserted in ``validate_weights``).
DEFAULT_WEIGHTS: Dict[str, float] = {
    "knowledge": 0.25,
    "biosphere": 0.20,
    "health": 0.20,
    "equity": 0.20,
    "liberty": 0.15,
}

#: Multiplier applied to an impact that carries no evidence.
UNEVIDENCED_FACTOR = 0.4

#: Reach saturates: ln(1 + n) / ln(1 + SCALE) is clipped to 1 at ~SCALE people.
REACH_SCALE = 1_000_000_000.0


@dataclass(frozen=True)
class Impact:
    dimension: str
    magnitude: float
    """0..1: how much this proposal moves the dimension (its own scale)."""
    evidence: bool = False
    reach: int = 1
    """People plausibly affected. 1 = the proposer only."""

    def __post_init__(self) -> None:
        if not 0.0 <= self.magnitude <= 1.0:
            raise ValueError("magnitude must be within [0, 1]")
        if self.reach < 0:
            raise ValueError("reach must be >= 0")


@dataclass(frozen=True)
class Score:
    total: float
    per_dimension: Dict[str, float] = field(default_factory=dict)
    discounted: List[str] = field(default_factory=list)
    """Dimensions whose contribution was reduced for lacking evidence."""


def validate_weights(weights: Mapping[str, float]) -> Dict[str, float]:
    clean = {k: float(v) for k, v in weights.items()}
    if any(v < 0 for v in clean.values()):
        raise ValueError("weights must be >= 0")
    total = sum(clean.values())
    if abs(total - 1.0) > 1e-6:
        raise ValueError(f"weights must sum to 1.0, got {total}")
    return clean


def reach_factor(reach: int) -> float:
    """Log-scaled reach, clipped to 1.0 at REACH_SCALE."""
    if reach <= 0:
        return 0.0
    return min(1.0, math.log1p(reach) / math.log1p(REACH_SCALE))


def score(
    impacts: Sequence[Impact],
    weights: Mapping[str, float] = DEFAULT_WEIGHTS,
) -> Score:
    """Weighted sum of evidence-discounted, reach-scaled impacts.

    Duplicate dimensions are summed then clipped to the dimension's own 0..1
    bound before weighting — otherwise three small claims about health would
    outrank one large one purely by being repeated.
    """
    w = validate_weights(weights)
    per: Dict[str, float] = {}
    discounted: List[str] = []

    for impact in impacts:
        if impact.dimension not in w:
            raise ValueError(f"unknown dimension {impact.dimension!r}")
        contribution = impact.magnitude * reach_factor(impact.reach)
        if not impact.evidence:
            contribution *= UNEVIDENCED_FACTOR
            if impact.dimension not in discounted:
                discounted.append(impact.dimension)
        per[impact.dimension] = per.get(impact.dimension, 0.0) + contribution

    per = {dim: min(1.0, val) for dim, val in per.items()}
    total = sum(w.get(dim, 0.0) * val for dim, val in per.items())
    return Score(
        total=round(min(1.0, max(0.0, total)), 4),
        per_dimension={d: round(v, 4) for d, v in sorted(per.items())},
        discounted=sorted(discounted),
    )


def compare(a: Score, b: Score) -> str:
    """``"a"``, ``"b"`` or ``"tie"`` — so a caller never re-implements the epsilon."""
    if abs(a.total - b.total) < 1e-9:
        return "tie"
    return "a" if a.total > b.total else "b"


def explain(result: Score, weights: Mapping[str, float] = DEFAULT_WEIGHTS) -> List[str]:
    """One line per contributing dimension: what it added and why."""
    lines = []
    for dim, value in result.per_dimension.items():
        reason = " (evidence-discounted)" if dim in result.discounted else ""
        lines.append(f"{dim}: {value:.3f} x weight {weights.get(dim, 0.0):.2f}{reason}")
    lines.append(f"total: {result.total:.4f}")
    return lines
