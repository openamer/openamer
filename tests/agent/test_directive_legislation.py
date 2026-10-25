"""DIR-16: directive evaluation and mutation proposals."""

from __future__ import annotations

from agent.directive_engine import ENFORCED, NOT_IMPLEMENTED, PARTIAL, RESEARCH, audit
from agent.directive_legislation import (
    IMPLEMENT,
    NOT_CODE_REACHABLE,
    REPAIR,
    RETIRE,
    evaluate,
    propose,
    summary,
)


def _row(did: str, status: str, checked=None, note: str = "") -> dict:
    return {"id": did, "status": status, "evidence": [], "checked": checked, "note": note}


def test_every_directive_gets_a_verdict() -> None:
    result = audit()
    verdicts = evaluate(result)
    assert len(verdicts) == result["directives"]
    assert [v.directive_id for v in verdicts] == sorted(v.directive_id for v in verdicts)


def test_missing_code_is_blocked() -> None:
    v = evaluate({"directives": 1, "rows": [_row("DIR-99", NOT_IMPLEMENTED)]})[0]
    assert v.blocked and "no code" in v.reason


def test_partial_and_research_are_not_blocked() -> None:
    rows = [_row("DIR-06", RESEARCH), _row("DIR-21", PARTIAL)]
    verdicts = evaluate({"directives": 2, "rows": rows})
    assert not any(v.blocked for v in verdicts)


def test_a_failing_check_blocks_even_when_code_exists() -> None:
    v = evaluate({"directives": 1, "rows": [_row("DIR-20", ENFORCED, checked=False)]})[0]
    assert v.blocked
    assert "check fails" in v.reason


def test_failing_check_proposes_repair_not_retire() -> None:
    rows = [_row("DIR-20", ENFORCED, checked=False)]
    (proposal,) = propose({"directives": 1, "rows": rows})
    assert proposal.action == REPAIR


def test_unreachable_directive_is_retired_with_its_reason() -> None:
    """Only when a caller explicitly declares it beyond code."""
    rows = [_row("DIR-99", NOT_IMPLEMENTED)]
    (proposal,) = propose({"directives": 1, "rows": rows}, not_code_reachable={"DIR-99": "needs a wet lab"})
    assert proposal.action == RETIRE
    assert "wet lab" in proposal.rationale


def test_reachable_gap_proposes_implementation() -> None:
    rows = [_row("DIR-07", NOT_IMPLEMENTED)]
    (proposal,) = propose({"directives": 1, "rows": rows})
    assert proposal.action == IMPLEMENT


def test_enforced_directive_produces_no_proposal() -> None:
    rows = [_row("DIR-03", ENFORCED, checked=True)]
    assert propose({"directives": 1, "rows": rows}) == []


def test_custom_reachability_map_overrides_the_default() -> None:
    rows = [_row("DIR-02", NOT_IMPLEMENTED)]
    (proposal,) = propose({"directives": 1, "rows": rows}, not_code_reachable={"DIR-02": "no venue access"})
    assert proposal.action == RETIRE


def test_no_directive_is_declared_beyond_code_by_default() -> None:
    """All 24 now carry code; the three hardware-bound ones are GATED, not dead.

    Retiring a GATED directive would delete the implementation that starts
    working the moment the hardware exists, so the default map is empty and a
    caller must argue for an exception explicitly.
    """
    assert NOT_CODE_REACHABLE == {}


def test_summary_counts_add_up_on_the_live_audit() -> None:
    """Every directive lands in exactly one bucket, and proposals cover the blocked ones."""
    result = audit()
    s = summary(result)
    assert s["directives"] == 24
    assert s["enforced"] + s["partial"] + s["research"] + s["gated"] + s["blocked"] == 24
    assert s["blocked"] == 0  # every directive has code as of 2026-10-25
    assert sum(s["by_action"].values()) == s["proposals"]
