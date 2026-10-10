"""Tests for the Darwin gate's verdict/reason parser (scripts/darwin_gate.py).

The gate is the safety layer every autonomous proposal passes through, so its
parser has to be pinned: a verdict read wrongly lets work through that should not
run, and a reason read wrongly turns the layer into a black box.

Measured 2026-10-10 over 100 live decisions: the verdicts were sane (70 APPROVE /
15 NEEDS_MORE_INFO / 15 REJECT) but 87 of the 100 reasons were the placeholder
"explicit decision anchor". The cause was a contradiction between the prompt and
the parser, pinned below.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent


def _gate_module():
    spec = importlib.util.spec_from_file_location(
        "darwin_gate", REPO / "scripts" / "darwin_gate.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def gate():
    return _gate_module()


def test_the_reason_comes_from_the_option_line_not_the_bare_anchor(gate):
    """The prompt asks for a bare DECISION line and the reason on a bullet.

    Rejecting on the anchor line only made 87 of 100 live reasons a placeholder:
    the anchor is specified WITHOUT a reason, so it never carries one.
    """
    reply = (
        "- APPROVE: safe, scoped to one script, and reversible.\n"
        "- REJECT: not needed.\n"
        "DECISION: APPROVE\n"
    )

    verdict, reason = gate._parse_verdict(reply)

    assert verdict == "APPROVE"
    assert reason.startswith("safe, scoped to one script")


def test_an_inline_reason_on_the_anchor_still_wins(gate):
    """Do not regress the shape that already worked."""
    verdict, reason = gate._parse_verdict("DECISION: REJECT - touches core tool schema\n")

    assert verdict == "REJECT"
    assert reason == "touches core tool schema"


def test_quoting_the_prompt_placeholder_is_not_a_reason(gate):
    """A model echoing `<one-sentence reason>` back has given no reason."""
    reply = "- APPROVE: <one-sentence reason>\nDECISION: APPROVE\n"

    verdict, reason = gate._parse_verdict(reply)

    assert verdict == "APPROVE"
    assert reason == "explicit decision anchor"


def test_an_unparseable_reply_stays_conservative(gate):
    """No verdict anywhere is NEEDS_MORE_INFO, never a silent APPROVE."""
    reply = "I am not sure about this one, let me think about the tradeoffs.\n"

    verdict, reason = gate._parse_verdict(reply)

    assert verdict == "NEEDS_MORE_INFO"
    assert reason


def test_the_last_anchor_wins_when_the_model_deliberates(gate):
    """The prompt forbids quoting the option names, so the model often does.

    The final answer sits at the bottom, so a scan from the end is required -
    otherwise the first quoted `APPROVE:` bullet decides the gate.
    """
    reply = (
        "- APPROVE: sounds fine\n"
        "Hmm, but scope is broad.\n"
        "- REJECT: too broad.\n"
        "DECISION: REJECT\n"
    )

    verdict, reason = gate._parse_verdict(reply)

    assert verdict == "REJECT"
    assert reason == "too broad."
