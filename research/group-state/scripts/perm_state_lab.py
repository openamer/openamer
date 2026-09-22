#!/usr/bin/env python3
"""Non-abelian state tracking: the wall a commutative scalar cannot cross.

WHY A NON-ABELIAN GROUP
-----------------------
scripts/rotor_snap_lab.py solves Z_K. But a unit-modulus scalar multiplies
COMMUTATIVELY:

    exp(i*a) * exp(i*b) == exp(i*b) * exp(i*a)

so no product of phases can encode the ORDER of non-commuting operations.
RotorSnap is structurally unable to solve S_5 -- not a tuning issue.

Merrill et al. ("The Illusion of State in State-Space Models", plus the
follow-up on chain-of-thought) report that transformers fail on non-solvable
groups such as S_5 / A_5 even with CoT. This file tests that locally instead of
trusting it.

THE CONSTRUCTION
----------------
Replace the commutative scalar by a MATRIX and let the group act by MATRIX
MULTIPLICATION, which does not commute:

    state_0   = I                       (5x5 identity permutation matrix)
    choice_t  = softmax(W x_t)          (over the 5 generators)
    G_t       = sum_k choice_t[k] * M_k (differentiable mixture)
    state_t   = G_t @ state_{t-1}

Convention verified, not assumed:  matrix(compose(a,b)) == M_b @ M_a
(see verify_convention() and scripts/s5_group.py).

The generators are the four adjacent transpositions (01),(12),(23),(34) plus
the identity; BFS in scripts/s5_group.py confirms they reach all 120 elements.
So the reachable state space is the full symmetric group and the update order
matters, because the matrix product does not commute.

WHAT IS ACTUALLY COMPARED
-------------------------
The model always carries a differentiable SOFT state (that is what backprop
sees). Evaluation can then use either:

    perm_soft : the soft, doubly-stochastic state
    perm_hard : the EXACT state, recomputed by composing the argmax generators

Both come from the SAME trained weights, so the comparison isolates one
question: does an exactly group-valued state beat a relaxed one?

This matters because a softmax mixture of permutation matrices is doubly
stochastic, and a product of doubly-stochastic matrices DIFFUSES toward uniform
-- the same failure mode already measured for the abelian case in
scripts/cyclic_state_lab.py. A temperature parameter sharpens the mixture so
soft can approach hard.

Controls: bag (generator counts -- order-BLIND, the commutative control),
tanh RNN and LSTM (the classical baselines).

Usage:
    python scripts/perm_state_lab.py --selftest
    python scripts/perm_state_lab.py --gradcheck
    python scripts/perm_state_lab.py --epochs 300 --seeds 2
"""
import argparse
import json
import math
import random
import sys
import time

sys.path.insert(0, "scripts")
from s5_group import (  # noqa: E402
    ELEMENTS, GEN_MATRICES, GENERATORS, IDENTITY, INDEX, N, NUM_GENS, ORDER,
    compose, matrix,
)
from state_tracking_lab import (  # noqa: E402
    P, Readout, add_into_bias, loss_and_grad, mv, mv_back, randn, vec_add,
)
D = N * N              # 25: flattened 5x5 state
OUT = ORDER            # 120 classes
CHANCE = 1.0 / ORDER


def matmul(A, B):
    R = [0.0] * D
    for i in range(N):
        for k in range(N):
            a = A[i * N + k]
            if a == 0.0:
                continue
            for j in range(N):
                R[i * N + j] += a * B[k * N + j]
    return R


# --- structural readout: the group provides its own inverse ----------------
# THE STATE **IS** THE ANSWER. A permutation matrix already encodes its element:
# M[i][p(i)] = 1. So the class logits are just the inner product of the state
# with each of the 120 permutation matrices:
#
#     logits_c = <S, M_c> = sum_ij S_ij * M_c_ij
#
# Nothing is learned -- the "weights" are the fixed matrix catalogue -- and the
# readout covers ALL 120 classes, so it cannot memorise a training subset.
# The gradient is exact:
#
#     dL/dS = sum_c (p_c - 1[c == target]) * M_c
#
# which then flows through the existing composition backward. MEASURED NEED:
# a learned MLP head scores 1.000 on permutations seen in training and 0.000 on
# unseen ones (train lengths 1-6 reach only ~91 of 120), i.e. it is a lookup
# table. The group's own structure needs no lookup.
MAT_CATALOGUE = [matrix(p) for p in ELEMENTS]      # 120 flat 25-vectors


def struct_logits(S):
    """<S, M_c> for every class c -- the exact structural readout."""
    return [sum(S[i] * M[i] for i in range(D)) for M in MAT_CATALOGUE]


def struct_grad_and_loss(S, target):
    """CE loss over the structural logits and its exact gradient wrt S."""
    logits = struct_logits(S)
    m = max(logits)
    ex = [math.exp(v - m) for v in logits]
    s = sum(ex)
    p = [e / s for e in ex]
    loss = -math.log(max(p[target], 1e-12))
    gS = [0.0] * D
    for c in range(OUT):
        w = p[c] - (1.0 if c == target else 0.0)
        if w == 0.0:
            continue
        M = MAT_CATALOGUE[c]
        for i in range(D):
            gS[i] += w * M[i]
    return loss, gS


def verify_convention():
    """matrix(compose(a,b)) must equal M_b @ M_a. Checked, not assumed."""
    ok = True
    for a in ELEMENTS:
        for b in ELEMENTS[:30]:
            lhs = matrix(compose(a, b))
            rhs = matmul(matrix(b), matrix(a))
            if max(abs(x - y) for x, y in zip(lhs, rhs)) > 1e-12:
                ok = False
    return ok


# ---------------------------------------------------------------------------

class PermState:
    """Non-abelian group state.

    GRADIENT BEHAVIOUR (measured, and easy to get wrong when documenting):
    the forward pass ALWAYS builds the differentiable soft state, and the
    backward pass is always the soft path. `eval_hard` only switches which
    state is handed to the READOUT. So `perm_hard` is effectively a
    straight-through estimator: the exact permutation is used for evaluation
    while the gradient flows through the soft relaxation.

    That makes the two evaluation modes a comparison of *decoders*, not of two
    different training regimes -- which is what the S_5 results must be read
    as. The construction itself was proven sound separately
    (scripts/diagnose_s5.py, STEP 1: freeze W=I, train the head only, and exact
    accuracy reaches 0.908 at L=4 against chance 0.008).
    """

    def __init__(self, rng, hidden=32, tau=1.0, init="identity",
                 readout="mlp"):
        """init:
          "identity" (DEFAULT) -- W = I + small noise, so argmax(raw) is the
              correct generator from the first step. MEASURED NECESSARY: with
              a small random W the softmax over generators is near-uniform at
              every token, the per-token mixture is the same near-average
              doubly-stochastic matrix, and the product state carries almost no
              input information (measured input-dependence 0.109 vs 0.183 for
              W=I). The head then sees a constant feature and the choice matrix
              never learns: per-token choice accuracy stayed at chance
              (0.198-0.214) across runs. With W=I it reaches 1.000.
              See scripts/s5_init_lab.py and reports/nonabelian_s5_paper.md.
          "random" -- the small-random baseline, kept for comparison.

        readout:
          "mlp"   -- learned MLP over the flattened matrix. MEASURED to be a
              pure LOOKUP TABLE: 1.000 on permutations seen in training, 0.000
              on unseen ones (train lengths 1-6 reach only ~91 of 120).
          "exact" -- STRUCTURAL inverse, logits_c = <S, M_c>. No parameters, so
              no memorisation is possible. Requires the state to actually BE a
              permutation matrix, which needs a SHARP tau (see below).

        tau:
          Temperature of the per-token generator softmax. THIS IS THE DECISIVE
          HYPER-PARAMETER. With tau=1 the choice is diffuse and the product of
          mixtures diffuses toward uniform, so the state stops being a group
          element at all. Measured with the structural readout and perfect
          choice weights:

              tau=1.0  dist-to-perm 1.7e+00   L=4 accuracy 0.095
              tau=0.1  dist-to-perm 1.8e-03   1.000 at L=4,12,48,200
              tau<=0.03 dist-to-perm ~0       1.000 at every length

          At tau<=0.1 the state is an exact group element and the accuracy is
          1.000 at EVERY length, including 33x beyond anything trained on.
          See scripts/s5_tau_sweep.py.
        """
        self.tau = tau
        self.emb = NUM_GENS                    # one-hot width
        self.readout_kind = readout
        # W is NUM_GENS x emb: raw_k = sum_j W[k][j] * onehot(x)[j] + b_k.
        # A per-generator SCALAR weight would be wrong: input index 0 would
        # contribute 0 to every logit, i.e. generator 0 could never be chosen.
        if init == "identity":
            noise = 0.05
            d = [0.0] * (NUM_GENS * NUM_GENS)
            for k in range(NUM_GENS):
                d[k * NUM_GENS + k] = 1.0
            for i in range(len(d)):
                d[i] += rng.gauss(0.0, noise)
            self.W = P(d)
        else:
            self.W = P([randn(1.0 / math.sqrt(self.emb), rng)
                        for _ in range(NUM_GENS * self.emb)])
        self.b = P([0.0] * NUM_GENS)
        # The MLP head is only built for readout="mlp". For readout="exact" it
        # is never called: the structural readout is logits_c = <S, M_c> with
        # the FIXED matrix catalogue as weights. Building it anyway left 4792
        # dead parameters in params(), which the optimiser still updated and
        # which made every reported parameter count wrong.
        self.head = Readout(D, hidden, OUT, rng) \
            if self.readout_kind == "mlp" else None
        self.eval_hard = False        # False: soft eval, True: exact eval

    def params(self):
        """Trainable parameters. With readout="exact" the head does not exist,
        so this is exactly the per-token choice matrix: NUM_GENS^2 + NUM_GENS
        (W plus bias)."""
        if self.head is None:
            return [self.W, self.b]
        return [self.W, self.b] + self.head.params()

    def _onehot(self, x):
        return [1.0 if i == x else 0.0 for i in range(self.emb)]

    def _choices(self, xs):
        out = []
        for x in xs:
            xv = self._onehot(x)
            out.append((xv, vec_add(mv(self.W, xv, NUM_GENS, self.emb),
                                    self.b.data)))
        return out

    def _soft_state(self, choices):
        S = [0.0] * D
        for i in range(N):
            S[i * N + i] = 1.0
        cache = []
        for xv, raw in choices:
            scaled = [v / self.tau for v in raw]
            m = max(scaled)
            ex = [math.exp(v - m) for v in scaled]
            den = sum(ex)
            a = [e / den for e in ex]
            G = [0.0] * D
            for k in range(NUM_GENS):
                ak = a[k]
                if ak == 0.0:
                    continue
                Mk = GEN_MATRICES[k]
                for idx in range(D):
                    G[idx] += ak * Mk[idx]
            S_prev = S
            S = matmul(G, S_prev)
            cache.append((S_prev, a, G, xv))
        return S, cache

    def _hard_state(self, choices):
        state = IDENTITY
        for xv, raw in choices:
            k = max(range(NUM_GENS), key=lambda i: raw[i])
            state = compose(state, GENERATORS[k])
        return matrix(state)

    def forward(self, xs):
        choices = self._choices(xs)
        S, cache = self._soft_state(choices)
        self._cache = cache
        self._S = S
        if self.readout_kind == "exact":
            # STRUCTURAL readout: logits_c = <S, M_c>. No parameters.
            return struct_logits(S)
        feat = self._hard_state(choices) if self.eval_hard else S
        self._feat = feat
        return self.head.forward(feat)

    def backward(self, glogits):
        """glogits is dL/dS for the structural readout (already computed
        analytically by struct_grad_and_loss), or dL/dlogits for the MLP."""
        if self.readout_kind == "exact":
            gS = glogits
            self._backward_from_state(gS)
            return
        gS = self.head.backward(glogits)
        self._backward_from_state(gS)

    def _backward_from_state(self, gS):
        for t in range(len(self._cache) - 1, -1, -1):
            S_prev, a, G, xv = self._cache[t]
            # S = G @ S_prev
            gG = [0.0] * D                                   # dG[i][k]
            for i in range(N):
                for k in range(N):
                    acc = 0.0
                    for j in range(N):
                        acc += gS[i * N + j] * S_prev[k * N + j]
                    gG[i * N + k] = acc
            gS_new = [0.0] * D                               # dS_prev[k][j]
            for k in range(N):
                for j in range(N):
                    acc = 0.0
                    for i in range(N):
                        acc += gS[i * N + j] * G[i * N + k]
                    gS_new[k * N + j] = acc
            # G = sum_k a_k M_k  =>  gA_k = <gG, M_k>
            gA = [0.0] * NUM_GENS
            for k in range(NUM_GENS):
                Mk = GEN_MATRICES[k]
                acc = 0.0
                for idx in range(D):
                    if Mk[idx] != 0.0:
                        acc += gG[idx]
                gA[k] = acc
            # softmax backward, incl. the tau scaling on raw
            dot = sum(gA[k] * a[k] for k in range(NUM_GENS))
            graw = [a[k] * (gA[k] - dot) / self.tau for k in range(NUM_GENS)]
            add_into_bias(self.b, graw)
            # raw = W @ onehot(x)  =>  dW = graw (x) onehot(x)
            mv_back(self.W, xv, graw, NUM_GENS, self.emb)
            gS = gS_new


class BagModel:
    """Order-blind control: counts each generator. Commutative by design."""

    def __init__(self, rng, hidden=32):
        self.head = Readout(NUM_GENS, hidden, OUT, rng)

    def params(self):
        return self.head.params()

    def forward(self, xs):
        f = [float(sum(1 for v in xs if v == k)) for k in range(NUM_GENS)]
        self._f = f
        return self.head.forward(f)

    def backward(self, g):
        self.head.backward(g)


class RNNModel:
    def __init__(self, rng, hidden=32, h=24):
        self.h, self.emb = h, NUM_GENS
        self.Wx = P([randn(1.0 / math.sqrt(self.emb), rng)
                     for _ in range(h * self.emb)])
        self.Wh = P([randn(1.0 / math.sqrt(h), rng) for _ in range(h * h)])
        self.b = P([0.0] * h)
        self.head = Readout(h, hidden, OUT, rng)

    def params(self):
        return [self.Wx, self.Wh, self.b] + self.head.params()

    def forward(self, xs):
        h = [0.0] * self.h
        self._cache = []
        for k in xs:
            xv = [1.0 if i == k else 0.0 for i in range(self.emb)]
            pre = vec_add(vec_add(mv(self.Wx, xv, self.h, self.emb),
                                  mv(self.Wh, h, self.h, self.h)), self.b.data)
            h = [math.tanh(v) for v in pre]
            self._cache.append((xv, h[:], pre))
        return self.head.forward(h)

    def backward(self, g):
        gh = self.head.backward(g)
        for t in range(len(self._cache) - 1, -1, -1):
            xv, h, pre = self._cache[t]
            prev = self._cache[t - 1][1] if t > 0 else [0.0] * self.h
            gpre = [gh[i] * (1 - h[i] * h[i]) for i in range(self.h)]
            add_into_bias(self.b, gpre)
            mv_back(self.Wx, xv, gpre, self.h, self.emb)
            gh = mv_back(self.Wh, prev, gpre, self.h, self.h)


class LSTMModel:
    def __init__(self, rng, hidden=32, h=24):
        self.h, self.emb = h, NUM_GENS
        H = h
        self.W = P([randn(1.0 / math.sqrt(self.emb), rng)
                    for _ in range(4 * H * self.emb)])
        self.U = P([randn(1.0 / math.sqrt(H), rng) for _ in range(4 * H * H)])
        self.b = P([0.0] * (4 * H))
        self.head = Readout(H, hidden, OUT, rng)

    def params(self):
        return [self.W, self.U, self.b] + self.head.params()

    def forward(self, xs):
        H = self.h
        h = [0.0] * H
        c = [0.0] * H
        cache = []
        for k in xs:
            xv = [1.0 if i == k else 0.0 for i in range(self.emb)]
            z = vec_add(vec_add(mv(self.W, xv, 4 * H, self.emb),
                                mv(self.U, h, 4 * H, H)), self.b.data)
            i = [1 / (1 + math.exp(-z[q])) for q in range(H)]
            f = [1 / (1 + math.exp(-z[H + q])) for q in range(H)]
            o = [1 / (1 + math.exp(-z[2 * H + q])) for q in range(H)]
            g = [math.tanh(z[3 * H + q]) for q in range(H)]
            c_new = [f[q] * c[q] + i[q] * g[q] for q in range(H)]
            tc = [math.tanh(v) for v in c_new]
            h_new = [o[q] * tc[q] for q in range(H)]
            cache.append((xv, h[:], c[:], z, i, f, o, g, c_new, tc))
            h, c = h_new, c_new
        self._cache = cache
        return self.head.forward(h)

    def backward(self, glogits):
        H = self.h
        gh = self.head.backward(glogits)
        gc = [0.0] * H
        for t in range(len(self._cache) - 1, -1, -1):
            xv, h_prev, c_prev, z, i, f, o, g, c_new, tc = self._cache[t]
            go = [gh[q] * tc[q] for q in range(H)]
            gtc = [gh[q] * o[q] for q in range(H)]
            gcn = [gtc[q] * (1 - tc[q] * tc[q]) + gc[q] for q in range(H)]
            gi = [gcn[q] * g[q] for q in range(H)]
            gg = [gcn[q] * i[q] for q in range(H)]
            gf = [gcn[q] * c_prev[q] for q in range(H)]
            gc = [gcn[q] * f[q] for q in range(H)]
            gz = [0.0] * (4 * H)
            for q in range(H):
                gz[q] = gi[q] * i[q] * (1 - i[q])
                gz[H + q] = gf[q] * f[q] * (1 - f[q])
                gz[2 * H + q] = go[q] * o[q] * (1 - o[q])
                gz[3 * H + q] = gg[q] * (1 - g[q] * g[q])
            add_into_bias(self.b, gz)
            mv_back(self.W, xv, gz, 4 * H, self.emb)
            gh = mv_back(self.U, h_prev, gz, 4 * H, H)


# ---------------------------------------------------------------------------
def _task_gen(rng, L):
    xs = [rng.randrange(NUM_GENS) for _ in range(L)]
    state = IDENTITY
    for g in xs:
        state = compose(state, GENERATORS[g])
    return xs, INDEX[state]


def accuracy(logits, target):
    """Top-1 over the 120 classes. Local to this file: the shared helper in
    state_tracking_lab takes a loss-kind argument (bce/ce) that does not apply
    to a 120-way non-abelian classification."""
    return 1.0 if max(range(len(logits)), key=lambda i: logits[i]) == target \
        else 0.0


def choice_accuracy(m, n=200, L=6, seed=5):
    """Per-token generator-choice accuracy of a PermState (chance 1/NUM_GENS).

    The canonical definition, next to the model it measures. Callers that only
    need the number import this rather than carrying a copy.
    """
    rng = random.Random(seed)
    tot = good = 0
    for _ in range(n):
        xs, _ = _task_gen(rng, L)
        for x, (xv, raw) in zip(xs, m._choices(xs)):
            tot += 1
            good += (max(range(NUM_GENS), key=lambda i: raw[i]) == x)
    return good / tot


def build(mode, rng, tau=1.0):
    if mode == "bag":
        return BagModel(rng)
    if mode == "rnn":
        return RNNModel(rng)
    if mode == "lstm":
        return LSTMModel(rng)
    m = PermState(rng, tau=tau)
    m.eval_hard = (mode == "perm_hard")
    return m


def train_phase(m, data, epochs, lr, anneal=None):
    """Train. anneal=(tau_start, tau_end) linearly sharpens the generator
    softmax over training.

    WHY: a per-token group choice is a HARD decision. With a flat tau the
    softmax over 5 generators gives a diffuse gradient, and the credit that
    reaches early tokens has to survive a long product of matrix
    multiplications; measured behaviour is unstable -- the same configuration
    reached choice_acc 0.610 in one run and sat at chance (0.198-0.214) in
    others. Annealing starts smooth (broad gradient, everything gets signal)
    and ends sharp (the choice becomes the hard decision actually used at
    evaluation), which is the standard remedy for training discrete decisions.
    """
    ps = m.params()
    mo = [[0.0] * p.n for p in ps]
    vo = [[0.0] * p.n for p in ps]
    b1, b2, eps = 0.9, 0.999, 1e-8
    step = 0
    for ep in range(epochs):
        if anneal is not None:
            t0, t1 = anneal
            frac = ep / max(1, epochs - 1)
            m.tau = t0 + (t1 - t0) * frac
        random.shuffle(data)
        for xs, t in data:
            for p in ps:
                p.zero()
            logits = m.forward(xs)
            _, g = loss_and_grad(logits, t, "ce")
            m.backward(g)
            step += 1
            bc1, bc2 = 1 - b1 ** step, 1 - b2 ** step
            for i, p in enumerate(ps):
                for j in range(p.n):
                    gj = p.grad[j]
                    mo[i][j] = b1 * mo[i][j] + (1 - b1) * gj
                    vo[i][j] = b2 * vo[i][j] + (1 - b2) * gj * gj
                    p.data[j] -= lr * (mo[i][j] / bc1) / \
                        (math.sqrt(vo[i][j] / bc2) + eps)


def run(mode, train_l, test_l, epochs, seeds, n_train, n_test, lr, tau):
    per = {L: [] for L in test_l}
    t0 = time.time()
    for s in range(seeds):
        rng = random.Random(1300 + s)
        m = build(mode, rng, tau=tau)
        data = [_task_gen(rng, random.choice(train_l)) for _ in range(n_train)]
        train_phase(m, data, epochs, lr)
        for L in test_l:
            c = 0
            for _ in range(n_test):
                xs, tg = _task_gen(rng, L)
                c += accuracy(m.forward(xs), tg)
            per[L].append(c / n_test)
    return {"mean": {L: sum(v) / len(v) for L, v in per.items()},
            "secs": round(time.time() - t0, 1)}


def gradcheck_perm():
    """Finite differences for the soft non-abelian path."""
    print("=" * 74)
    print("gradcheck: PermState soft path (matrix product, non-commutative)")
    print("=" * 74)
    ok_all = True
    for L in (1, 3, 6):
        rng = random.Random(0)
        xs, t = _task_gen(rng, L)
        m = PermState(random.Random(1), tau=1.0)
        ps = m.params()
        for p in ps:
            p.zero()
        _, g = loss_and_grad(m.forward(xs), t, "ce")
        m.backward(g)
        eps = 1e-6
        worst = 0.0
        n = 0
        for pi, p in enumerate(ps):
            for j in range(0, p.n, max(1, p.n // 8)):
                orig = p.data[j]
                p.data[j] = orig + eps
                lp, _ = loss_and_grad(m.forward(xs), t, "ce")
                p.data[j] = orig - eps
                lm, _ = loss_and_grad(m.forward(xs), t, "ce")
                p.data[j] = orig
                num = (lp - lm) / (2 * eps)
                ae = abs(num - p.grad[j])
                sc = max(1e-6, abs(num) + abs(p.grad[j]))
                if ae > 1e-6:
                    worst = max(worst, ae / sc)
                n += 1
        ok = worst < 1e-3
        ok_all &= ok
        print(f"  L={L:3d} params={sum(p.n for p in ps):5d} checked={n:3d} "
              f"worst_rel={worst:.3e} {'OK' if ok else 'FAIL'}")
    print("GRADCHECK:", "ALL OK" if ok_all else "FAILURES PRESENT")
    return ok_all


def gradcheck_mlp_path():
    """Finite-difference check of the LEARNED-head path.

    WHY SEPARATE: `--gradcheck` covers the soft group-state path, and the
    structural readout has its own check. Neither exercises the MLP head that
    readout="mlp" still uses, so a regression there would pass the whole suite.
    Also guards the head-construction optimisation: readout="exact" must build
    NO head -- otherwise ~4792 dead parameters silently return to params().
    """
    print("=" * 78)
    print("gradcheck: MLP-head path  (head presence, params, dL/dW vs FD, learning)")
    print("=" * 78)
    ok = True

    def ce_grad(logits, t):
        # CORRECT upstream gradient for CE wrt LOGITS: p - onehot(t).
        m = max(logits)
        ex = [math.exp(v - m) for v in logits]
        s = sum(ex)
        g = [e / s for e in ex]
        g[t] -= 1.0
        return g

    def loss_of(m, xs, t):
        lo = m.forward(xs)
        mx = max(lo)
        ex = [math.exp(v - mx) for v in lo]
        return -math.log(max(ex[t] / sum(ex), 1e-30))

    # -- the head exists only for readout="mlp" ---------------------------
    for ro, want in (("mlp", True), ("exact", False)):
        m = PermState(random.Random(1), tau=0.1, readout=ro)
        has = m.head is not None
        n = sum(p.n for p in m.params())
        good = (has == want)
        ok &= good
        print(f"  readout={ro:5s} head={str(has):5s} params={n:5d}  "
              f"{'OK' if good else 'FAIL'}")
    K = NUM_GENS
    m = PermState(random.Random(1), tau=0.1, readout="exact")
    n_exact = sum(p.n for p in m.params())
    good = (n_exact == K * K + K)
    ok &= good
    print(f"  exact params == K^2+K = {K*K+K}: {n_exact}  "
          f"{'OK' if good else 'FAIL'}")

    # -- dL/dW against central differences --------------------------------
    m = PermState(random.Random(1), tau=0.1, readout="mlp")
    xs, t = _task_gen(random.Random(2), 4)
    lo = m.forward(xs)
    for p in m.params():
        p.zero()
    m.backward(ce_grad(lo, t))
    p = m.W
    base, ana = p.data[7], p.grad[7]
    eps = 1e-6
    p.data[7] = base + eps
    lp = loss_of(m, xs, t)
    p.data[7] = base - eps
    lm = loss_of(m, xs, t)
    p.data[7] = base
    num = (lp - lm) / (2 * eps)
    diff = abs(ana - num)
    good = (diff < 1e-8)
    ok &= good
    print(f"  dL/dW[7]: analytic={ana:.6e} numeric={num:.6e} "
          f"abs_diff={diff:.2e}  {'OK' if good else 'FAIL'}")

    # -- the head still trains --------------------------------------------
    rng = random.Random(7)
    m = PermState(rng, tau=0.1, readout="mlp")
    data = [_task_gen(rng, random.choice(range(1, 7))) for _ in range(64)]
    train_phase(m, data, 120, 0.05)
    ca = choice_accuracy(m, n=80, L=6, seed=9)
    good = (ca > 0.5)
    ok &= good
    print(f"  choice_acc after 120 epochs = {ca:.3f}  "
          f"{'OK' if good else 'FAIL'}")

    print("MLP-PATH GRADCHECK:", "ALL OK" if ok else "FAILURES PRESENT")
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--gradcheck", action="store_true")
    ap.add_argument("--gradcheck-mlp", action="store_true")
    ap.add_argument("--epochs", type=int, default=300)
    ap.add_argument("--seeds", type=int, default=2)
    ap.add_argument("--tau", type=float, default=1.0)
    args = ap.parse_args()

    if args.selftest:
        ok = verify_convention()
        print(f"matrix convention matrix(compose(a,b)) == M_b @ M_a : "
              f"{'OK' if ok else 'FAIL'}")
        sys.exit(0 if ok else 1)
    if args.gradcheck:
        sys.exit(0 if gradcheck_perm() else 1)
    if args.gradcheck_mlp:
        sys.exit(0 if gradcheck_mlp_path() else 1)

    print("=" * 84)
    print("NON-ABELIAN state tracking: S_5 (120 elements, non-solvable)")
    print(f"chance = 1/120 = {CHANCE:.4f}    tau = {args.tau}")
    print("=" * 84)

    train_l = list(range(1, 7))
    test_l = [4, 6, 12, 24, 48]
    modes = ["bag", "rnn", "lstm", "perm_soft", "perm_hard"]
    labels = {"bag": "bag (order-blind)", "rnn": "SimpleRNN(tanh)",
              "lstm": "LSTM", "perm_soft": "PermState soft eval",
              "perm_hard": "PermState EXACT eval"}

    res = {}
    for mode in modes:
        r = run(mode, train_l, test_l, args.epochs, args.seeds,
                n_train=24, n_test=32, lr=0.05, tau=args.tau)
        res[mode] = r
        print(f"  done: {mode:14s} ({r['secs']}s)")

    print()
    print("=" * 84)
    print(f"S_5 product task   trained on lengths {min(train_l)}-{max(train_l)}"
          f"   '*' = NEVER seen in training")
    print("=" * 84)
    print("  " + f"{'mechanism':<22s}" +
          "".join(f"{str(L) + ('*' if L not in train_l else ' '):>9s}"
                  for L in test_l))
    print("  " + "-" * (22 + 9 * len(test_l)))
    for mode in modes:
        print("  " + f"{labels[mode]:<22s}" +
              "".join(f"{res[mode]['mean'][L]:9.3f}" for L in test_l))
    print()

    with open("reports/perm_state_results.json", "w", encoding="utf-8") as f:
        json.dump(res, f, indent=2)
    print("wrote reports/perm_state_results.json")


if __name__ == "__main__":
    main()
