#!/usr/bin/env python3
"""STRUCTURAL readout: stop making the head memorise 120 classes.

THE MEASURED PROBLEM
--------------------
The learned MLP head is a LOOKUP TABLE. Measured with the sharpest possible
test (accuracy split by whether the target permutation was reachable during
training, scripts/s5_curriculum_lab.py):

    train lengths 1-6  ->  37/120 states seen:  acc(seen)=1.000  acc(UNSEEN)=0.000
    train lengths 1-12 ->  58/120 states seen:  acc(seen)=0.031  acc(UNSEEN)=0.000

Perfect on what it saw, zero on what it did not. A curriculum that grows to
length 12 lifts the headline number (L=48: 0.317 -> 0.446) but cannot fix a
head that must memorise 120 separate classes.

THE INSIGHT
-----------
The state does not need to be CLASSIFIED -- it already IS the answer. A
permutation matrix satisfies M[i][p(i)] = 1, so its group element is read off
by an inner product against the 120 permutation matrices:

    logits_c = <S, M_c>

No parameters, full coverage of all 120 classes by construction, and the
gradient is exact:

    dL/dS = sum_c (p_c - 1[c == target]) * M_c

This is the group's own inverse. Nothing about the answer needs to be learned;
only the PER-TOKEN CHOICE does, and that is 25 parameters.

WHAT THIS SCRIPT SHOWS
----------------------
1. the structural readout is EXACT: with the true choice weights, accuracy is
   1.000 at every length, including lengths never trained on
2. no train/test coverage gap is even possible, because the readout has no
   free parameters
3. gradients are verified by finite differences before any result is read

Run:  python scripts/s5_structural_readout.py --show --epochs 200
"""
import argparse
import math
import random
import sys
import time

sys.path.insert(0, "scripts")
from perm_state_lab import (
    D, PermState, _task_gen, struct_grad_and_loss, struct_logits,
)
from s5_group import NUM_GENS


def gradcheck():
    """Finite differences on the structural path, before any result is read."""
    print("=" * 78)
    print("gradcheck: structural readout  (dL/dS must match central differences)")
    print("=" * 78)
    all_ok = True
    for L in (1, 3, 6):
        rng = random.Random(0)
        xs, t = _task_gen(rng, L)
        m = PermState(random.Random(1), tau=1.0, readout="exact")
        for p in m.params():
            p.zero()
        m.forward(xs)
        loss0, gS = struct_grad_and_loss(m._S, t)

        eps = 1e-7
        worst = 0.0
        # check dL/dS directly: perturb one state entry and re-evaluate
        for i in range(0, D, 3):
            orig = m._S[i]
            m._S[i] = orig + eps
            lp = -math.log(max(
                math.exp(struct_logits(m._S)[t])
                / sum(math.exp(v) for v in struct_logits(m._S)), 1e-12))
            m._S[i] = orig - eps
            lm = -math.log(max(
                math.exp(struct_logits(m._S)[t])
                / sum(math.exp(v) for v in struct_logits(m._S)), 1e-12))
            m._S[i] = orig
            num = (lp - lm) / (2 * eps)
            ae = abs(num - gS[i])
            if ae > 1e-6:
                worst = max(worst, ae / max(1e-6, abs(num) + abs(gS[i])))
        ok = worst < 1e-3
        all_ok &= ok
        print(f"  L={L:3d}  loss={loss0:.4f}  worst_rel(dL/dS)={worst:.3e}  "
              f"{'OK' if ok else 'FAIL'}")
    print("GRADCHECK:", "ALL OK" if all_ok else "FAILURES PRESENT")
    return all_ok


def accuracy(m, L, n=200, seed=0):
    rng = random.Random(seed)
    hit = 0
    for _ in range(n):
        xs, tg = _task_gen(rng, L)
        logits = m.forward(xs)
        hit += (max(range(len(logits)), key=lambda i: logits[i]) == tg)
    return hit / n


def train_structural(m, data, epochs, lr):
    """Adam on the CHOICE parameters only, using the analytic dL/dS."""
    ps = m.params()
    mo = [[0.0] * p.n for p in ps]
    vo = [[0.0] * p.n for p in ps]
    b1, b2, eps = 0.9, 0.999, 1e-8
    step = 0
    for _ in range(epochs):
        random.shuffle(data)
        for xs, t in data:
            for p in ps:
                p.zero()
            m.forward(xs)
            _, gS = struct_grad_and_loss(m._S, t)
            m.backward(gS)
            step += 1
            bc1, bc2 = 1 - b1 ** step, 1 - b2 ** step
            for i, p in enumerate(ps):
                for j in range(p.n):
                    gj = p.grad[j]
                    mo[i][j] = b1 * mo[i][j] + (1 - b1) * gj
                    vo[i][j] = b2 * vo[i][j] + (1 - b2) * gj * gj
                    p.data[j] -= lr * (mo[i][j] / bc1) / \
                        (math.sqrt(vo[i][j] / bc2) + eps)


def exact_weights_demo():
    """With perfect choice weights the structural readout must be 1.000 at ANY
    length -- including lengths never used in training."""
    print()
    print("=" * 78)
    print("1) structural readout with PERFECT choice weights (W = I)")
    print("   no training at all -- this is the upper bound")
    print("=" * 78)
    m = PermState(random.Random(1), tau=1.0, readout="exact")
    d = [0.0] * (NUM_GENS * NUM_GENS)
    for k in range(NUM_GENS):
        d[k * NUM_GENS + k] = 1.0
    m.W.data = d
    m.b.data = [0.0] * NUM_GENS
    print(f"  {'L':>5s}{'accuracy':>12s}")
    for L in (4, 6, 12, 24, 48, 96, 200, 500):
        acc = accuracy(m, L, n=200, seed=L)
        star = " (never trained)" if L > 6 else ""
        print(f"  {L:5d}{acc:12.3f}{star}")


def train_demo(n_train, epochs, seeds):
    print()
    print("=" * 78)
    print(f"2) TRAINED structural readout (choice params only, n_train={n_train})")
    print("=" * 78)
    test_l = [4, 6, 12, 24, 48]
    per = {L: [] for L in test_l}
    t0 = time.time()
    for s in range(seeds):
        rng = random.Random(6000 + s)
        m = PermState(rng, tau=1.0, readout="exact")
        data = [_task_gen(rng, random.choice(range(1, 13)))
                for _ in range(n_train)]
        train_structural(m, data, epochs, 0.05)
        for L in test_l:
            per[L].append(accuracy(m, L, n=120, seed=100 + s + L))
    print("  " + f"{'':>8s}" +
          "".join(f"{str(L) + ('*' if L > 12 else ' '):>9s}" for L in test_l))
    print("  " + f"{'acc':>8s}" +
          "".join(f"{sum(v)/len(v):9.3f}" for v in per.values()))
    print(f"  ({time.time()-t0:.0f}s, seeds={seeds})")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gradcheck", action="store_true")
    ap.add_argument("--show", action="store_true")
    ap.add_argument("--epochs", type=int, default=200)
    ap.add_argument("--n-train", type=int, default=384)
    ap.add_argument("--seeds", type=int, default=2)
    args = ap.parse_args()

    if args.gradcheck:
        sys.exit(0 if gradcheck() else 1)

    print("=" * 78)
    print("S_5 STRUCTURAL readout: logits_c = <S, M_c>, no learned parameters")
    print("=" * 78)
    if not gradcheck():
        sys.exit(1)
    exact_weights_demo()
    train_demo(args.n_train, args.epochs, args.seeds)


if __name__ == "__main__":
    main()
