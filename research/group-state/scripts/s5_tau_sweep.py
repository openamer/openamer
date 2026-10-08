#!/usr/bin/env python3
"""The structural readout needs the state to ACTUALLY be a permutation matrix.

MEASURED FAILURE, AND WHY
-------------------------
struct_logits(S) computes <S, M_c>. That is exact ONLY if S is a permutation
matrix, where the inner product is 1 for the true element and 0 for all others.
With tau=1 the softmax over generators is diffuse (logit gap ~1 gives weights
~0.5 vs ~0.12), so each per-token mixture G_t is far from a permutation matrix
and the product diffuses toward uniform. Measured with perfect choice weights
(W=I) and tau=1: accuracy 0.095 at L=4. The readout was not wrong; the STATE was
not a permutation.

This is the same diffusion measured twice before (the abelian convolution state,
and the S_5 init dependence). It has one lever: tau.

WHAT TO MEASURE
---------------
Accuracy of the structural readout with perfect choice weights as a function of
tau. If the theory is right, low tau (sharp choices -> state = exact permutation
matrix) must give 1.000 at EVERY length, and there is no memorisation anywhere
in the pipeline: 25 choice parameters, a fixed catalogue of group matrices, and
an exact inner product.

Run:  python scripts/s5_tau_sweep.py
"""
import random
import sys

sys.path.insert(0, "scripts")
from perm_state_lab import D, PermState, _task_gen
from s5_group import ELEMENTS, NUM_GENS, matrix


def make(tau):
    m = PermState(random.Random(1), tau=tau, readout="exact")
    d = [0.0] * (NUM_GENS * NUM_GENS)
    for k in range(NUM_GENS):
        d[k * NUM_GENS + k] = 1.0
    m.W.data = d
    m.b.data = [0.0] * NUM_GENS
    return m


def accuracy(m, L, n=200, seed=0):
    rng = random.Random(seed + L)
    hit = 0
    for _ in range(n):
        xs, tg = _task_gen(rng, L)
        lo = m.forward(xs)
        hit += (max(range(len(lo)), key=lambda i: lo[i]) == tg)
    return hit / n


def state_is_permutation(m, L=6, seed=0):
    """How far is the final state from a permutation matrix?

    Distance to the nearest permutation matrix, averaged: 0.0 means the state
    is exactly an element of the group.
    """
    cat = [matrix(p) for p in ELEMENTS]
    rng = random.Random(seed)
    tot = 0.0
    n = 40
    for _ in range(n):
        xs, _ = _task_gen(rng, L)
        m.forward(xs)
        S = m._S
        best = min(sum((S[i] - M[i]) ** 2 for i in range(D)) for M in cat)
        tot += best ** 0.5
    return tot / n


def main():
    print("=" * 82)
    print("structural readout vs tau  (perfect choice weights W=I, no training)")
    print("=" * 82)
    print(f"  {'tau':>8s}{'dist-to-perm':>14s}" +
          "".join(f"{str(L) + ('*' if L > 6 else ' '):>8s}"
                  for L in (4, 6, 12, 48, 200)))
    print("  " + "-" * (22 + 8 * 5))

    for tau in (1.0, 0.3, 0.1, 0.03, 0.01, 0.003, 0.001):
        m = make(tau)
        dist = state_is_permutation(m)
        row = f"  {tau:8.3f}{dist:14.3e}"
        for L in (4, 6, 12, 48, 200):
            row += f"{accuracy(m, L):8.3f}"
        print(row)

    print()
    print("=" * 82)
    print("READING IT")
    print("=" * 82)
    print("dist-to-perm ~0  => the state IS a group element, and <S, M_c> is an")
    print("                    exact inverse, so accuracy is 1.000 at all lengths.")
    print("dist-to-perm >0  => the state is a diffuse mixture; the products have")
    print("                    drifted toward uniform and the inner product cannot")
    print("                    identify the element.")
    print("The lever is tau: sharp choices keep the state on the group.")


if __name__ == "__main__":
    main()
