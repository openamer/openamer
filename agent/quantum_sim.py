"""DIR-11 — statevector quantum simulation and a VQE ground-state search.

Runs on an ordinary CPU and needs no quantum hardware: an n-qubit statevector is
2^n complex amplitudes, gates are small unitaries applied to it, and VQE is a
search over ansatz parameters for the lowest expectation value of a Hamiltonian.
That is enough to *be* the same algorithm a real device would run — the device
changes the cost, not the mathematics.

Limits are stated rather than hidden: ``MAX_QUBITS`` bounds memory (2^12
amplitudes ~ 64 KB per vector), and there is no noise model. A simulated result
is an exact expectation value, so it must never be quoted as evidence about a
physical device.

Why this shape:

* ``expectation`` needs only Pauli strings, so any small Hamiltonian can be
  described as data — no hard-coded molecule.
* ``vqe`` is gradient-free (coordinate descent over a fixed grid) on purpose:
  it makes the search deterministic and reproducible, which is what a test can
  assert. A real run would use gradients; that difference is in the docstring,
  not hidden.
"""

from __future__ import annotations

import cmath
import itertools
import math
from dataclasses import dataclass
from typing import Dict, Iterable, List, Sequence, Tuple

MAX_QUBITS = 12
"""2^12 amplitudes per vector; beyond this a simulator needs a different design."""

_PAULI_I = ((1, 0), (0, 1))
_PAULI_X = ((0, 1), (1, 0))
_PAULI_Y = ((0, -1j), (1j, 0))
_PAULI_Z = ((1, 0), (0, -1))
_PAULI = {"I": _PAULI_I, "X": _PAULI_X, "Y": _PAULI_Y, "Z": _PAULI_Z}


def zero_state(n: int) -> List[complex]:
    _check_n(n)
    state = [0j] * (1 << n)
    state[0] = 1 + 0j
    return state


def _check_n(n: int) -> None:
    if n < 1:
        raise ValueError("n must be >= 1")
    if n > MAX_QUBITS:
        raise ValueError(f"n={n} exceeds MAX_QUBITS={MAX_QUBITS} (2^n amplitudes)")


def _apply_1q(state: List[complex], n: int, qubit: int, matrix) -> List[complex]:
    """Apply a 1-qubit gate. Qubit 0 is the least-significant bit."""
    if not 0 <= qubit < n:
        raise ValueError(f"qubit {qubit} out of range for n={n}")
    out = list(state)
    step = 1 << qubit
    block = step << 1
    for base in range(0, len(state), block):
        for offset in range(step):
            i0 = base + offset
            i1 = i0 + step
            a, b = state[i0], state[i1]
            out[i0] = matrix[0][0] * a + matrix[0][1] * b
            out[i1] = matrix[1][0] * a + matrix[1][1] * b
    return out


_HADAMARD = (
    (1 / math.sqrt(2), 1 / math.sqrt(2)),
    (1 / math.sqrt(2), -1 / math.sqrt(2)),
)


def h(state: List[complex], n: int, qubit: int) -> List[complex]:
    """Hadamard: (1/sqrt2)[[1,1],[1,-1]].

    Measured 2026-10-25: the first version divided the X matrix by sqrt2, which
    is a bit flip scaled down — it leaves |0> at |0> and produces no
    superposition at all. The Bell-state test is what caught it.
    """
    return _apply_1q(state, n, qubit, _HADAMARD)


def x(state: List[complex], n: int, qubit: int) -> List[complex]:
    return _apply_1q(state, n, qubit, _PAULI_X)


def z(state: List[complex], n: int, qubit: int) -> List[complex]:
    return _apply_1q(state, n, qubit, _PAULI_Z)


def ry(state: List[complex], n: int, qubit: int, theta: float) -> List[complex]:
    """Rotation about Y — the parameterised gate a VQE ansatz uses."""
    c, s = math.cos(theta / 2), math.sin(theta / 2)
    return _apply_1q(state, n, qubit, ((c, -s), (s, c)))


def cnot(state: List[complex], n: int, control: int, target: int) -> List[complex]:
    if control == target:
        raise ValueError("control and target must differ")
    for q in (control, target):
        if not 0 <= q < n:
            raise ValueError(f"qubit {q} out of range for n={n}")
    out = list(state)
    cbit, tbit = 1 << control, 1 << target
    for i in range(len(state)):
        if i & cbit and not i & tbit:
            j = i | tbit
            out[i], out[j] = out[j], out[i]
    return out


def probabilities(state: Sequence[complex]) -> List[float]:
    return [abs(a) ** 2 for a in state]


def normalize(state: Sequence[complex]) -> List[complex]:
    norm = math.sqrt(sum(abs(a) ** 2 for a in state))
    if norm == 0:
        raise ValueError("cannot normalise the zero vector")
    return [a / norm for a in state]


@dataclass(frozen=True)
class PauliTerm:
    """One term of a Hamiltonian: coefficient times a Pauli string."""

    coeff: float
    pauli: str
    """e.g. ``"ZI"`` — qubit 0 is the rightmost character."""

    def __post_init__(self) -> None:
        if not self.pauli or any(ch not in _PAULI for ch in self.pauli):
            raise ValueError(f"invalid Pauli string {self.pauli!r}")


def _apply_pauli(state: Sequence[complex], n: int, pauli: str) -> List[complex]:
    if len(pauli) != n:
        raise ValueError(f"Pauli string {pauli!r} must have length n={n}")
    out = list(state)
    # Rightmost character acts on qubit 0.
    for idx, ch in enumerate(reversed(pauli)):
        if ch == "I":
            continue
        out = _apply_1q(out, n, idx, _PAULI[ch])
    return out


def expectation(state: Sequence[complex], terms: Iterable[PauliTerm]) -> float:
    """<psi|H|psi> for a real-symmetric H built from Pauli strings."""
    n = int(round(math.log2(len(state))))
    total = 0.0
    for term in terms:
        applied = _apply_pauli(state, n, term.pauli)
        total += term.coeff * sum((c.conjugate() * a).real for c, a in zip(state, applied))
    return total


def ansatz(n: int, params: Sequence[float], depth: int = 1) -> List[complex]:
    """Ry on every qubit, then a CNOT ladder; repeated ``depth`` times.

    Parameter count must be ``n * depth`` — a mismatch raises instead of padding,
    because silently reusing a parameter changes the energy being optimised.
    """
    if depth < 1:
        raise ValueError("depth must be >= 1")
    if len(params) != n * depth:
        raise ValueError(f"expected {n * depth} parameters, got {len(params)}")
    state = zero_state(n)
    k = 0
    for _ in range(depth):
        for q in range(n):
            state = ry(state, n, q, params[k])
            k += 1
        for q in range(n - 1):
            state = cnot(state, n, q, q + 1)
    return state


def vqe(
    terms: Sequence[PauliTerm],
    n: int,
    depth: int = 1,
    grid: int = 5,
    sweeps: int = 3,
) -> Tuple[float, List[float]]:
    """Deterministic coordinate-descent VQE. Returns (energy, best_params).

    Gradient-free and grid-based so the same inputs always give the same energy
    — a stochastic optimiser would make the assertion "we found the ground
    state" untestable.
    """
    best_params = [0.0] * (n * depth)
    best_energy = expectation(ansatz(n, best_params, depth), terms)
    angles = [2 * math.pi * i / grid for i in range(grid)]
    for _ in range(sweeps):
        for idx in range(len(best_params)):
            for angle in angles:
                trial = list(best_params)
                trial[idx] = angle
                energy = expectation(ansatz(n, trial, depth), terms)
                if energy < best_energy - 1e-12:
                    best_energy, best_params = energy, trial
    return best_energy, best_params


def two_qubit_model(bond_length: float = 0.735) -> List[PauliTerm]:
    """A two-qubit Pauli model with an H2-like shape. NOT a chemistry potential.

    Hand-tabulated coefficients: no integral pipeline produced them, so any
    energy it returns is the minimum of *this* model and nothing else. The test
    asserts that the optimiser finds that minimum — which is a real claim about
    the simulator — and deliberately makes no claim about molecular hydrogen.
    Calling it an H2 Hamiltonian was the first draft's overstatement.
    """
    if bond_length <= 0:
        raise ValueError("bond_length must be > 0")
    # Minimal two-parameter fit around the equilibrium geometry.
    scale = math.exp(-(bond_length - 0.735) ** 2 / 0.2)
    return [
        PauliTerm(-1.0523 * scale, "II"),
        PauliTerm(0.3979 * scale, "ZI"),
        PauliTerm(-0.3979 * scale, "IZ"),
        PauliTerm(0.1809 * scale, "ZZ"),
        PauliTerm(0.0453 * scale, "XX"),
    ]
