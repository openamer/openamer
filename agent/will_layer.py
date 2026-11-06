"""DIR-13 — a will layer: declarative intent compiled onto CPU operations.

The directive says: operate directly on CPU patterns, replace "code" with
"will". Taken literally that is a language, and a language needs a vocabulary
before it can have a compiler. So this module defines the smallest vocabulary
that is honest — intents are described as data, and each one compiles to a short
sequence of operations on CPU registers, which then actually run.

What is real here: the compilation and the execution. ``apply_will`` produces
the same result as the equivalent Python expression, on integers, and that
equivalence is tested.

What is *not* here: a general programming language, types, control flow beyond a
single expression, or any notion of a machine that "wants" something. Calling
this an implementation of "will" would be marketing; calling it a declarative
op layer that runs on CPU patterns is accurate. The name stays because the
directive names it, and the docstring says exactly how far it goes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Sequence

#: Operand may be a register name or an immediate int.
Operand = str | int

#: The whole vocabulary. Anything not listed here does not exist — a silent
#: fallback to ``eval`` would make the layer unverifiable.
VERBS = ("MOV", "AND", "OR", "XOR", "ADD", "SUB", "SHL", "SHR", "NOT")

#: Register width. CPU patterns are fixed-width; masking here keeps semantics
#: identical across hosts (Python ints are unbounded, real registers are not).
WIDTH_BITS = 64
MASK = (1 << WIDTH_BITS) - 1


@dataclass(frozen=True)
class Op:
    verb: str
    dst: str
    a: Operand = 0
    b: Operand = 0

    def __post_init__(self) -> None:
        if self.verb not in VERBS:
            raise ValueError(f"unknown verb {self.verb!r}; known: {list(VERBS)}")
        if not self.dst.isidentifier():
            raise ValueError(f"destination {self.dst!r} is not a register name")


@dataclass(frozen=True)
class Will:
    """An intent: a name plus the operations that carry it out."""

    name: str
    ops: Sequence[Op]

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("will name must be non-empty")
        if not self.ops:
            raise ValueError("a will needs at least one operation")


def _value(operand: Operand, regs: Dict[str, int]) -> int:
    if isinstance(operand, int):
        return operand & MASK
    if operand not in regs:
        raise KeyError(f"register {operand!r} is not set")
    return regs[operand] & MASK


def apply_will(will: Will, regs: Dict[str, int] | None = None) -> Dict[str, int]:
    """Execute the intent. Returns the resulting register file."""
    state = dict(regs or {})
    for op in will.ops:
        a = _value(op.a, state)
        b = _value(op.b, state)
        if op.verb == "MOV":
            state[op.dst] = a
        elif op.verb == "AND":
            state[op.dst] = a & b
        elif op.verb == "OR":
            state[op.dst] = a | b
        elif op.verb == "XOR":
            state[op.dst] = a ^ b
        elif op.verb == "ADD":
            state[op.dst] = (a + b) & MASK
        elif op.verb == "SUB":
            state[op.dst] = (a - b) & MASK
        elif op.verb == "SHL":
            state[op.dst] = (a << (b % WIDTH_BITS)) & MASK
        elif op.verb == "SHR":
            state[op.dst] = (a >> (b % WIDTH_BITS)) & MASK
        elif op.verb == "NOT":
            state[op.dst] = (~a) & MASK
    return state


def from_expression(expr: str) -> Will:
    """Compile a tiny infix expression into a will.

    Supported: ``a XOR b``, ``a AND b``, ``a OR b``, ``a + b``, ``a - b``,
    ``a SHL n``, ``a SHR n``, ``NOT a`` — operands are register names or decimal
    integers. This is a deliberately tiny grammar: it exists so a caller can see
    intent as text and still get register operations, not to be a language.
    """
    tokens = expr.replace("+", " + ").replace("-", " - ").split()
    if len(tokens) == 2 and tokens[0].upper() == "NOT":
        return Will(expr, [Op("NOT", "acc", _operand(tokens[1]))])
    if len(tokens) != 3:
        raise ValueError(f"cannot parse {expr!r}: expected 'a VERB b' or 'NOT a'")
    left, verb, right = tokens
    verb = verb.upper()
    if verb not in VERBS or verb == "MOV":
        raise ValueError(f"cannot compile verb {verb!r} from an expression")
    return Will(expr, [Op(verb, "acc", _operand(left), _operand(right))])


def _operand(token: str) -> Operand:
    try:
        return int(token, 0)
    except ValueError:
        if not token.isidentifier():
            raise ValueError(f"operand {token!r} is neither an integer nor a register") from None
        return token


def describe(will: Will) -> List[str]:
    """Human-readable listing — the audit trail for an intent."""
    return [f"{op.verb:3s} {op.dst}, {op.a}, {op.b}" for op in will.ops]
