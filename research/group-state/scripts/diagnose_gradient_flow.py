#!/usr/bin/env python3
"""WHERE does the gradient die in the S_5 non-commutative product?

THE SYMPTOM
-----------
Training everything together leaves per-token choice accuracy at chance
(0.198-0.214 vs 0.20). The construction is sound (freeze W=I -> 0.928 at L=4),
so there is ONE 120-way classification grade per sequence and it must be
distributed to every token through a long non-commutative matrix product.

BEFORE any fix, measure the obvious suspect: does gradient reach early tokens?
A state that is a product of T matrices has its gradient scaled by a product of
T Jacobians, so early-token gradient either vanishes (~0) or explodes.

METHOD
------
Replicate the soft backward loop exactly (it is short and fully specified in
perm_state_lab.PermState.backward) and record, per token position walked
backwards:
  * ||gS||   -- the state-gradient norm entering that step
  * ||graw|| -- the generator-choice gradient produced at that step
Both are printed from the FIRST token walked (highest position) to the LAST
(position 0), so a monotone decay is directly visible.

Run:  python scripts/diagnose_gradient_flow.py
"""
import math
import random
import sys

sys.path.insert(0, "scripts")
from perm_state_lab import D, NUM_GENS, PermState, _task_gen
from s5_group import GEN_MATRICES
from state_tracking_lab import loss_and_grad


def norm(v):
    return math.sqrt(sum(x * x for x in v))


def trace(length, seed=0):
    """Return (per_step_state_norms, per_step_choice_norms, positions).

    Step order is the BACKWARD order: index 0 is the final token, index -1 is
    the first token. So a healthy model shows roughly constant values; a
    vanishing one shows the first entries >> the last.
    """
    rng = random.Random(seed)
    xs, t = _task_gen(rng, length)

    m = PermState(random.Random(1), tau=1.0)
    for p in m.params():
        p.zero()
    _, g = loss_and_grad(m.forward(xs), t, "ce")

    gS = m.head.backward(g)
    state_norms, choice_norms = [], []
    for idx in range(len(m._cache) - 1, -1, -1):
        S_prev, a, G, xv = m._cache[idx]
        state_norms.append(norm(gS))

        # dG = gS @ S_prev^T   (same math as the real backward)
        gG = [0.0] * D
        for i in range(5):
            for k in range(5):
                acc = 0.0
                for j in range(5):
                    acc += gS[i * 5 + j] * S_prev[k * 5 + j]
                gG[i * 5 + k] = acc

        # gA_k = <gG, M_k> ; graw = softmax-grad with tau
        gA = [0.0] * NUM_GENS
        for k in range(NUM_GENS):
            Mk = GEN_MATRICES[k]
            gA[k] = sum(gG[p] for p in range(D) if Mk[p] != 0.0)
        dot = sum(gA[k] * a[k] for k in range(NUM_GENS))
        graw = [a[k] * (gA[k] - dot) / m.tau for k in range(NUM_GENS)]
        choice_norms.append(norm(graw))

        # advance gS to the previous step: dS_prev = G^T @ gS
        gS_next = [0.0] * D
        for k in range(5):
            for j in range(5):
                acc = 0.0
                for i in range(5):
                    acc += gS[i * 5 + j] * G[i * 5 + k]
                gS_next[k * 5 + j] = acc
        gS = gS_next

    return state_norms, choice_norms


def main():
    print("=" * 80)
    print("gradient flow through the non-commutative product")
    print("index 0 = LAST token walked back; last index = FIRST token")
    print("=" * 80)

    for L in (4, 8, 16, 32):
        sn, cn = trace(L, seed=3)
        print()
        print(f"  L={L}")
        print(f"    ||gS||    first-token={sn[-1]:.4e}  last-token={sn[0]:.4e}"
              f"   ratio(first/last)={sn[-1]/sn[0] if sn[0] else float('inf'):.4f}")
        print(f"    ||graw||  first-token={cn[-1]:.4e}  last-token={cn[0]:.4e}"
              f"   ratio={cn[-1]/cn[0] if cn[0] else float('inf'):.4f}")
        # profile in the middle
        step = max(1, L // 8)
        prof = " ".join(f"{sn[i]:.2e}" for i in range(0, L, step))
        print(f"    ||gS|| profile (last->first): {prof}")

    print()
    print("=" * 80)
    print("READING IT")
    print("=" * 80)
    print("ratio ~1     -> gradient reaches the first token intact")
    print("ratio ~0     -> VANISHING: early tokens get no signal (the product of")
    print("                Jacobians contracts); a curriculum or a shorter-range")
    print("                credit path is needed")
    print("ratio >>1    -> EXPLODING: early tokens dominate")


if __name__ == "__main__":
    main()
