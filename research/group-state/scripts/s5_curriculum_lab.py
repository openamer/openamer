#!/usr/bin/env python3
"""Does TRAINING LENGTH explain the readout decay? Test the coverage theory.

THE GAP TO CLOSE
----------------
After the initialisation fix (W=I), S_5 accuracy is 0.917 at L=4 but drops to
0.383 at L=24, while the frozen-W upper bound shows the STATE path is correct.
The proposed reason is that training on lengths 1-6 only ever shows the readout
a subset of the 120 permutations; it must classify states it never saw.

That is a testable claim with a countable quantity: CLASS COVERAGE, the number
of distinct group elements reachable within a maximum training length.

    L=4  -> 49 of 120
    L=6  -> 91 of 120
    L=8  -> 115
    L=12 -> 120 (all)

If coverage is the cause, then training with longer sequences (or a curriculum
that grows) should raise accuracy at unseen LONG lengths. If it does not, the
coverage theory is wrong and something else limits the readout.

WHAT IS MEASURED
----------------
1. coverage(L) -- distinct permutations reachable by words of length <= L
2. accuracy at L=4,6,12,24,48 for training regimes:
     fixed-6    train on 1..6     (the current baseline)
     fixed-12   train on 1..12
     curriculum grow max length 1 -> 12 over training
3. the readout's accuracy RESTRICTED to states it saw vs never saw, which is
   the sharpest test of the coverage theory

Run:  python scripts/s5_curriculum_lab.py --epochs 250 --seeds 2
"""
import argparse
import json
import random
import sys
import time
from collections import Counter

sys.path.insert(0, "scripts")
from perm_state_lab import (
    OUT, PermState, _task_gen, accuracy, choice_accuracy, train_phase,
)
from s5_group import ELEMENTS, GENERATORS, IDENTITY, INDEX, compose

TEST_L = [4, 6, 12, 24, 48]


# ---------------------------------------------------------------------------
def coverage(max_len, n_per_len=1500, seed=0):
    """Number of DISTINCT permutations reachable by words of length <= max_len.

    Also returns, for each element, the shortest length that reaches it, which
    is what a curriculum can exploit.
    """
    seen = {IDENTITY}
    rng = random.Random(seed)
    for L in range(1, max_len + 1):
        for _ in range(n_per_len):
            state = IDENTITY
            for _ in range(L):
                state = compose(state, GENERATORS[rng.randrange(len(GENERATORS))])
            seen.add(state)
    # exact shortest-word length per element via BFS over the generator set
    dist = {IDENTITY: 0}
    frontier = [IDENTITY]
    d = 0
    while frontier and d < max_len:
        nxt = []
        for cur in frontier:
            for g in GENERATORS:
                s = compose(cur, g)
                if s not in dist:
                    dist[s] = d + 1
                    nxt.append(s)
        frontier = nxt
        d += 1
    return len(seen), len(dist), dist


def make_data_train(train_lens, n, rng):
    return [_task_gen(rng, random.choice(train_lens)) for _ in range(n)]




def evaluate(m, seed=0, n=120):
    out = {}
    for L in TEST_L:
        rng = random.Random(700 + seed + L)
        hit = sum(accuracy(m.forward(xs), tg)
                  for xs, tg in (_task_gen(rng, L) for _ in range(n)))
        out[L] = hit / n
    return out


# ---------------------------------------------------------------------------
def run(regime, n_train, epochs, lr, seeds):
    choice, per_len = [], {L: [] for L in TEST_L}
    t0 = time.time()
    for s in range(seeds):
        rng = random.Random(4100 + s)
        m = PermState(rng, tau=1.0)          # init="identity" is the default
        m.eval_hard = True

        if regime == "fixed-6":
            data = make_data_train(range(1, 7), n_train, rng)
            train_phase(m, data, epochs, lr)

        elif regime == "fixed-12":
            data = make_data_train(range(1, 13), n_train, rng)
            train_phase(m, data, epochs, lr)

        elif regime == "curriculum":
            # grow the maximum training length 1 -> 12, refreshing data each
            # stage. Earlier stages are cheap and establish the choice map;
            # later stages expose the readout to the states it never saw.
            stages = 6
            per_stage = max(1, epochs // stages)
            for st in range(stages):
                hi = 1 + round((12 - 1) * (st + 1) / stages)
                data = make_data_train(range(1, hi + 1), n_train, rng)
                train_phase(m, data, per_stage, lr)

        choice.append(choice_accuracy(m, seed=100 + s))
        ev = evaluate(m, seed=s)
        for L in TEST_L:
            per_len[L].append(ev[L])
    return {"choice_acc": sum(choice) / len(choice),
            "choice_per_seed": choice,
            "exact": {L: sum(v) / len(v) for L, v in per_len.items()},
            "secs": round(time.time() - t0, 1)}


def seen_vs_unseen(n_train=192, epochs=250, seed=0, max_train_len=6):
    """Accuracy split by whether the target state was reachable in training.

    THE SHARPEST TEST: if the readout fails mainly on states it never saw, the
    coverage theory holds. If it fails equally on states it DID see, coverage
    is not the explanation.
    """
    rng = random.Random(4100 + seed)
    m = PermState(rng, tau=1.0)
    m.eval_hard = True
    data = make_data_train(range(1, max_train_len + 1), n_train, rng)
    trainable = {IDENTITY}
    for xs, _ in data:
        st = IDENTITY
        for g in xs:
            st = compose(st, GENERATORS[g])
        trainable.add(st)

    train_phase(m, data, epochs, 0.05)

    hit_seen = tot_seen = hit_un = tot_un = 0
    rng2 = random.Random(999)
    for _ in range(4000):
        xs, tg = _task_gen(rng2, 16)
        st = IDENTITY
        for g in xs:
            st = compose(st, GENERATORS[g])
        ok = accuracy(m.forward(xs), tg)
        if st in trainable:
            hit_seen += ok
            tot_seen += 1
        else:
            hit_un += ok
            tot_un += 1
    return (hit_seen / max(1, tot_seen), tot_seen,
            hit_un / max(1, tot_un), tot_un,
            len(trainable))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=250)
    ap.add_argument("--n-train", type=int, default=192)
    ap.add_argument("--seeds", type=int, default=2)
    args = ap.parse_args()

    print("=" * 86)
    print("S_5: does training-length COVERAGE explain the readout decay?")
    print(f"  chance 1/{OUT} = {1/OUT:.4f} | n_train={args.n_train} "
          f"epochs={args.epochs} seeds={args.seeds}")
    print("=" * 86)

    # ---- 1. coverage vs maximum training length --------------------------
    print()
    print("1) class coverage: how many of the 120 permutations are reachable?")
    print(f"   {'max len':>8s}{'reachable':>12s}{'BFS distance<=':>16s}")
    print("   " + "-" * 34)
    for L in (4, 6, 8, 12):
        n_emp, n_exact, _ = coverage(L)
        print(f"   {L:8d}{n_emp:12d}{n_exact:16d}")

    # ---- 2. regimes ------------------------------------------------------
    print()
    print("2) training regimes")
    results = {}
    for regime in ("fixed-6", "fixed-12", "curriculum"):
        r = run(regime, args.n_train, args.epochs, 0.05, args.seeds)
        results[regime] = r
        print(f"   {regime:12s} choice_acc={r['choice_acc']:.3f} "
              f"(seeds {[round(c,3) for c in r['choice_per_seed']]})  "
              f"({r['secs']}s)")

    print()
    print("=" * 86)
    print("EXACT accuracy")
    print("=" * 86)
    print("   " + f"{'regime':<12s}" +
          "".join(f"{str(L) + ('*' if L > 6 else ' '):>9s}" for L in TEST_L))
    print("   " + "-" * (12 + 9 * len(TEST_L)))
    for c, r in results.items():
        print("   " + f"{c:<12s}" +
              "".join(f"{r['exact'][L]:9.3f}" for L in TEST_L))

    # ---- 3. seen vs unseen states ---------------------------------------
    print()
    print("3) SHARPEST TEST: accuracy on states seen vs never seen in training")
    for mtl in (6, 12):
        hs, ts, hu, tu, ntr = seen_vs_unseen(n_train=args.n_train,
                                            epochs=args.epochs,
                                            max_train_len=mtl)
        print(f"   train<= {mtl:2d}  trainable states={ntr:3d}/120  "
              f"acc(seen)={hs:.3f} (n={ts})  acc(UNSEEN)={hu:.3f} (n={tu})")

    print()
    print("=" * 86)
    print("READING IT")
    print("=" * 86)
    print("If acc(seen) >> acc(UNSEEN), the readout fails on states it never")
    print("saw -> coverage is the limit and a longer curriculum is the fix.")
    print("If acc(seen) ~ acc(UNSEEN), coverage is NOT the cause.")

    with open("reports/s5_curriculum_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print("\nwrote reports/s5_curriculum_results.json")


if __name__ == "__main__":
    main()
