"""DIR-08: max-min fair allocation — the properties that make it verifiable."""

from __future__ import annotations

import pytest

from agent.resource_fairness import gini, max_min_allocate, report


def test_equal_demands_split_evenly() -> None:
    alloc = max_min_allocate({"a": 10, "b": 10, "c": 10}, capacity=30)
    assert alloc == {"a": 10.0, "b": 10.0, "c": 10.0}


def test_scarce_capacity_is_shared_equally() -> None:
    alloc = max_min_allocate({"a": 100, "b": 100}, capacity=50)
    assert alloc["a"] == alloc["b"] == 25.0


def test_small_demand_is_satisfied_first_and_the_rest_split() -> None:
    """Max-min: the light asker is filled, the heavy ones share what is left."""
    alloc = max_min_allocate({"small": 5, "big1": 100, "big2": 100}, capacity=55)
    assert alloc["small"] == 5.0
    assert alloc["big1"] == alloc["big2"] == 25.0
    assert sum(alloc.values()) == pytest.approx(55.0)


def test_never_allocates_more_than_demanded() -> None:
    alloc = max_min_allocate({"a": 3, "b": 3}, capacity=1000)
    assert sum(alloc.values()) == pytest.approx(6.0)


def test_zero_capacity_allocates_nothing() -> None:
    assert max_min_allocate({"a": 5}, capacity=0) == {"a": 0.0}


def test_zero_demand_is_not_reported_as_unserved() -> None:
    r = report({"a": 0, "b": 10}, capacity=10)
    assert "a" not in r.unserved
    assert r.unserved == []


def test_deterministic_across_key_order() -> None:
    one = max_min_allocate({"b": 10, "a": 20, "c": 5}, capacity=25)
    two = max_min_allocate({"c": 5, "a": 20, "b": 10}, capacity=25)
    assert one == two


def test_negative_inputs_are_rejected() -> None:
    with pytest.raises(ValueError):
        max_min_allocate({"a": -1}, capacity=10)
    with pytest.raises(ValueError):
        max_min_allocate({"a": 1}, capacity=-5)


def test_gini_extremes() -> None:
    assert gini([10, 10, 10, 10]) == pytest.approx(0.0)
    assert gini([0, 0, 0, 100]) > 0.7
    assert gini([]) == 0.0


def test_report_is_self_consistent() -> None:
    r = report({"a": 100, "b": 100}, capacity=30)
    assert r.allocated == pytest.approx(30.0, abs=1e-6)
    assert r.unmet == pytest.approx(170.0, abs=1e-6)
    assert r.min_share == r.max_share  # even split
    assert r.partially_satisfied == ["a", "b"]
    assert r.fair is True


def test_unallocated_capacity_with_unmet_demand_is_not_fair() -> None:
    """A report that leaves the pool partly unused while someone is short is
    internally inconsistent, and ``fair`` must say so."""
    r = report({"a": 100}, capacity=1000)
    assert r.unmet == 0.0  # nothing left over: the demand was met
    assert r.fair is True
