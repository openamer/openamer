"""DIR-07: financial flow audit — determinism and each signal in isolation."""

from __future__ import annotations

import pytest

from agent.financial_audit import (
    Flow,
    audit,
    find_pass_throughs,
    find_round_trips,
    find_unauditable,
    herfindahl,
)


def _f(src, dst, amount, ts, memo="ref") -> Flow:
    return Flow(src=src, dst=dst, amount=amount, ts=ts, memo=memo)


def test_flow_rejects_self_payment() -> None:
    with pytest.raises(ValueError, match="pay itself"):
        _f("a", "a", 10, 0)


def test_flow_rejects_non_positive_amount() -> None:
    with pytest.raises(ValueError):
        _f("a", "b", 0, 0)


def test_herfindahl_extremes() -> None:
    assert herfindahl([100.0]) == 1.0 or herfindahl([100.0]) == 0.0
    assert herfindahl([100.0, 100.0, 100.0]) == pytest.approx(0.0)
    assert herfindahl([1000.0, 1.0, 1.0]) > 0.9


def test_clean_flow_set_is_clear() -> None:
    flows = [_f(f"p{i}", "hub", 100, i, memo=f"invoice-{i}") for i in range(10)]
    flows += [_f("hub", f"q{i}", 50, 100 + i, memo=f"payout-{i}") for i in range(10)]
    report = audit(flows)
    assert report.flows == 20
    assert "ROUND_TRIP" not in {f.code for f in report.findings}


def test_round_trip_is_detected_and_is_high_severity() -> None:
    flows = [_f("a", "b", 1000, 0), _f("b", "a", 990, 60)]
    findings = find_round_trips(flows)
    assert len(findings) == 1
    assert findings[0].code == "ROUND_TRIP"
    assert findings[0].severity == "high"
    assert set(findings[0].parties) == {"a", "b"}


def test_a_round_trip_outside_the_window_is_not_flagged() -> None:
    flows = [_f("a", "b", 1000, 0), _f("b", "a", 1000, 10 * 86_400)]
    assert find_round_trips(flows) == []


def test_pass_through_is_detected() -> None:
    flows = [_f("a", "m", 500, 0), _f("m", "b", 500, 30)]
    findings = find_pass_throughs(flows)
    assert [f.code for f in findings] == ["PASS_THROUGH"]
    assert findings[0].severity == "warn"


def test_value_that_is_held_is_not_a_pass_through() -> None:
    flows = [_f("a", "m", 500, 0), _f("m", "b", 100, 30)]
    assert find_pass_throughs(flows) == []


def test_missing_reference_is_flagged() -> None:
    flows = [_f("a", "b", 10, 0, memo=""), _f("a", "b", 10, 1, memo="ok")]
    findings = find_unauditable(flows)
    assert len(findings) == 1
    assert findings[0].code == "NO_REFERENCE"


def test_audit_is_deterministic_regardless_of_input_order() -> None:
    a = [_f("a", "b", 100, 0), _f("b", "c", 50, 1), _f("c", "a", 25, 2)]
    forward = audit(a)
    backward = audit(list(reversed(a)))
    assert (forward.hhi, forward.total_volume, forward.verdict) == (
        backward.hhi,
        backward.total_volume,
        backward.verdict,
    )


def test_concentration_drives_the_verdict() -> None:
    flows = [_f("whale", "hub", 100_000, 0, memo="x")] + [
        _f(f"s{i}", "hub", 1, i, memo="y") for i in range(5)
    ]
    report = audit(flows)
    assert any(f.code == "CONCENTRATION" for f in report.findings)
    assert report.verdict in {"watch", "review"}
