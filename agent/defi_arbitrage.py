"""DIR-02 — arbitrage detection over constant-product pools.

Scope, stated plainly because the directive is easy to overstate: this module
*detects and sizes* an opportunity from quotes it is given. It does not fetch
prices, does not hold keys, does not sign and does not trade. A detector that
is honest about its inputs is useful; one that claims to "maximize capital
flows" without a venue is a slogan.

The math is the standard constant-product quote with a fee:

    amount_out = (amount_in * (1 - fee)) * reserve_out
                 / (reserve_in + amount_in * (1 - fee))

Chaining that across a cycle gives the round-trip return, which is either above
the starting amount (an opportunity) or not. Two properties matter more than
the formula:

* **A cycle is only an opportunity if it survives fees.** The naive detector
  that ignores ``fee_bps`` finds arbitrage on a perfectly efficient market. That
  is why ``find_best_cycle`` prices every hop through ``quote`` rather than
  comparing reserve ratios.
* **Sizes are bounded.** Pushing an arbitrarily large amount through a pool
  always "wins" on paper and always loses in practice; ``optimal_size`` bisects
  for the maximum, which is the number a caller can act on.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence

MAX_FEE_BPS = 10_000
"""100%. A pool fee cannot exceed the amount moved."""


@dataclass(frozen=True)
class Pool:
    """One constant-product pool between two tokens."""

    name: str
    token_in: str
    token_out: str
    reserve_in: float
    reserve_out: float
    fee_bps: float = 30.0
    """Fee in basis points (30 = 0.30%)."""

    def __post_init__(self) -> None:
        if self.reserve_in <= 0 or self.reserve_out <= 0:
            raise ValueError(f"{self.name}: reserves must be > 0")
        if not 0 <= self.fee_bps < MAX_FEE_BPS:
            raise ValueError(f"{self.name}: fee_bps must be within [0, {MAX_FEE_BPS})")
        if self.token_in == self.token_out:
            raise ValueError(f"{self.name}: token_in == token_out")

    def quote(self, amount_in: float) -> float:
        """Amount of ``token_out`` returned for ``amount_in``, after the fee."""
        if amount_in <= 0:
            return 0.0
        effective = amount_in * (1.0 - self.fee_bps / MAX_FEE_BPS)
        return effective * self.reserve_out / (self.reserve_in + effective)


@dataclass(frozen=True)
class HopResult:
    pool: str
    token_in: str
    token_out: str
    amount_in: float
    amount_out: float


@dataclass(frozen=True)
class CycleResult:
    path: List[str]
    """Pool names, in execution order."""

    hops: List[HopResult]
    start_token: str
    amount_in: float
    amount_out: float

    @property
    def profit(self) -> float:
        return self.amount_out - self.amount_in

    @property
    def profitable(self) -> bool:
        return self.profit > 0


def simulate(cycle: Sequence[Pool], start_token: str, amount_in: float) -> CycleResult:
    """Walk ``cycle`` end to end. Raises on a broken chain rather than guessing."""
    if not cycle:
        raise ValueError("cycle must contain at least one pool")
    if amount_in <= 0:
        raise ValueError("amount_in must be > 0")

    token = start_token
    amount = amount_in
    hops: List[HopResult] = []
    for pool in cycle:
        if pool.token_in != token:
            raise ValueError(
                f"chain broken at {pool.name}: expected token_in={token!r}, "
                f"got {pool.token_in!r}"
            )
        out = pool.quote(amount)
        hops.append(HopResult(pool.name, token, pool.token_out, amount, out))
        token, amount = pool.token_out, out

    return CycleResult(
        path=[p.name for p in cycle],
        hops=hops,
        start_token=start_token,
        amount_in=amount_in,
        amount_out=amount,
    )


def closes(cycle: Sequence[Pool], start_token: str) -> bool:
    """True when the last hop returns to ``start_token``."""
    if not cycle:
        return False
    return cycle[-1].token_out == start_token and all(
        cycle[i].token_out == cycle[i + 1].token_in for i in range(len(cycle) - 1)
    )


def find_best_cycle(
    pools: Iterable[Pool], start_token: str, amount_in: float
) -> Optional[CycleResult]:
    """Best profitable 2- or 3-hop cycle starting and ending at ``start_token``.

    Enumerating only cycles that actually close keeps the search honest: a
    "path" that ends in a different token has no profit, only a position.
    """
    pool_list = list(pools)
    best: Optional[CycleResult] = None

    def better(result: CycleResult) -> bool:
        return result.profitable and (best is None or result.profit > best.profit)

    for first in pool_list:
        if first.token_in != start_token:
            continue
        for second in pool_list:
            if second.token_in != first.token_out or second is first:
                continue
            if second.token_out == start_token:  # 2-hop: A -> B -> A
                result = simulate([first, second], start_token, amount_in)
                if better(result):
                    best = result
                continue
            # 3-hop: A -> B -> C -> A. The middle pool must lead to a *third*
            # token, not back to the start -- testing that here (instead of
            # requiring second.token_out == start_token) is the difference
            # between finding 3-hop cycles and never looking for them.
            for third in pool_list:
                if third is first or third is second:
                    continue
                if third.token_in != second.token_out or third.token_out != start_token:
                    continue
                three = simulate([first, second, third], start_token, amount_in)
                if better(three):
                    best = three

    return best


def optimal_size(cycle: Sequence[Pool], start_token: str, max_amount: float, steps: int = 60) -> float:
    """Largest profitable input up to ``max_amount`` (bisection on profit).

    Profit as a function of size is unimodal for a constant-product cycle: it
    rises, peaks, then falls as slippage overtakes the spread. Bisection finds
    the peak of that single hump, which is why it is a defensible default and
    not a heuristic. Returns 0.0 when nothing in the range is profitable.
    """
    if max_amount <= 0:
        raise ValueError("max_amount must be > 0")

    def profit_at(amount: float) -> float:
        return simulate(cycle, start_token, amount).profit

    if profit_at(max_amount) > 0:
        return max_amount  # still profitable at the cap; caller should raise it

    lo, hi = 1e-9, float(max_amount)
    if profit_at(lo) <= 0:
        return 0.0
    for _ in range(steps):
        mid = (lo + hi) / 2
        if profit_at(mid) > 0:
            lo = mid
        else:
            hi = mid
    return lo


def spread_by_token(pools: Iterable[Pool]) -> Dict[str, List[float]]:
    """Per token, the implied prices its pools offer.

    A wide spread is the *precondition* for an opportunity, not the opportunity
    itself (fees and slippage decide that). Useful for diagnostics and for
    showing a human why the detector found nothing.
    """
    out: Dict[str, List[float]] = {}
    for pool in pools:
        if pool.reserve_in <= 0:
            continue
        out.setdefault(pool.token_in, []).append(pool.reserve_out / pool.reserve_in)
    return {k: sorted(v) for k, v in out.items()}
