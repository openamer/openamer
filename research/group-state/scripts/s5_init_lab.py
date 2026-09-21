#!/usr/bin/env python3
"""THE ACTUAL BOTTLENECK: at init the soft state is INPUT-INDEPENDENT.

MEASURED EVIDENCE
-----------------
1. scripts/diagnose_gradient_flow.py: the gradient does NOT vanish. The
   first-token/last-token state-gradient ratio is 0.51 at L=4 and 0.44 at
   L=32, and the per-position profile FLATTENS with length. So "credit
   assignment is blocked by a vanishing gradient" is REFUTED as the cause.

2. The remaining suspect is the INITIALISATION of the soft state. At init
   W ~ N(0, 1/sqrt(5)) is small, so softmax(W @ onehot(x)) is near UNIFORM
   for every token. Each per-token generator mixture G_t is then the SAME
   near-average doubly-stochastic matrix, and a product of T such matrices is
   again near-uniform -- i.e. the state carries almost NO information about
   the input sequence. The readout head therefore sees an input-independent
   feature, gets no usable signal, and the 25-parameter choice matrix W never
   learns. This is the same DIFFUSION already measured for the abelian
   convolution case.

THE TEST
--------
If that diagnosis is right, initialising W to the IDENTITY (so argmax is
already the correct generator and the initial state IS the true permutation)
should immediately give the head a meaningful feature, and training should
escape chance -- without changing anything else.

Configs compared, all with the same data/epochs:
  rand-init   W = small random          (the failing baseline)
  I-init      W = I + 0.05 noise        (choice correct at the start; trained)
  I-frozen    W = I, gradients blocked  (upper bound: what the state supports
                                         with only the readout learning)

Plus a diagnostic of the ACTUAL init behaviour: how input-dependent is the
soft state at initialisation? That number is near-minimal for rand-init.

Run:  python scripts/s5_init_lab.py --epochs 200 --seeds 2
      python scripts/s5_init_lab.py --assert-init     # fast gate
"""
import argparse
import json
import math
import random
import sys
import time

sys.path.insert(0, "scripts")
from perm_state_lab import (
    OUT, PermState, _task_gen, accuracy, choice_accuracy, train_phase,
)
from s5_group import NUM_GENS

TRAIN_L = range(1, 7)          # short products only
TEST_L = [4, 6, 12, 24]        # 4,6 in-distribution; 12,24 unseen
INIT_DEPENDENCE_FLOOR = 0.15   # gate threshold (rand-init measures ~0.109)


def input_dependence(m, L=6, n=64, seed=0):
    """How different is the final soft state across DIFFERENT token sequences?

    Measures the mean pairwise L2 distance between final states of random
    inputs. ~0 means the state does not depend on the input at all -- the
    head cannot possibly read the answer out of it.
    """
    rng = random.Random(seed)
    states = []
    for _ in range(n):
        xs, _ = _task_gen(rng, L)
        choices = m._choices(xs)
        S, _ = m._soft_state(choices)
        states.append(S)
    tot = 0.0
    pairs = 0
    for i in range(0, len(states), 4):
        for j in range(i + 1, min(i + 4, len(states))):
            tot += math.sqrt(sum((a - b) ** 2
                                 for a, b in zip(states[i], states[j])))
            pairs += 1
    return tot / max(1, pairs)


def run(config, n_train, epochs, lr, seeds):
    """config: rand-init | I-init | I-frozen  (init is a PermState argument)."""
    choice = []
    per_len = {L: [] for L in TEST_L}
    t0 = time.time()
    for s in range(seeds):
        rng = random.Random(3000 + s)
        m = PermState(rng, tau=1.0,
                      init="random" if config == "rand-init" else "identity")
        m.eval_hard = True
        if config == "I-frozen":
            # upper bound: the choice path is correct AND frozen, so only the
            # readout learns. Shows what the state alone can support.
            m.params = lambda: [m.head.W1, m.head.b1, m.head.W2, m.head.b2]
        data = [_task_gen(rng, random.choice(TRAIN_L)) for _ in range(n_train)]
        train_phase(m, data, epochs, lr)
        choice.append(choice_accuracy(m, seed=100 + s))
        for L in TEST_L:
            rng2 = random.Random(200 + s + L)
            hit = sum(accuracy(m.forward(xs), tg)
                      for xs, tg in (_task_gen(rng2, L) for _ in range(120)))
            per_len[L].append(hit / 120)
    return {"choice_acc": sum(choice) / len(choice),
            "choice_per_seed": choice,
            "exact": {L: sum(v) / len(v) for L, v in per_len.items()},
            "secs": round(time.time() - t0, 1)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=200)
    ap.add_argument("--n-train", type=int, default=192)
    ap.add_argument("--seeds", type=int, default=2)
    ap.add_argument("--assert-init", action="store_true")
    args = ap.parse_args()

    if args.assert_init:
        # FAST gate (<2s): the DEFAULT init must make the soft state actually
        # depend on the input. If it does not, the readout sees a constant
        # feature, the choice matrix never learns, and every S_5 accuracy
        # number is meaningless -- exactly the bug that produced the original
        # "the wall holds" conclusion (input-dependence 0.109).
        d = sum(input_dependence(PermState(random.Random(11 + s), tau=1.0))
                for s in range(3)) / 3
        ok = d > INIT_DEPENDENCE_FLOOR
        print(f"  input-dependence at default init = {d:.4f} "
              f"(must exceed {INIT_DEPENDENCE_FLOOR})  {'OK' if ok else 'FAIL'}")
        if not ok:
            print("  -> the state is near input-INDEPENDENT at init; the")
            print("     choice matrix cannot learn. Check PermState init.")
            sys.exit(1)
        print("INIT CHECK: the default init carries input information")
        sys.exit(0)

    print("=" * 84)
    print("S_5: is the bottleneck the INIT, not credit assignment?")
    print(f"  chance: choice 1/5 = 0.200 | class 1/{OUT} = 0.008")
    print(f"  n_train={args.n_train} epochs={args.epochs} seeds={args.seeds}")
    print("=" * 84)

    # ---- diagnostic: how input-dependent is the state at init? -----------
    print()
    print("input-dependence of the soft state AT INITIALISATION")
    print("  (mean pairwise L2 distance between final states of random inputs)")
    for label, init in (("rand-init", "random"), ("I-init", "identity")):
        vals = [input_dependence(PermState(random.Random(11 + s), tau=1.0,
                                           init=init)) for s in range(3)]
        print(f"  {label:12s} distance = {sum(vals)/len(vals):.4f}"
              f"   (per seed {[round(v,4) for v in vals]})")

    # ---- experiment ------------------------------------------------------
    print()
    results = {}
    for config in ("rand-init", "I-init", "I-frozen"):
        r = run(config, args.n_train, args.epochs, 0.05, args.seeds)
        results[config] = r
        print(f"  {config:12s} choice_acc={r['choice_acc']:.3f} "
              f"(seeds {[round(c,3) for c in r['choice_per_seed']]})  "
              f"({r['secs']}s)")

    print()
    print("=" * 84)
    print("EXACT accuracy")
    print("=" * 84)
    print("  " + f"{'config':<12s}" +
          "".join(f"{str(L) + ('*' if L not in TRAIN_L else ' '):>9s}"
                  for L in TEST_L))
    print("  " + "-" * (12 + 9 * len(TEST_L)))
    for c, r in results.items():
        print("  " + f"{c:<12s}" +
              "".join(f"{r['exact'][L]:9.3f}" for L in TEST_L))

    with open("reports/s5_init_results.json", "w") as f:
        json.dump(results, f, indent=2)
    print("\nwrote reports/s5_init_results.json")


if __name__ == "__main__":
    main()
