#!/usr/bin/env python3
"""Does TAU ANNEALING break the S_5 credit-assignment bottleneck?

MEASURED SITUATION (scripts/diagnose_s5.py, scripts/perm_state_lab.py)
----------------------------------------------------------------------
* The CONSTRUCTION is proven sound: freeze W = I (choose the true generator
  every token) and train only the readout head -> exact accuracy 0.908 at L=4,
  0.342 at L=48, against chance 0.008. So the state path works and the group
  algebra is right.
* Training everything together does NOT recover it: per-token choice accuracy
  sits at chance (0.198-0.214, chance = 0.20). One run briefly hit 0.610 --
  i.e. the optimisation is UNSTABLE, not merely slow.

THE HYPOTHESIS UNDER TEST
-------------------------
A per-token generator choice is a HARD, discrete decision. At flat tau the
gradient reaching early tokens must survive a long product of matrix
multiplications to be useful, and it is dominated by noise. The standard
remedy is a schedule: start smooth so every token receives usable signal, end
sharp so the model matches the hard decision used at evaluation.

    tau: 2.0 -> 0.25   linearly over training

If annealing is the missing ingredient, choice accuracy must climb clearly
above 0.20 and exact accuracy must rise with it. If it does not, annealing is
not the bottleneck and we say so.

Run:  python scripts/s5_anneal_lab.py --epochs 300 --n-train 192
"""
import argparse
import json
import random
import sys
import time

sys.path.insert(0, "scripts")
from s5_group import NUM_GENS
from perm_state_lab import (
    OUT, PermState, _task_gen, accuracy, choice_accuracy, train_phase,
)




def evaluate(m, lengths, n=120, seed=6):
    rng = random.Random(seed)
    out = {}
    for L in lengths:
        h = 0
        for _ in range(n):
            xs, tg = _task_gen(rng, L)
            h += accuracy(m.forward(xs), tg)
        out[L] = h / n
    return out


def run(anneal, n_train, epochs, lr, seeds, tau_fixed):
    test_l = [4, 6, 12, 24, 48]
    choice, exact = [], {L: [] for L in test_l}
    t0 = time.time()
    for s in range(seeds):
        rng = random.Random(2000 + s)
        m = PermState(rng, tau=tau_fixed)
        m.eval_hard = True
        data = [_task_gen(rng, random.choice(range(1, 7)))
                for _ in range(n_train)]
        train_phase(m, data, epochs, lr,
                    anneal=anneal)
        choice.append(choice_accuracy(m, seed=100 + s))
        ev = evaluate(m, test_l, seed=200 + s)
        for L in test_l:
            exact[L].append(ev[L])
    return {
        "choice_acc": sum(choice) / len(choice),
        "choice_per_seed": choice,
        "exact": {L: sum(v) / len(v) for L, v in exact.items()},
        "secs": round(time.time() - t0, 1),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=300)
    ap.add_argument("--n-train", type=int, default=192)
    ap.add_argument("--seeds", type=int, default=2)
    ap.add_argument("--lr", type=float, default=0.05)
    args = ap.parse_args()

    print("=" * 84)
    print("S_5 non-abelian: does tau annealing fix credit assignment?")
    print(f"  chance: per-token choice 1/5 = 0.200 | class 1/{OUT} = 0.008")
    print(f"  n_train={args.n_train}  epochs={args.epochs}  seeds={args.seeds}")
    print("=" * 84)

    configs = [
        ("flat tau=1.0",       None,          1.0),
        ("anneal 2.0->0.25",   (2.0, 0.25),   1.0),
        ("anneal 4.0->0.10",   (4.0, 0.10),   1.0),
    ]

    results = {}
    for label, anneal, tau in configs:
        r = run(anneal, args.n_train, args.epochs, args.lr, args.seeds, tau)
        results[label] = r
        print(f"  {label:20s} choice_acc={r['choice_acc']:.3f} "
              f"(seeds {[round(c,3) for c in r['choice_per_seed']]})  "
              f"({r['secs']}s)")

    test_l = [4, 6, 12, 24, 48]
    print()
    print("=" * 84)
    print("EXACT accuracy (state recomposed from argmax generators)")
    print("=" * 84)
    print("  " + f"{'config':<20s}" +
          "".join(f"{str(L) + ('*' if L > 6 else ' '):>9s}" for L in test_l))
    print("  " + "-" * (20 + 9 * len(test_l)))
    for label in results:
        print("  " + f"{label:<20s}" +
              "".join(f"{results[label]['exact'][L]:9.3f}" for L in test_l))

    print()
    best = max(results.items(), key=lambda kv: kv[1]["choice_acc"])
    print(f"best config: {best[0]}  choice_acc={best[1]['choice_acc']:.3f}")
    if best[1]["choice_acc"] <= 0.25:
        print()
        print("VERDICT: annealing did NOT lift the per-token choice above")
        print("chance. Credit assignment through the non-commutative product is")
        print("the open problem, and a tau schedule is not sufficient for it.")
    else:
        print()
        print("VERDICT: annealing lifts the choice accuracy above chance ->")
        print("the bottleneck was optimisation, and the schedule is the fix.")

    with open("reports/s5_anneal_results.json", "w") as f:
        json.dump(results, f, indent=2)
    print("wrote reports/s5_anneal_results.json")


if __name__ == "__main__":
    main()
