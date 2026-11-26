"""Guard tests for the cross-agent benchmark harness.

These tests exist because a scorer that has never been shown to move is not a
measurement. Each one pins one way the verdict could silently become wrong:

  * a wrong answer must score False (not None, not True)
  * a right answer must score True -> the scorer is not stuck
  * a transport failure must be an ``error`` row, never a wrong answer: a dead
    provider must not look like a stupid model
  * a verifier that raises must be visible as ``verify_error``, not swallowed
  * the pass rate must be computed over *scored* rows only, so errors cannot
    inflate or deflate it
  * an identical run must not silently change the catalog signature

No network, no model, no subprocess: every subject is a stub.
"""

from __future__ import annotations

import sys
from pathlib import Path

BENCH = Path(__file__).resolve().parents[2] / "scripts" / "bench"
if str(BENCH) not in sys.path:
    sys.path.insert(0, str(BENCH))

import cross_agent  # noqa: E402


def _task(expected: int = 42) -> dict:
    return {
        "id": "stub.arith.v1",
        "kind": "arith",
        "prompt": "stub",
        "check": lambda out: out.strip() == str(expected),
    }


def _subject(text: str = "", raises: Exception | None = None) -> dict:
    def call(prompt: str) -> dict:
        if raises is not None:
            raise raises
        return {"text": text, "latency_s": 0.01}

    return {"name": "stub-subject", "label": "stub", "kind": "agent", "call": call}


def test_wrong_answer_scores_false() -> None:
    row = cross_agent.run_task(_task(), _subject("41"))
    assert row["status"] == "ok"
    assert row["passed"] is False


def test_right_answer_scores_true() -> None:
    row = cross_agent.run_task(_task(), _subject("42"))
    assert row["status"] == "ok"
    assert row["passed"] is True


def test_transport_failure_is_error_not_wrong_answer() -> None:
    row = cross_agent.run_task(_task(), _subject(raises=ConnectionError("no route")))
    assert row["status"] == "error"
    assert row["passed"] is False
    assert "no route" in row["error"]


def test_verifier_exception_is_visible() -> None:
    task = _task()
    task["check"] = lambda out: (_ for _ in ()).throw(ValueError("bad verifier"))
    row = cross_agent.run_task(task, _subject("42"))
    assert row["status"] == "verify_error"
    assert "bad verifier" in row["error"]


def test_pass_rate_uses_scored_rows_only() -> None:
    subjects = [_subject(), {**_subject(), "name": "other"}]
    rows = [
        {"subject": "stub-subject", "task": "a", "kind": "arith", "status": "ok", "passed": True, "latency_s": 1.0},
        {"subject": "stub-subject", "task": "b", "kind": "arith", "status": "error", "passed": False},
        {"subject": "other", "task": "a", "kind": "arith", "status": "ok", "passed": False, "latency_s": 2.0},
    ]
    summary = {s["subject"]: s for s in cross_agent.summarize(subjects, rows)}

    first = summary["stub-subject"]
    assert first["scored"] == 1 and first["errors"] == 1
    assert first["pass_rate_of_scored"] == 1.0, "an error must not count as a wrong answer"
    assert first["pass_rate_of_all"] == 0.5
    assert summary["other"]["pass_rate_of_scored"] == 0.0


def test_catalog_signature_is_stable_across_imports() -> None:
    assert cross_agent.catalog_signature() == cross_agent.catalog_signature()
    assert len(cross_agent.catalog_signature()) == 16


def test_ansi_escapes_are_stripped() -> None:
    dirty = "\x1b[32m42\x1b[0m\r\n"
    assert cross_agent._clean(dirty) == "42"


def test_expected_values_are_derived_not_asserted() -> None:
    """The 2026-11-26 cross-agent run exposed two broken expectations.

    Two independent agents answered 489 to a 340/8/15%/10h task whose verifier
    demanded 488 (the true value is 488.75 -- the prompt never said how to
    round), and a marbles task priced at 10 moves really costs 12. A pass rate
    built on either number measured the verifier, not the subject. These
    assertions recompute the numbers from the prompt arithmetic.
    """
    from fractions import Fraction

    from tasks import by_id

    rate = by_id("arith.rate.v1")
    exact = Fraction(320, 8) * (1 + Fraction(15, 100)) * 10
    assert exact == 460, "the task numbers must divide to a whole number"
    assert rate["check"]("460") is True
    assert rate["check"]("461") is False

    marbles = by_id("reason.multi_step.v1")
    boxes = [12, 18, 30]
    share = sum(boxes) // len(boxes)
    # Only box 3 is above the share, so it funds every deficit: the marbles that
    # change hands equal the surplus, not the surplus plus the deficits. (12 was
    # my own double-count in review, not the verifier's error -- keep the test.)
    surplus = sum(b - share for b in boxes if b > share)
    deficit = sum(share - b for b in boxes if b < share)
    assert surplus == deficit == 10
    assert marbles["check"]("10") is True
    assert marbles["check"]("12") is False


def test_audit_flags_a_rejected_consensus() -> None:
    """An audit that never fires is not an instrument.

    The 2026-11-26 defect was exactly this shape: two models agree on an answer
    the verifier refuses. Replay it with stubs and require the flag.
    """
    from verifier_audit import audit

    old_rate = {
        "id": "arith.rate.v1",
        "kind": "arith",
        "prompt": "legacy 340/8/15%/10h task",
        "check": lambda out: out.strip() == "488",
    }

    def subj(answer: str) -> dict:
        return {"name": f"stub-{answer}", "call": lambda prompt: {"text": answer}}

    flagged = audit([old_rate], [subj("489"), subj("490")])
    # different answers -> no consensus -> not a flag
    assert flagged["flagged"] == []

    both_wrong = audit([old_rate], [subj("489"), subj("489")])
    assert both_wrong["rows"][0]["state"] == "flagged:consensus_rejected"
    assert both_wrong["flagged"] == ["arith.rate.v1"]

    both_right = audit([old_rate], [subj("488"), subj("488")])
    assert both_right["rows"][0]["state"] == "ok:consensus_accepted"
    assert both_right["flagged"] == []


def test_audit_surfaces_a_raising_verifier() -> None:
    from verifier_audit import audit

    broken = {"id": "broken.v1", "kind": "code", "prompt": "x", "check": lambda out: 1 / 0}
    row = audit([broken], [{"name": "a", "call": lambda p: {"text": "1"}},
                           {"name": "b", "call": lambda p: {"text": "1"}}])
    assert row["rows"][0]["state"] == "verifier_raises"
    assert row["flagged"] == ["broken.v1"]
