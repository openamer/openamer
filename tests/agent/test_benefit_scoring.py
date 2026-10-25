"""DIR-09: benefit scoring — the rubric must resist being gamed."""

from __future__ import annotations

import pytest

from agent.benefit_scoring import (
    DEFAULT_WEIGHTS,
    Impact,
    compare,
    explain,
    reach_factor,
    score,
    validate_weights,
)


def test_weights_must_sum_to_one() -> None:
    with pytest.raises(ValueError, match="sum to 1.0"):
        validate_weights({"knowledge": 0.5})


def test_unknown_dimension_is_rejected() -> None:
    with pytest.raises(ValueError, match="unknown dimension"):
        score([Impact("vibes", 1.0)])


def test_magnitude_bounds_are_enforced() -> None:
    with pytest.raises(ValueError):
        Impact("health", 1.5)
    with pytest.raises(ValueError):
        Impact("health", -0.1)


def test_evidence_beats_an_equal_claim_without_evidence() -> None:
    measured = score([Impact("health", 0.8, evidence=True, reach=1_000_000)])
    claimed = score([Impact("health", 0.8, evidence=False, reach=1_000_000)])
    assert measured.total > claimed.total
    assert "health" in claimed.discounted


def test_repeating_a_small_claim_cannot_beat_one_large_claim() -> None:
    """Three weak health claims must not outweigh one strong one."""
    weak = score([Impact("health", 0.3, True, 1000)] * 3)
    strong = score([Impact("health", 1.0, True, 1000)])
    assert strong.total >= weak.total


def test_reach_saturates() -> None:
    assert reach_factor(0) == 0.0
    assert reach_factor(1) < reach_factor(1_000)
    assert reach_factor(10**12) == 1.0
    assert reach_factor(1_000_000_000) == 1.0


def test_total_is_bounded() -> None:
    everything = [Impact(d, 1.0, True, 10**12) for d in DEFAULT_WEIGHTS]
    assert score(everything).total == pytest.approx(1.0)


def test_empty_proposal_scores_zero() -> None:
    assert score([]).total == 0.0


def test_determinism_and_ordering_of_dimensions() -> None:
    impacts = [Impact("equity", 0.5, True, 100), Impact("health", 0.5, True, 100)]
    a, b = score(impacts), score(list(reversed(impacts)))
    assert a.total == b.total
    assert list(a.per_dimension) == sorted(a.per_dimension)


def test_compare_is_epsilon_safe() -> None:
    a = score([Impact("health", 0.5, True, 1000)])
    assert compare(a, a) == "tie"
    bigger = score([Impact("health", 1.0, True, 1000)])
    assert compare(a, bigger) == "b"


def test_explain_names_the_discount() -> None:
    lines = explain(score([Impact("health", 0.5, evidence=False, reach=1000)]))
    assert any("evidence-discounted" in line for line in lines)
    assert lines[-1].startswith("total:")
