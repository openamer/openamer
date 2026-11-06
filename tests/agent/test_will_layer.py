"""DIR-13: the will layer must compute what it claims, on real CPU words."""

from __future__ import annotations

import pytest

from agent.will_layer import (
    MASK,
    WIDTH_BITS,
    Op,
    Will,
    apply_will,
    describe,
    from_expression,
)


def test_unknown_verb_is_rejected() -> None:
    with pytest.raises(ValueError, match="unknown verb"):
        Op("MULTIPLY", "acc", 1, 2)


def test_register_names_must_be_identifiers() -> None:
    with pytest.raises(ValueError):
        Op("MOV", "not a register", 1)


def test_a_will_needs_an_operation() -> None:
    with pytest.raises(ValueError):
        Will("empty", [])


def test_mov_then_xor_matches_python() -> None:
    w = Will("xor", [Op("MOV", "a", 0b1010), Op("MOV", "b", 0b0110), Op("XOR", "r", "a", "b")])
    regs = apply_will(w)
    assert regs["r"] == 0b1010 ^ 0b0110


def test_and_or_shift_subtract_match_python() -> None:
    cases = [
        (("AND", 0b1100, 0b1010), 0b1100 & 0b1010),
        (("OR", 0b1100, 0b1010), 0b1100 | 0b1010),
        (("SHL", 0b0011, 3), 0b0011 << 3),
        (("SHR", 0b11000, 2), 0b11000 >> 2),
        (("ADD", 7, 5), 12),
        (("SUB", 7, 5), 2),
    ]
    for (verb, a, b), expected in cases:
        regs = apply_will(Will(verb, [Op(verb, "r", a, b)]))
        assert regs["r"] == expected, verb


def test_width_is_enforced_like_a_real_register() -> None:
    """Python ints are unbounded; a CPU word is not. The mask is the difference."""
    regs = apply_will(Will("and", [Op("AND", "r", -1, MASK)]))
    assert regs["r"] == MASK


def test_shift_wraps_at_the_word_width() -> None:
    regs = apply_will(Will("shl", [Op("SHL", "r", 1, WIDTH_BITS + 1)]))
    assert regs["r"] == 2  # 64+1 shifts fold back to 1


def test_not_is_the_word_wise_complement() -> None:
    regs = apply_will(Will("not", [Op("NOT", "r", 0)]))
    assert regs["r"] == MASK


def test_unset_register_is_an_error_not_a_zero() -> None:
    with pytest.raises(KeyError, match="not set"):
        apply_will(Will("bad", [Op("ADD", "r", "missing", 1)]))


def test_expression_compiles_and_runs() -> None:
    will = from_expression("12 XOR 10")
    assert apply_will(will)["acc"] == 12 ^ 10


def test_expression_with_registers() -> None:
    will = from_expression("a SHL 2")
    assert apply_will(will, {"a": 3})["acc"] == 12


def test_not_expression() -> None:
    will = from_expression("NOT a")
    assert apply_will(will, {"a": 0})["acc"] == MASK


def test_malformed_expression_is_rejected() -> None:
    with pytest.raises(ValueError):
        from_expression("a b c d")
    with pytest.raises(ValueError):
        from_expression("a MOV b")


def test_describe_is_an_audit_trail() -> None:
    will = Will("demo", [Op("MOV", "a", 1), Op("ADD", "r", "a", 2)])
    assert describe(will) == ["MOV a, 1, 0", "ADD r, a, 2"]


def test_execution_does_not_mutate_the_callers_registers() -> None:
    regs = {"a": 5}
    apply_will(Will("x", [Op("ADD", "a", 1, 1)]), regs)
    assert regs == {"a": 5}
