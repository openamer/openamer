"""DIR-02: arbitrage detection over constant-product pools (math only)."""

from __future__ import annotations

import pytest

from agent.defi_arbitrage import (
    MAX_FEE_BPS,
    Pool,
    closes,
    find_best_cycle,
    optimal_size,
    simulate,
    spread_by_token,
)


def _pool(name, tin, tout, rin, rout, fee=0.0) -> Pool:
    return Pool(name=name, token_in=tin, token_out=tout, reserve_in=rin, reserve_out=rout, fee_bps=fee)


def test_quote_is_the_constant_product_output() -> None:
    p = _pool("a", "USDC", "WETH", 100_000, 50)
    # 1000 in, no fee: 1000*50 / (100000+1000)
    assert p.quote(1000) == pytest.approx(1000 * 50 / 101_000)


def test_fee_reduces_the_output() -> None:
    free = _pool("a", "USDC", "WETH", 100_000, 50, fee=0)
    paid = _pool("b", "USDC", "WETH", 100_000, 50, fee=30)
    assert paid.quote(1000) < free.quote(1000)
    assert paid.quote(0) == 0.0


def test_a_balanced_market_offers_no_opportunity() -> None:
    """Same price both ways: nothing to take. The classic false positive."""
    a_to_b = _pool("a2b", "A", "B", 1_000_000, 1_000_000)
    b_to_a = _pool("b2a", "B", "A", 1_000_000, 1_000_000)
    assert find_best_cycle([a_to_b, b_to_a], "A", 1000) is None


def test_fees_alone_remove_a_thin_edge() -> None:
    """A 0.2% mispricing is not an opportunity against 2 x 0.3% fees."""
    a_to_b = _pool("a2b", "A", "B", 1_000_000, 1_002_000, fee=30)
    b_to_a = _pool("b2a", "B", "A", 1_000_000, 998_000, fee=30)
    assert find_best_cycle([a_to_b, b_to_a], "A", 1000) is None


def test_a_two_hop_cycle_is_found_and_sized() -> None:
    a_to_b = _pool("a2b", "A", "B", 1_000_000, 1_100_000)  # B cheap here
    b_to_a = _pool("b2a", "B", "A", 1_000_000, 1_000_000)
    result = find_best_cycle([a_to_b, b_to_a], "A", 1000)
    assert result is not None
    assert result.path == ["a2b", "b2a"]
    assert result.profitable
    assert result.amount_out > result.amount_in


def test_a_three_hop_cycle_is_found() -> None:
    """Regression: the middle pool must lead to a third token, not back to A."""
    a_to_b = _pool("a2b", "A", "B", 1_000_000, 1_000_000)
    b_to_c = _pool("b2c", "B", "C", 1_000_000, 1_200_000)  # C cheap in B terms
    c_to_a = _pool("c2a", "C", "A", 1_000_000, 1_000_000)
    result = find_best_cycle([a_to_b, b_to_c, c_to_a], "A", 1000)
    assert result is not None
    assert result.path == ["a2b", "b2c", "c2a"]
    assert len(result.hops) == 3
    assert result.profitable


def test_simulate_rejects_a_broken_chain() -> None:
    a_to_b = _pool("a2b", "A", "B", 1000, 1000)
    wrong = _pool("x2y", "X", "Y", 1000, 1000)
    with pytest.raises(ValueError, match="chain broken"):
        simulate([a_to_b, wrong], "A", 10)


def test_closes_requires_returning_to_the_start_token() -> None:
    a_to_b = _pool("a2b", "A", "B", 1000, 1000)
    b_to_a = _pool("b2a", "B", "A", 1000, 1000)
    assert closes([a_to_b, b_to_a], "A")
    assert not closes([a_to_b], "A")


def test_optimal_size_stays_within_the_cap_and_is_profitable() -> None:
    a_to_b = _pool("a2b", "A", "B", 1_000_000, 1_100_000)
    b_to_a = _pool("b2a", "B", "A", 1_000_000, 1_000_000)
    cycle = [a_to_b, b_to_a]
    size = optimal_size(cycle, "A", max_amount=10_000)
    assert 0 < size <= 10_000
    assert simulate(cycle, "A", size).profit >= 0


def test_optimal_size_returns_zero_when_nothing_is_profitable() -> None:
    a_to_b = _pool("a2b", "A", "B", 1_000_000, 1_000_000)
    b_to_a = _pool("b2a", "B", "A", 1_000_000, 1_000_000)
    assert optimal_size([a_to_b, b_to_a], "A", max_amount=10_000) == 0.0


def test_invalid_pools_are_rejected() -> None:
    with pytest.raises(ValueError):
        _pool("bad", "A", "B", 0, 1000)
    with pytest.raises(ValueError):
        _pool("bad", "A", "B", 1000, 1000, fee=MAX_FEE_BPS)
    with pytest.raises(ValueError, match="token_in == token_out"):
        _pool("bad", "A", "A", 1000, 1000)


def test_spread_by_token_sorts_implied_prices() -> None:
    pools = [
        _pool("p1", "A", "B", 100, 200),
        _pool("p2", "A", "B", 100, 150),
    ]
    assert spread_by_token(pools) == {"A": [1.5, 2.0]}
