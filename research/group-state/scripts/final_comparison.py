#!/usr/bin/env python3
"""Final controlled comparison: where does each state mechanism actually stand?

The warm-up run produced a striking split and a suspicious one:

  parity: continuous warm-up then snap -> 1.000 at EVERY length up to 2048
          (trained only on lengths 1-12)
  mod7:   same recipe -> 0.13, i.e. BELOW chance, at a TRAINED length

A model that is broken even on lengths it trained on points at the training
recipe, not at the representation. Hypothesis: the straight-through gradient is
an estimator, so continuing to train AFTER snapping lets it walk the learned
angle off the correct group element. If so, stopping (freezing) right after the
snap should keep both tasks correct.

This script runs every mode side by side on the same data, including a full
LSTM reference at the long lengths, so the comparison is like-for-like.

Modes per mechanism:
  cont        continuous angles throughout (no snapping)
  snap0       snapped from step 0
  warm+cont   continuous warm-up, then continue training snapped
  warm+freeze continuous warm-up, then snap and STOP training
"""
import argparse
import json
import math
import random
import sys
import time

sys.path.insert(0, "scripts")
from state_tracking_lab import (  # noqa: E402
    LSTM, Rotor, TASKS, accuracy, make_data, loss_and_grad,
)
from rotor_snap_lab import RotorSnap  # noqa: E402


def adam_phase(model, data, epochs, lr, kind):
    ps = model.params()
    m = [[0.0] * p.n for p in ps]
    v = [[0.0] * p.n for p in ps]
    b1, b2, eps = 0.9, 0.999, 1e-8
    step = 0
    for _ in range(epochs):
        random.shuffle(data)
        for xs, t in data:
            for p in ps:
                p.zero()
            _, g = loss_and_grad(model.forward(xs), t, kind)
            model.backward(g)
            step += 1
            bc1 = 1.0 - b1 ** step
            bc2 = 1.0 - b2 ** step
            for i, p in enumerate(ps):
                for j in range(p.n):
                    gj = p.grad[j]
                    m[i][j] = b1 * m[i][j] + (1 - b1) * gj
                    v[i][j] = b2 * v[i][j] + (1 - b2) * gj * gj
                    p.data[j] -= lr * (m[i][j] / bc1) / \
                        (math.sqrt(v[i][j] / bc2) + eps)


def make(mode, out_dim, rng, K):
    if mode.startswith("lstm"):
        return LSTM(1, 16, out_dim, rng, hidden_dim=16)
    snap = mode in ("snap0", "warm+cont", "warm+freeze")
    return RotorSnap(1, 16, out_dim, rng, K=K, hidden_dim=8, snap=snap)


def fit(mode, model, data, epochs, warmup, lr, kind):
    if mode == "warm+freeze":
        model.snap = False
        adam_phase(model, data, warmup, lr, kind)
        model.snap = True
        # frozen: no further training at all
        return
    if mode == "warm+cont":
        model.snap = False
        adam_phase(model, data, warmup, lr, kind)
        model.snap = True
        adam_phase(model, data, max(0, epochs - warmup), lr, kind)
        return
    adam_phase(model, data, epochs, lr, kind)


MODES = ["lstm", "cont", "snap0", "warm+cont", "warm+freeze"]
LABEL = {"lstm": "LSTM (reference)", "cont": "Rotor continuous",
         "snap0": "RotorSnap from0", "warm+cont": "Snap warm+continue",
         "warm+freeze": "Snap warm+FREEZE"}


def run(task, K, train_l, test_l, epochs, warmup, seeds, n_train, n_test, lr):
    kind = TASKS[task]["loss"]
    out_dim = TASKS[task]["out"]
    gen = TASKS[task]["gen"]
    out = {}
    for mode in MODES:
        per = {L: [] for L in test_l}
        t0 = time.time()
        for s in range(seeds):
            rng = random.Random(900 + s)
            model = make(mode, out_dim, rng, K)
            data = make_data(task, train_l, n_train, rng)
            fit(mode, model, data, epochs, warmup, lr, kind)
            for L in test_l:
                c = 0
                for _ in range(n_test):
                    xs, tg = gen(rng, L)
                    c += accuracy(model.forward(xs), tg, kind)
                per[L].append(c / n_test)
        out[mode] = {"mean": {L: sum(v) / len(v) for L, v in per.items()},
                     "secs": round(time.time() - t0, 1)}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=400)
    ap.add_argument("--warmup", type=int, default=250)
    ap.add_argument("--seeds", type=int, default=2)
    args = ap.parse_args()

    summary = {}
    for task, K, tr, te in (
        ("parity", 2, list(range(1, 13)), [8, 64, 256, 1024, 2048]),
        ("mod7", 7, list(range(1, 9)), [6, 16, 64, 256]),
    ):
        res = run(task, K, tr, te, args.epochs, args.warmup, args.seeds,
                  n_train=32, n_test=48, lr=0.02)
        summary[task] = res
        print()
        print("=" * 84)
        print(f"TASK {task} (Z_{K})   trained on lengths {min(tr)}-{max(tr)}   "
              f"'*' = NEVER seen in training")
        print("=" * 84)
        print("  " + f"{'mechanism':<20s}" +
              "".join(f"{str(L)+('*' if L not in tr else ' '):>10s}" for L in te))
        print("  " + "-" * (20 + 10 * len(te)))
        for mode in MODES:
            r = res[mode]
            print("  " + f"{LABEL[mode]:<20s}" +
                  "".join(f"{r['mean'][L]:10.3f}" for L in te))
        print()

    with open("reports/final_comparison_results.json", "w") as f:
        json.dump(summary, f, indent=2)
    print("wrote reports/final_comparison_results.json")


if __name__ == "__main__":
    main()
