#!/usr/bin/env python3
"""RotorSnap + warm-up: learn continuously, then lock onto the group.

WHY WARM-UP
-----------
Two measurements in this repo point at each other:

  * scripts/diagnose_rotor_drift.py -- the CONTINUOUS rotor learns the group
    angle to 0.08% (0.8983 rad learned vs 2*pi/7 = 0.8976 ideal) and scores
    1.000 on mod-7 at trained lengths. So continuous training FINDS the right
    answer.
  * scripts/rotor_snap_lab.py -- the SNAPPED rotor is flat across length
    (parity 0.81-0.87 from L=24 to L=512, where the continuous rotor collapsed
    to 0.33), so snapping REMOVES drift. But snapping from step 0 costs
    accuracy (parity 0.83 not 1.000; mod-7 0.27 vs 1.000), because a hard
    rounding step with a straight-through gradient gives a poor learning
    signal.

Neither alone is enough. Warm-up uses each for what it is good at:

    phase 1 (warm-up):  snap=False  -- gradients flow, w and b find the group
    phase 2 (locked):   snap=True   -- state is exactly on Z_K, no drift

The switch is a property of the update, so length generalisation becomes
structural rather than empirical.

Run:  python scripts/rotor_snap_warmup.py --epochs 600 --warmup 300 --seeds 3
"""
import argparse
import json
import math
import random
import sys
import time

sys.path.insert(0, "scripts")
from state_tracking_lab import (  # noqa: E402
    TASKS, accuracy, make_data, loss_and_grad,
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
            logits = model.forward(xs)
            _, g = loss_and_grad(logits, t, kind)
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


def run(task, K, train_l, test_l, epochs, warmup, seeds, n_train=32, n_test=64,
        lr=0.02):
    kind = TASKS[task]["loss"]
    out_dim = TASKS[task]["out"]
    gen = TASKS[task]["gen"]
    per = {L: [] for L in test_l}
    t0 = time.time()
    for s in range(seeds):
        rng = random.Random(700 + s)
        m = RotorSnap(1, 16, out_dim, rng, K=K, hidden_dim=8, snap=False)
        data = make_data(task, train_l, n_train, rng)
        if warmup > 0:
            adam_phase(m, data, warmup, lr, kind)      # learn continuously
        m.snap = True                                  # LOCK onto the group
        adam_phase(m, data, max(0, epochs - warmup), lr, kind)
        for L in test_l:
            c = 0
            for _ in range(n_test):
                xs, tg = gen(rng, L)
                c += accuracy(m.forward(xs), tg, kind)
            per[L].append(c / n_test)
    return {"mean": {L: sum(v) / len(v) for L, v in per.items()},
            "secs": round(time.time() - t0, 1)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=600)
    ap.add_argument("--warmup", type=int, default=300)
    ap.add_argument("--seeds", type=int, default=3)
    args = ap.parse_args()

    print("=" * 78)
    print(f"RotorSnap with warm-up: continuous for {args.warmup} epochs, then")
    print(f"locked onto Z_K for the remaining {args.epochs - args.warmup}.")
    print("=" * 78)

    summary = {}
    cases = [
        ("parity", 2, list(range(1, 13)),
         [8, 24, 64, 128, 256, 512, 1024, 2048]),
        ("mod7", 7, list(range(1, 9)),
         [6, 16, 32, 64, 128, 256]),
    ]
    for task, K, tr, te in cases:
        r = run(task, K, tr, te, args.epochs, args.warmup, args.seeds)
        summary[task] = r
        print()
        print(f"  task={task} (Z_{K})   trained {min(tr)}-{max(tr)}   "
              f"'*' = unseen length")
        print("  " + " " * 8 + " ".join(f"{str(L)+('*' if L not in tr else ' '):>9s}"
                                        for L in te))
        print("  " + " " * 8 + " ".join(f"{r['mean'][L]:9.3f}" for L in te))
        print(f"  ({r['secs']}s)")

    with open("reports/rotor_snap_warmup_results.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print("\nwrote reports/rotor_snap_warmup_results.json")


if __name__ == "__main__":
    main()
