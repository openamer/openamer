"""Regression tests for scripts/training/self_improve.py rule engine.

Hermetic: no network, no LLM, no live files touched. The module is exec'd (not
just AST-parsed) so a broken rule actually runs.

The bug pinned here was live on the main branch (2026-09-20): P2 tested the
WRONG match object. It guarded on `m` -- P1's `CYCLE_SECONDS` regex match --
while proposing `m.group(0)`, the CYCLE_SECONDS text itself, as the pattern for
apply_and_test() to replace. On any target whose cycle interval was under 100s
the rule therefore DELETED the interval assignment and wrote a second
`max_tokens` line in its place. Nothing downstream noticed: the patched file
still compiles, still AST-parses, and still defines loop().

Measured on the broken form, for
    CYCLE_SECONDS = 60
    max_tokens = 400
propose_improvement() returned
    [('capacity', 'CYCLE_SECONDS = 60', 'max_tokens=200', ...)]
and applying it produced
    max_tokens=200
    max_tokens = 400
"""
import importlib.util
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
TRAINING = REPO / "scripts" / "training"
sys.path.insert(0, str(TRAINING))

_spec = importlib.util.spec_from_file_location(
    "self_improve", TRAINING / "self_improve.py"
)
SI = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(SI)


def _capacity_proposals(content):
    return [p for p in SI.propose_improvement("target.py", content) if p[0] == "capacity"]


def test_p2_never_rewrites_the_cycle_interval():
    """The reported symptom: a small cycle interval must not trigger P2 at all."""
    content = "CYCLE_SECONDS = 60\nmax_tokens = 400\n"
    assert _capacity_proposals(content) == [], (
        "P2 must not fire when max_tokens is already >= 100, even if "
        "CYCLE_SECONDS is a small number"
    )


def test_p2_targets_max_tokens_when_it_is_small():
    """The rule still works for its actual purpose: a small max_tokens."""
    content = "CYCLE_SECONDS = 60\nmax_tokens = 50\n"
    props = _capacity_proposals(content)
    assert len(props) == 1, props
    kind, old, new, _why = props[0]
    assert old == "max_tokens = 50", old
    assert new == "max_tokens=200", new
    # And applying it must leave the cycle interval intact.
    patched = content.replace(old, new, 1)
    assert "CYCLE_SECONDS = 60" in patched, patched
    assert "max_tokens=200" in patched, patched
    # `max_tokens = 50` was REPLACED, so exactly one max_tokens reference remains.
    assert patched.count("max_tokens") == 1, patched


def test_p2_pattern_is_always_a_max_tokens_assignment():
    """Invariant across a range of contents: P2's `old` is never a non-max_tokens line."""
    for content in (
        "CYCLE_SECONDS = 30\nmax_tokens = 10\n",
        "max_tokens = 5\n",
        "CYCLE_SECONDS = 900\nmax_tokens = 20\n",
        "CYCLE_SECONDS = 45\n",
        "max_tokens = 99\nCYCLE_SECONDS = 12\n",
    ):
        for _kind, old, _new, _why in _capacity_proposals(content):
            assert "max_tokens" in old, (
                f"P2 proposed replacing a non-max_tokens line {old!r} for {content!r}"
            )
            assert "CYCLE_SECONDS" not in old, (
                f"P2 proposed deleting the cycle interval {old!r} for {content!r}"
            )
