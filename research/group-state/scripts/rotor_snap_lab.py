#!/usr/bin/env python3
"""RotorSnap -- exact group state via snapping + straight-through gradient.

MEASURED MOTIVATION (all from this repo's own runs)
---------------------------------------------------
1. scripts/state_tracking_lab.py: on mod-7 state tracking, tanh-RNN and LSTM
   sit at CHANCE (0.09-0.20 of 1.000) while the phase rotor reaches 1.000.
   Phase representation is the only thing that works there -- the
   "Illusion of State" wall (arXiv 2404.08819).
2. scripts/diagnose_rotor_drift.py: the rotor LEARNS the exact group angle
   (0.8983 rad learned vs 2*pi/7 = 0.8976 ideal, 0.08% off) -- but a
   continuous angle is never exactly a group element, so the residual error
   accumulates and the mechanism collapses past ~6x the training length.
3. scripts/cyclic_state_lab.py: relaxing the group algebra to a probability
   distribution (softmax + circular convolution) FAILS. Reason, now
   understood: convolution of distributions is a RANDOM WALK, so the state
   diffuses toward uniform and destroys the information. A differentiable
   relaxation of an automaton is not an automaton.

THE FIX
-------
Keep the phase rotor -- it already finds the right group -- and remove the
drift by SNAPPING the angle onto the K-th roots of unity at every step:

    raw_t   = w . x_t + b                      (learned, in radians)
    q_t     = round(K * raw_t / 2*pi)  mod K   (nearest group element of Z_K)
    theta_t = 2*pi * q_t / K                   (EXACT root of unity)
    z_t     = z_{t-1} * exp(i * theta_t)       (exact group action)

Because exp(i*theta_t) is an exact root of unity, z_T lands exactly on the
group for ANY sequence length: there is no angle error left to accumulate.
Length generalisation stops being an empirical hope and becomes a property of
the update -- while the number of steps, depth, width and state stay O(1).

Rounding blocks the gradient, so the backward pass uses a straight-through
estimator (Bengio et al. 2013): d/draw := d/dtheta. Gradients reach w and b
as if the snap were the identity.

Usage:
    python scripts/rotor_snap_lab.py --gradcheck
    python scripts/rotor_snap_lab.py --epochs 400 --seeds 2
"""
import argparse
import json
import math
import random
import sys
import time

sys.path.insert(0, "scripts")
from state_tracking_lab import (  # noqa: E402
    P, Readout, TASKS, accuracy, adam, loss_and_grad, make_data, mv, mv_back,
    add_into_bias, vec_add, randn,
)

TWO_PI = 2.0 * math.pi


class RotorSnap:
    """d independent Z_K rotors. State is d exact roots of unity, O(1)."""

    def __init__(self, xs_dim, hidden, out_dim, rng, K=2, hidden_dim=8,
                 temperature=1.0, snap=True):
        self.K = K
        self.d = hidden_dim
        self.in_dim = xs_dim
        self.temperature = temperature          # scales raw angle spread
        self.snap = snap                        # False => identical to Rotor
        self.Wt = P([randn(1.0 / math.sqrt(xs_dim), rng)
                    for _ in range(self.d * xs_dim)])
        self.bt = P([randn(0.5, rng) for _ in range(self.d)])
        # exact roots of unity, precomputed -> no trig drift at all
        self._cos = [math.cos(TWO_PI * q / K) for q in range(K)]
        self._sin = [math.sin(TWO_PI * q / K) for q in range(K)]
        self.feat_dim = 2 * self.d
        self.readout = Readout(self.feat_dim, hidden, out_dim, rng)

    def params(self):
        return [self.Wt, self.bt] + self.readout.params()

    def _snap(self, raw):
        """Nearest group element index; returns (q, theta_exact)."""
        K = self.K
        q = int(round(K * raw / TWO_PI)) % K
        return q if self.snap else None

    def forward(self, xs):
        d, K = self.d, self.K
        a = [1.0] * d
        b = [0.0] * d
        self._cache = []
        for x in xs:
            xv = [x]
            raw = vec_add(mv(self.Wt, xv, d, self.in_dim), self.bt.data)
            qs = [self._snap(r) for r in raw]
            if self.snap:
                cs = [self._cos[q] for q in qs]
                sn = [self._sin[q] for q in qs]
            else:
                # continuous path: theta = raw, identical to plain Rotor
                cs = [math.cos(r) for r in raw]
                sn = [math.sin(r) for r in raw]
            a_prev, b_prev = a, b
            a = [a_prev[k] * cs[k] - b_prev[k] * sn[k] for k in range(d)]
            b = [a_prev[k] * sn[k] + b_prev[k] * cs[k] for k in range(d)]
            self._cache.append((xv, a_prev, b_prev, cs, sn))
        self._aT, self._bT = a, b
        f = []
        for k in range(d):
            f.append(a[k])
            f.append(b[k])
        self._f = f
        return self.readout.forward(f)

    def backward(self, glogits):
        """Straight-through: treat the snapped angle as the continuous one."""
        d = self.d
        gf = self.readout.backward(glogits)
        ga = [gf[2 * k] for k in range(d)]
        gb = [gf[2 * k + 1] for k in range(d)]
        for t in range(len(self._cache) - 1, -1, -1):
            xv, a_prev, b_prev, cs, sn = self._cache[t]
            ga_prev = [ga[k] * cs[k] + gb[k] * sn[k] for k in range(d)]
            gb_prev = [-ga[k] * sn[k] + gb[k] * cs[k] for k in range(d)]
            # d/dtheta through the exact rotation, then STE: dx/draw = dx/dtheta
            gth = []
            for k in range(d):
                da = -a_prev[k] * sn[k] - b_prev[k] * cs[k]
                db = a_prev[k] * cs[k] - b_prev[k] * sn[k]
                gth.append(ga[k] * da + gb[k] * db)
            add_into_bias(self.bt, gth)
            mv_back(self.Wt, xv, gth, d, self.in_dim)
            ga, gb = ga_prev, gb_prev


def build(out_dim, rng, K):
    return RotorSnap(1, 16, out_dim, rng, K=K, hidden_dim=8)


# ---------------------------------------------------------------- gradcheck
def gradcheck():
    print("=" * 74)
    print("RotorSnap gradient check (straight-through estimator)")
    print("=" * 74)
    print("NOTE: the snap is piecewise constant, so a finite-difference check")
    print("      is only meaningful where no parameter sits on a rounding")
    print("      boundary. We measure how often that happens and judge on the")
    print("      cases where the forward pass is locally smooth.")
    ok_all = True
    for task, K in (("parity", 2), ("mod7", 7)):
        gen = TASKS[task]["gen"]
        for L in (1, 5, 11):
            rng = random.Random(0)
            xs, t = gen(rng, L)
            kind, out_dim = TASKS[task]["loss"], TASKS[task]["out"]
            m = build(out_dim, random.Random(1), K)
            ps = m.params()
            for p in ps:
                p.zero()
            _, g = loss_and_grad(m.forward(xs), t, kind)
            m.backward(g)

            eps = 1e-6
            worst = 0.0
            smooth = 0
            onboundary = 0
            for pi, p in enumerate(ps):
                for j in range(0, p.n, max(1, p.n // 10)):
                    orig = p.data[j]
                    # detect a rounding boundary: does snapping change?
                    m.forward(xs)
                    qs_a = [list(c[3]) for c in m._cache]
                    p.data[j] = orig + eps
                    m.forward(xs)
                    qs_b = [list(c[3]) for c in m._cache]
                    p.data[j] = orig
                    if qs_a != qs_b:
                        onboundary += 1
                        continue          # non-differentiable by design
                    smooth += 1
                    lp, _ = loss_and_grad(m.forward(xs), t, kind)
                    p.data[j] = orig - eps
                    lm, _ = loss_and_grad(m.forward(xs), t, kind)
                    p.data[j] = orig
                    num = (lp - lm) / (2 * eps)
                    ae = abs(num - p.grad[j])
                    if ae > 1e-6:
                        worst = max(worst, ae / max(1e-6, abs(num) + abs(p.grad[j])))
            ok = worst < 1e-3
            ok_all &= ok
            print(f"  {task:7s} K={K} L={L:3d}  smooth={smooth:3d} "
                  f"on-boundary={onboundary:3d}  worst_rel(smooth)={worst:.3e} "
                  f"{'OK' if ok else 'FAIL'}")
    print("GRADCHECK:", "ALL OK" if ok_all else "FAILURES PRESENT")
    return ok_all


# --------------------------------------------------------------- experiment
def run(task, train_l, test_l, epochs, seeds, n_train, n_test, K):
    kind = TASKS[task]["loss"]
    out_dim = TASKS[task]["out"]
    gen = TASKS[task]["gen"]
    per = {L: [] for L in test_l}
    t0 = time.time()
    for s in range(seeds):
        rng = random.Random(500 + s)
        m = build(out_dim, rng, K)
        data = make_data(task, train_l, n_train, rng)
        adam(m, data, epochs, 0.02, kind)
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
    ap.add_argument("--gradcheck", action="store_true")
    ap.add_argument("--epochs", type=int, default=400)
    ap.add_argument("--seeds", type=int, default=2)
    args = ap.parse_args()

    if args.gradcheck:
        sys.exit(0 if gradcheck() else 1)

    summary = {}
    for task, K, tr, te in (
            ("parity", 2, list(range(1, 13)), [8, 12, 24, 64, 128, 256, 512]),
            ("mod7", 7, list(range(1, 9)), [6, 8, 16, 32, 64, 128]),
    ):
        r = run(task, tr, te, args.epochs, args.seeds, 32, 64, K)
        summary[task] = r
        print()
        print("=" * 74)
        print(f"RotorSnap  task={task} (Z_{K})  trained on lengths "
              f"{min(tr)}-{max(tr)}   '*' = unseen length")
        print("=" * 74)
        row = "  " + " ".join(f"{str(L)+('*' if L not in tr else ' '):>8s}"
                              for L in te)
        print("  " + " " * 10 + row.strip())
        print("  " + " " * 10 + " ".join(f"{r['mean'][L]:8.3f}" for L in te))
        print(f"  ({r['secs']}s)")

    with open("reports/rotor_snap_results.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print("\nwrote reports/rotor_snap_results.json")


if __name__ == "__main__":
    main()
