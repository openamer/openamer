#!/usr/bin/env python3
"""CyclicState -- exact group-valued recurrent state for state tracking.

WHERE THIS COMES FROM
---------------------
Measured in scripts/state_tracking_lab.py:
  * tanh/sigmoid recurrences (SimpleRNN) and the bag-of-tokens baseline sit at
    CHANCE on mod-k (0.17 of 1.000) -- the saturating-representation limit.
  * the continuous-angle rotor learns the EXACT group angle (learned
    0.8983 rad vs the ideal 2*pi/7 = 0.8976 rad, 0.08% off) and destroys the
    baselines on mod-k -- but collapses past ~6x the training length.
  * diagnosis (scripts/diagnose_rotor_drift.py) shows why: a CONTINUOUS angle
    is never exactly a group element, and any residual error accumulates with
    sequence length. Shorter training lengths hide it.

THE FIX
-------
Do not learn a continuous angle. Let the state BE a probability distribution
over the cyclic group Z_K, and let each token pick a group element:

    s_0 = delta_0
    t_n = softmax(W_k x_n)                 # per-token choice over Z_K
    s_n = s_{n-1} (*) t_n                  # circular convolution = ADDITION mod K

Circular convolution on Z_K IS the group operation of the group algebra, so the
accumulation is EXACT by construction: s_T is a distribution over
sum_n (chosen element) mod K. There is no angle to drift, so length
generalisation is not an empirical accident -- it is a property of the update.
The whole path is differentiable (softmax + convolution), so it trains by plain
backprop, unlike a hard argmax state machine.

Note what this is NOT: no depth, no width, no attention, no scan trick. The
recurrence is one convolution of a K-vector per token, O(K) per step and O(K)
state -- cheaper than any baseline here, and it is the classical weight finite
automaton, learned end to end.

Usage:  python scripts/cyclic_state_lab.py [--epochs N] [--seeds N]
"""
import argparse
import json
import math
import random
import sys
import time

sys.path.insert(0, "scripts")
from state_tracking_lab import (  # noqa: E402
    MECHANISMS, P, Readout, TASKS, accuracy, adam, make_data, mv, mv_back,
    add_into_bias, vec_add, randn,
)

# ===========================================================================
# CyclicState
# ===========================================================================


class CyclicState:
    """Recurrent state = distribution over Z_K, updated by convolution."""

    def __init__(self, xs_dim, hidden, out_dim, rng, K=2, use_readout=True,
                 hidden_dim=16):
        self.K = K
        self.in_dim = xs_dim
        # group-element logits per token
        self.Wk = P([randn(1.0 / math.sqrt(xs_dim), rng)
                     for _ in range(K * xs_dim)])
        self.bk = P([0.0] * K)
        # readout consumes the K-vector state directly
        self.use_readout = use_readout
        if use_readout:
            self.readout = Readout(K, hidden, out_dim, rng)
        else:
            # direct linear map K -> out_dim (state IS the answer space)
            self.Wo = P([randn(1.0 / math.sqrt(K), rng)
                         for _ in range(out_dim * K)])
            self.bo = P([0.0] * out_dim)

    def params(self):
        base = [self.Wk, self.bk]
        return base + (self.readout.params() if self.use_readout
                       else [self.Wo, self.bo])

    # ---- forward ---------------------------------------------------------
    def forward(self, xs):
        K = self.K
        s = [0.0] * K
        s[0] = 1.0                      # delta at 0
        self._cache = []
        for x in xs:
            xv = [x]
            z = vec_add(mv(self.Wk, xv, K, self.in_dim), self.bk.data)
            m = max(z)
            ex = [math.exp(v - m) for v in z]
            den = sum(ex)
            t = [e / den for e in ex]
            # circular convolution: s_new[i] = sum_j s[j] * t[(i-j) % K]
            s_new = [0.0] * K
            for i in range(K):
                acc = 0.0
                for j in range(K):
                    acc += s[j] * t[(i - j) % K]
                s_new[i] = acc
            self._cache.append((xv, z, t, s[:], s_new[:]))
            s = s_new
        self._sT = s
        if self.use_readout:
            return self.readout.forward(s)
        return vec_add(mv(self.Wo, s, len(self.bo.data), K), self.bo.data)

    # ---- backward --------------------------------------------------------
    def backward(self, glogits):
        K = self.K
        if self.use_readout:
            gs = self.readout.backward(glogits)
        else:
            add_into_bias(self.bo, glogits)
            gs = mv_back(self.Wo, self._sT, glogits, len(self.bo.data), K)
        for t_i in range(len(self._cache) - 1, -1, -1):
            xv, z, t, s_prev, s_new = self._cache[t_i]
            # grad wrt s_prev and t through the convolution
            gs_prev = [0.0] * K
            gt = [0.0] * K
            for i in range(K):
                gi = gs[i]
                if gi == 0.0:
                    continue
                for j in range(K):
                    gs_prev[j] += gi * t[(i - j) % K]
                    gt[(i - j) % K] += gi * s_prev[j]
            # softmax backward
            dot = sum(gt[k] * t[k] for k in range(K))
            gz = [t[k] * (gt[k] - dot) for k in range(K)]
            add_into_bias(self.bk, gz)
            mv_back(self.Wk, xv, gz, K, self.in_dim)
            gs = gs_prev


# ===========================================================================
# reference implementations kept in the same file for a like-for-like run
# ===========================================================================


def build(mech, out_dim, rng, K):
    if mech == "cyclic":
        return CyclicState(1, 16, out_dim, rng, K=K)
    return MECHANISMS[mech](1, 16, out_dim, rng, hidden_dim=16)


NAMES = {"window": "WindowMLP(bag)", "rnn": "SimpleRNN(tanh)",
         "lstm": "LSTM", "rotor": "Rotor(angle)",
         "cyclic": "CyclicState(NEW)"}


def run(task, mechs, train_l, test_l, n_train, n_test, epochs, lr, seeds, K):
    kind = TASKS[task]["loss"]
    out_dim = TASKS[task]["out"]
    res = {}
    for mname in mechs:
        per_len = {L: [] for L in test_l}
        t0 = time.time()
        for s in range(seeds):
            rng = random.Random(1000 + s)
            model = build(mname, out_dim, rng, K)
            data = make_data(task, train_l, n_train, rng)
            adam(model, data, epochs, lr, kind)
            for L in test_l:
                gen = TASKS[task]["gen"]
                c = 0
                for _ in range(n_test):
                    xs, tg = gen(rng, L)
                    c += accuracy(model.forward(xs), tg, kind)
                per_len[L].append(c / n_test)
        res[mname] = {"mean": {L: sum(v) / len(v) for L, v in per_len.items()},
                      "secs": round(time.time() - t0, 1)}
    return res


def report(task, train_l, test_l, res):
    print()
    print("=" * 80)
    print(f"TASK {task}   train lengths {min(train_l)}-{max(train_l)}"
          f"   '*' = length NEVER seen in training")
    print("=" * 80)
    hdr = f"  {'mechanism':<18s}"
    for L in test_l:
        hdr += f"{str(L) + ('*' if L not in train_l else ' '):>9s}"
    hdr += f"{'secs':>9s}"
    print(hdr)
    print("  " + "-" * (len(hdr) - 2))
    for mname, r in res.items():
        row = f"  {NAMES[mname]:<18s}"
        for L in test_l:
            row += f"{r['mean'][L]:9.3f}"
        row += f"{r['secs']:9.1f}"
        print(row)
    print("=" * 80)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=400)
    ap.add_argument("--seeds", type=int, default=3)
    args = ap.parse_args()

    mechs = ["window", "rnn", "lstm", "rotor", "cyclic"]
    summary = {}

    # ---- parity (Z_2) ----------------------------------------------------
    tr = list(range(1, 13))
    te = [8, 12, 24, 48, 96, 192]
    res = run("parity", mechs, tr, te, 32, 64, args.epochs, 0.02, args.seeds, K=2)
    report("parity (Z_2)", tr, te, res)
    summary["parity"] = res

    # ---- mod 7 (Z_7) -----------------------------------------------------
    tr7 = list(range(1, 9))
    te7 = [6, 8, 16, 32, 64, 128]
    res = run("mod7", mechs, tr7, te7, 32, 64, args.epochs, 0.02, args.seeds, K=7)
    report("mod7 (Z_7)", tr7, te7, res)
    summary["mod7"] = res

    with open("reports/cyclic_state_results.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print("wrote reports/cyclic_state_results.json")


if __name__ == "__main__":
    main()
