"""DIR-11: the simulator must behave like the mathematics, not like a demo."""

from __future__ import annotations

import math

import pytest

from agent.quantum_sim import (
    MAX_QUBITS,
    PauliTerm,
    ansatz,
    cnot,
    expectation,
    h,
    two_qubit_model,
    normalize,
    probabilities,
    ry,
    vqe,
    x,
    zero_state,
)


def test_zero_state_is_normalised() -> None:
    s = zero_state(3)
    assert len(s) == 8
    assert probabilities(s)[0] == pytest.approx(1.0)
    assert sum(probabilities(s)) == pytest.approx(1.0)


def test_qubit_limit_is_enforced() -> None:
    with pytest.raises(ValueError, match="MAX_QUBITS"):
        zero_state(MAX_QUBITS + 1)


def test_hadamard_makes_an_even_superposition() -> None:
    s = h(zero_state(1), 1, 0)
    probs = probabilities(s)
    assert probs[0] == pytest.approx(0.5)
    assert probs[1] == pytest.approx(0.5)


def test_x_flips_the_basis_state() -> None:
    assert probabilities(x(zero_state(1), 1, 0))[1] == pytest.approx(1.0)


def test_bell_state_has_correlated_outcomes() -> None:
    """H then CNOT: only |00> and |11> appear, each at one half."""
    s = h(zero_state(2), 2, 0)
    s = cnot(s, 2, 0, 1)
    probs = probabilities(s)
    assert probs[0] == pytest.approx(0.5)
    assert probs[3] == pytest.approx(0.5)
    assert probs[1] == pytest.approx(0.0)
    assert probs[2] == pytest.approx(0.0)


def test_ry_rotates_by_the_expected_angle() -> None:
    s = ry(zero_state(1), 1, 0, math.pi / 2)
    assert probabilities(s)[0] == pytest.approx(0.5)


def test_cnot_rejects_identical_qubits() -> None:
    with pytest.raises(ValueError):
        cnot(zero_state(2), 2, 0, 0)


def test_cnot_rejects_out_of_range_qubit() -> None:
    with pytest.raises(ValueError, match="out of range"):
        cnot(zero_state(2), 2, 0, 5)


def test_expectation_of_identity_is_one() -> None:
    assert expectation(zero_state(2), [PauliTerm(1.0, "II")]) == pytest.approx(1.0)


def test_expectation_of_z_on_ground_state_is_one() -> None:
    assert expectation(zero_state(1), [PauliTerm(1.0, "Z")]) == pytest.approx(1.0)


def test_pauli_string_rejects_unknown_letters() -> None:
    with pytest.raises(ValueError, match="invalid Pauli"):
        PauliTerm(1.0, "AB")


def test_pauli_length_must_match_qubit_count() -> None:
    with pytest.raises(ValueError, match="must have length"):
        expectation(zero_state(2), [PauliTerm(1.0, "Z")])


def test_ansatz_parameter_count_is_checked() -> None:
    with pytest.raises(ValueError, match="expected"):
        ansatz(2, [0.1], depth=1)


def test_vqe_finds_the_minimum_of_the_model_brute_force() -> None:
    """The optimiser must reach the same minimum an exhaustive sweep finds.

    This is the real claim: for a two-parameter ansatz, a grid of 9x9 over
    [0, 2pi) is an exhaustive search, so VQE has no excuse to miss the floor.
    No chemistry statement is made — the model's coefficients are hand-tabulated.
    """
    terms = two_qubit_model(0.735)
    grid = 9
    best = min(
        expectation(ansatz(2, [a, b], 1), terms)
        for a in [2 * math.pi * i / grid for i in range(grid)]
        for b in [2 * math.pi * i / grid for i in range(grid)]
    )
    energy, params = vqe(terms, n=2, depth=1, grid=grid, sweeps=3)
    assert energy == pytest.approx(best, abs=1e-9)
    assert len(params) == 2


def test_vqe_never_reports_above_the_reference_state() -> None:
    terms = two_qubit_model()
    reference = expectation(zero_state(2), terms)
    energy, _ = vqe(terms, n=2, depth=1, grid=5, sweeps=2)
    assert energy <= reference + 1e-9


def test_normalize_rescales() -> None:
    out = normalize([2 + 0j, 0j])
    assert sum(probabilities(out)) == pytest.approx(1.0)


def test_normalize_rejects_the_zero_vector() -> None:
    with pytest.raises(ValueError):
        normalize([0j, 0j])
