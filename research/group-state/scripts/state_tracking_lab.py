#!/usr/bin/env python3
"""State-Tracking Lab -- OpenAmer neural architecture research.

THE FRONTIER
------------
The hardest open wall in sequence architectures is STATE TRACKING: computing
order-sensitive, unbounded state such as parity, modular counting, or a
flip-flop. It is formalised in "The Illusion of State in State-Space Models"
(arXiv 2404.08819, 2024): SSM/linear-RNN recurrences are provably in a weak
circuit class and cannot solve these tasks at all, regardless of width or
training. DeltaProduct (2025) and "Expressivity-Efficiency Tradeoffs for
Hybrid Sequence Models" (2026) are current attempts at the same wall.

THE HYPOTHESIS UNDER TEST
-------------------------
A saturating scalar recurrence h_t = tanh(Wx + Uh) can only approximate
state tracking by *magnitude*. Parity needs the running count mod 2, which a
saturating map cannot represent for unbounded lengths.

A PHASE cannot saturate. If the hidden state is a unit-modulus complex number
and each token applies a learned rotation,

        z_t = z_{t-1} * exp(i * theta(x_t))

then the group structure is exact:

        theta(x) = pi*x   =>   z_T = exp(i*pi*sum(x)) = (-1)^(#ones) = PARITY
        theta(x) = 2*pi*x/k =>  z_T encodes sum(x) mod k

No depth, no width, no memorisation: one rotation per token, O(1) state.
This is the same oscillation that our own oa_ripple activation hinted at
(sin(x)*sigmoid(x)); here the oscillation is the *state*, not the nonlinearity.

WHAT THIS SCRIPT DOES
---------------------
1. Implements four state mechanisms with an IDENTICAL readout MLP, so the
   comparison isolates the temporal mechanism alone:
       WindowMLP  - no recurrence, bag-of-tokens statistics
       SimpleRNN  - tanh recurrence (the classic saturating baseline)
       LSTM       - the strong classical baseline
       Rotor      - NEW: unit-modulus phase accumulation (this work)
2. Trains on SHORT sequences and evaluates on SHORTER-EQUAL and LONGER lengths
   never seen in training. Length generalisation is the discriminator: a
   mechanism that pattern-matches collapses; one that tracks state holds.
3. Verifies every analytic gradient against finite differences (--gradcheck)
   so the numbers cannot be an artefact of a wrong derivative.

Pure Python. No numpy, no torch.

Usage:
    python scripts/state_tracking_lab.py --gradcheck
    python scripts/state_tracking_lab.py --quick
    python scripts/state_tracking_lab.py --seeds 3 --epochs 600
"""
import argparse
import json
import math
import random
import sys
import time

# ===========================================================================
# primitives
# ===========================================================================


def sigmoid(x):
    if x < -60:
        return 0.0
    if x > 60:
        return 1.0
    return 1.0 / (1.0 + math.exp(-x))


class P:
    """A parameter tensor with a flat row-major buffer + matching gradient."""

    __slots__ = ("data", "grad", "n")

    def __init__(self, data):
        self.data = list(data)
        self.n = len(self.data)
        self.grad = [0.0] * self.n

    def zero(self):
        for i in range(self.n):
            self.grad[i] = 0.0


def randn(scale, rng=None):
    """Standard normal draw, scaled.

    IMPORTANT: pass the model's own `rng`. The default falls back to the
    global `random` module, which makes weight initialisation NON-reproducible
    -- the same seed then yields different models, and a gradient check flips
    between pass and fail. Every model below forwards its own seeded rng.
    """
    return (rng if rng is not None else random).gauss(0.0, scale)


def mv(p, x, rows, cols):
    """y = W x, W is rows x cols row-major inside p."""
    d = p.data
    out = [0.0] * rows
    for r in range(rows):
        base = r * cols
        s = 0.0
        for c in range(cols):
            s += d[base + c] * x[c]
        out[r] = s
    return out


def mv_back(p, x, gout, rows, cols):
    """Accumulate dW += gout (x) x, return dx."""
    d = p.data
    g = p.grad
    gx = [0.0] * cols
    for r in range(rows):
        gr = gout[r]
        if gr == 0.0:
            continue
        base = r * cols
        for c in range(cols):
            g[base + c] += gr * x[c]
            gx[c] += gr * d[base + c]
    return gx


def add_into_bias(p, gout):
    for i in range(p.n):
        p.grad[i] += gout[i]


def vec_add(a, b):
    return [x + y for x, y in zip(a, b)]


# ===========================================================================
# tasks
# ===========================================================================


def gen_parity(rng, n):
    """Bits -> 1 logit, target = sum mod 2."""
    xs = [1.0 if rng.random() < 0.5 else 0.0 for _ in range(n)]
    return xs, float(int(sum(xs)) % 2)


def gen_flipflop(rng, n):
    """Tokens: -1/+1 = write, 0 = ignore. Target = sign of last write."""
    xs = [0.0] * n
    for _ in range(n):
        if rng.random() < 0.25:
            xs[rng.randrange(n)] = 1.0 if rng.random() < 0.5 else -1.0
    last = 0.0
    for v in xs:
        if v != 0.0:
            last = v
    return xs, 1.0 if last >= 0.0 else 0.0


def gen_modk(rng, n, k):
    """Values in 0..k-1 -> k logits, target = sum mod k."""
    xs = [float(rng.randrange(k)) for _ in range(n)]
    return xs, int(sum(xs)) % k


TASKS = {
    "parity": {"gen": gen_parity, "out": 1, "loss": "bce"},
    "flipflop": {"gen": gen_flipflop, "out": 1, "loss": "bce"},
    "mod7": {"gen": lambda r, n: gen_modk(r, n, 7), "out": 7, "loss": "ce"},
}


# ===========================================================================
# shared readout -- identical for every mechanism, so the comparison isolates
# the recurrence and nothing else
# ===========================================================================


class Readout:
    def __init__(self, feat_dim, hidden, out_dim, rng):
        self.feat_dim = feat_dim
        self.hidden = hidden
        self.out_dim = out_dim
        self.W1 = P([randn(1.0 / math.sqrt(feat_dim), rng)
                     for _ in range(hidden * feat_dim)])
        self.b1 = P([0.0] * hidden)
        self.W2 = P([randn(1.0 / math.sqrt(hidden), rng)
                     for _ in range(out_dim * hidden)])
        self.b2 = P([0.0] * out_dim)

    def params(self):
        return [self.W1, self.b1, self.W2, self.b2]

    def forward(self, f):
        h_pre = mv(self.W1, f, self.hidden, self.feat_dim)
        h = vec_add(h_pre, self.b1.data)
        a = [max(0.0, v) for v in h]          # relu
        logits = vec_add(mv(self.W2, a, self.out_dim, self.hidden),
                         self.b2.data)
        self._f, self._h_pre, self._a = f, h_pre, a
        return logits

    def backward(self, glogits):
        gb2 = glogits
        add_into_bias(self.b2, gb2)
        ga = mv_back(self.W2, self._a, glogits, self.out_dim, self.hidden)
        gh = [ga[i] if self._h_pre[i] > 0 else 0.0
              for i in range(self.hidden)]
        add_into_bias(self.b1, gh)
        gf = mv_back(self.W1, self._f, gh, self.hidden, self.feat_dim)
        return gf


# ===========================================================================
# mechanisms
# ===========================================================================


class WindowMLP:
    """No recurrence: bag-of-token statistics. Cannot see order at all."""

    name = "WindowMLP(bag)"
    feat_dim = 5

    def __init__(self, xs_dim, hidden, out_dim, rng, hidden_dim=16):
        self.readout = Readout(self.feat_dim, hidden, out_dim, rng)

    def params(self):
        return self.readout.params()

    def features(self, xs):
        n = len(xs)
        s = sum(xs)
        return [s, s / n if n else 0.0, float(n),
                min(xs) if xs else 0.0, max(xs) if xs else 0.0]

    def forward(self, xs):
        self._f = self.features(xs)
        return self.readout.forward(self._f)

    def backward(self, glogits):
        self.readout.backward(glogits)


class SimpleRNN:
    """h_t = tanh(Wx x_t + Wh h_{t-1} + b) -- the saturating baseline."""

    name = "SimpleRNN(tanh)"

    def __init__(self, xs_dim, hidden, out_dim, rng, hidden_dim=16):
        self.in_dim, self.h = 1, hidden_dim
        self.Wx = P([randn(1.0 / math.sqrt(self.in_dim), rng)
                     for _ in range(self.h * self.in_dim)])
        self.Wh = P([randn(1.0 / math.sqrt(self.h), rng)
                     for _ in range(self.h * self.h)])
        self.b = P([0.0] * self.h)
        self.readout = Readout(self.h, hidden, out_dim, rng)

    def params(self):
        return [self.Wx, self.Wh, self.b] + self.readout.params()

    def forward(self, xs):
        h = [0.0] * self.h
        self._cache = []
        for x in xs:
            xv = [x]
            pre = vec_add(vec_add(mv(self.Wx, xv, self.h, self.in_dim),
                                  mv(self.Wh, h, self.h, self.h)),
                          self.b.data)
            h = [math.tanh(v) for v in pre]
            self._cache.append((xv, h[:], pre))
        self._hT = h
        return self.readout.forward(h)

    def backward(self, glogits):
        gh = self.readout.backward(glogits)
        for t in range(len(self._cache) - 1, -1, -1):
            xv, h, pre = self._cache[t]
            prev_h = self._cache[t - 1][1] if t > 0 else [0.0] * self.h
            gpre = [gh[i] * (1.0 - h[i] * h[i]) for i in range(self.h)]
            add_into_bias(self.b, gpre)
            mv_back(self.Wx, xv, gpre, self.h, self.in_dim)
            gh = mv_back(self.Wh, prev_h, gpre, self.h, self.h)


class LSTM:
    """Full LSTM -- the strong classical baseline."""

    name = "LSTM"

    def __init__(self, xs_dim, hidden, out_dim, rng, hidden_dim=16):
        self.in_dim, self.h = 1, hidden_dim
        H = self.h
        self.W = P([randn(1.0 / math.sqrt(self.in_dim), rng)
                    for _ in range(4 * H * self.in_dim)])
        self.U = P([randn(1.0 / math.sqrt(H), rng) for _ in range(4 * H * H)])
        self.b = P([0.0] * (4 * H))
        self.readout = Readout(H, hidden, out_dim, rng)

    def params(self):
        return [self.W, self.U, self.b] + self.readout.params()

    def forward(self, xs):
        H = self.h
        h = [0.0] * H
        c = [0.0] * H
        cache = []
        for x in xs:
            xv = [x]
            z = vec_add(vec_add(mv(self.W, xv, 4 * H, self.in_dim),
                                mv(self.U, h, 4 * H, H)),
                        self.b.data)
            i = [sigmoid(z[k]) for k in range(H)]
            f = [sigmoid(z[H + k]) for k in range(H)]
            o = [sigmoid(z[2 * H + k]) for k in range(H)]
            g = [math.tanh(z[3 * H + k]) for k in range(H)]
            c_new = [f[k] * c[k] + i[k] * g[k] for k in range(H)]
            tc = [math.tanh(v) for v in c_new]
            h_new = [o[k] * tc[k] for k in range(H)]
            cache.append((xv, h[:], c[:], z, i, f, o, g, c_new, tc, h_new))
            h, c = h_new, c_new
        self._cache = cache
        return self.readout.forward(h)

    def backward(self, glogits):
        H = self.h
        gh = self.readout.backward(glogits)
        gc = [0.0] * H
        for t in range(len(self._cache) - 1, -1, -1):
            (xv, h_prev, c_prev, z, i, f, o, g, c_new, tc,
             h_new) = self._cache[t]
            go = [gh[k] * tc[k] for k in range(H)]
            gtc = [gh[k] * o[k] for k in range(H)]
            gc_new = [gtc[k] * (1.0 - tc[k] * tc[k]) + gc[k] for k in range(H)]
            gi = [gc_new[k] * g[k] for k in range(H)]
            gg = [gc_new[k] * i[k] for k in range(H)]
            gf = [gc_new[k] * c_prev[k] for k in range(H)]
            gc_prev = [gc_new[k] * f[k] for k in range(H)]
            gz = [0.0] * (4 * H)
            for k in range(H):
                gz[k] = gi[k] * i[k] * (1.0 - i[k])
                gz[H + k] = gf[k] * f[k] * (1.0 - f[k])
                gz[2 * H + k] = go[k] * o[k] * (1.0 - o[k])
                gz[3 * H + k] = gg[k] * (1.0 - g[k] * g[k])
            add_into_bias(self.b, gz)
            mv_back(self.W, xv, gz, 4 * H, self.in_dim)
            gh = mv_back(self.U, h_prev, gz, 4 * H, H)
            gc = gc_prev


class Rotor:
    """NEW: unit-modulus phase accumulation.

        theta_t = w . x_t + b            (learned rotation per token)
        z_t     = z_{t-1} * exp(i*theta_t)
        z_0     = 1

    The state is d unit-modulus complex numbers (phase is the group element).
    Multiplication by exp(i*theta) is an exact group action, so cyclic state
    (parity = Z_2, mod-k = Z_k) is representable WITHOUT saturation, at O(1)
    state and one rotation per token. Readout sees [Re(z), Im(z)].
    """

    name = "Rotor(phase)"

    def __init__(self, xs_dim, hidden, out_dim, rng, hidden_dim=16):
        self.d = hidden_dim
        self.in_dim = 1
        scale = 1.0 / math.sqrt(self.in_dim)
        self.Wt = P([randn(scale, rng) for _ in range(self.d * self.in_dim)])
        self.bt = P([randn(0.5, rng) for _ in range(self.d)])  # offset spread
        self.feat_dim = 2 * self.d
        self.readout = Readout(self.feat_dim, hidden, out_dim, rng)

    def params(self):
        return [self.Wt, self.bt] + self.readout.params()

    def forward(self, xs):
        d = self.d
        a = [1.0] * d
        b = [0.0] * d
        self._cache = []
        for x in xs:
            xv = [x]
            th = vec_add(mv(self.Wt, xv, d, self.in_dim), self.bt.data)
            cs = [math.cos(v) for v in th]
            sn = [math.sin(v) for v in th]
            a_prev, b_prev = a, b
            a = [a_prev[k] * cs[k] - b_prev[k] * sn[k] for k in range(d)]
            b = [a_prev[k] * sn[k] + b_prev[k] * cs[k] for k in range(d)]
            self._cache.append((xv, a_prev, b_prev, cs, sn, a[:], b[:]))
        f = []
        for k in range(d):
            f.append(a[k])
            f.append(b[k])
        self._f = f
        return self.readout.forward(f)

    def backward(self, glogits):
        d = self.d
        gf = self.readout.backward(glogits)
        ga = [gf[2 * k] for k in range(d)]
        gb = [gf[2 * k + 1] for k in range(d)]
        for t in range(len(self._cache) - 1, -1, -1):
            xv, a_prev, b_prev, cs, sn, a_new, b_new = self._cache[t]
            # d/da_prev, d/db_prev
            ga_prev = [ga[k] * cs[k] + gb[k] * sn[k] for k in range(d)]
            gb_prev = [-ga[k] * sn[k] + gb[k] * cs[k] for k in range(d)]
            # d/dtheta
            gth = []
            for k in range(d):
                da_dth = -a_prev[k] * sn[k] - b_prev[k] * cs[k]
                db_dth = a_prev[k] * cs[k] - b_prev[k] * sn[k]
                gth.append(ga[k] * da_dth + gb[k] * db_dth)
            add_into_bias(self.bt, gth)
            mv_back(self.Wt, xv, gth, d, self.in_dim)
            ga, gb = ga_prev, gb_prev


MECHANISMS = {
    "window": WindowMLP,
    "rnn": SimpleRNN,
    "lstm": LSTM,
    "rotor": Rotor,
}


# ===========================================================================
# loss
# ===========================================================================


def loss_and_grad(logits, target, kind):
    if kind == "bce":
        p = sigmoid(logits[0])
        t = target
        p_c = min(max(p, 1e-12), 1 - 1e-12)
        loss = -(t * math.log(p_c) + (1 - t) * math.log(1 - p_c))
        return loss, [p - t]
    # softmax cross entropy
    m = max(logits)
    ex = [math.exp(v - m) for v in logits]
    s = sum(ex)
    probs = [e / s for e in ex]
    loss = -math.log(max(probs[target], 1e-12))
    g = probs[:]
    g[target] -= 1.0
    return loss, g


def accuracy(logits, target, kind):
    if kind == "bce":
        return 1.0 if (sigmoid(logits[0]) >= 0.5) == (target >= 0.5) else 0.0
    return 1.0 if max(range(len(logits)), key=lambda i: logits[i]) == target \
        else 0.0


# ===========================================================================
# training
# ===========================================================================


def adam(model, data, epochs, lr, kind, log_every=0):
    ps = model.params()
    m = [[0.0] * p.n for p in ps]
    v = [[0.0] * p.n for p in ps]
    b1, b2, eps = 0.9, 0.999, 1e-8
    step = 0
    hist = []
    for ep in range(1, epochs + 1):
        random.shuffle(data)
        total = 0.0
        for xs, t in data:
            for p in ps:
                p.zero()
            logits = model.forward(xs)
            loss, g = loss_and_grad(logits, t, kind)
            total += loss
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
        hist.append(total / len(data))
        if log_every and ep % log_every == 0:
            print(f"      ep {ep:4d}  loss {hist[-1]:.4f}", flush=True)
    return hist


def make_data(task, lengths, n_per_len, rng):
    gen = TASKS[task]["gen"]
    out = []
    for L in lengths:
        for _ in range(n_per_len):
            out.append(gen(rng, L))
    return out


def evaluate(model, task, lengths, n_per_len, rng):
    gen = TASKS[task]["gen"]
    kind = TASKS[task]["loss"]
    accs = {}
    for L in lengths:
        correct = 0
        for _ in range(n_per_len):
            xs, t = gen(rng, L)
            logits = model.forward(xs)
            correct += accuracy(logits, t, kind)
        accs[L] = correct / n_per_len
    return accs


# ===========================================================================
# gradient check
# ===========================================================================


def gradcheck(task="parity", seed=0, eps=1e-5):
    rng = random.Random(seed)
    xs, t = TASKS[task]["gen"](rng, 4)
    kind = TASKS[task]["loss"]
    out_dim = TASKS[task]["out"]
    print(f"gradient check: task={task} seq_len=4 out_dim={out_dim}")
    all_ok = True
    for mname, cls in MECHANISMS.items():
        rng2 = random.Random(seed + 1)
        model = cls(1, 16, out_dim, rng2, hidden_dim=8)
        ps = model.params()
        for p in ps:
            p.zero()
        logits = model.forward(xs)
        loss0, g = loss_and_grad(logits, t, kind)
        model.backward(g)

        worst = 0.0
        nchecked = 0
        for pi, p in enumerate(ps):
            idxs = list(range(0, p.n, max(1, p.n // 5)))[:5]
            for j in idxs:
                orig = p.data[j]
                p.data[j] = orig + eps
                lp, _ = loss_and_grad(model.forward(xs), t, kind)
                p.data[j] = orig - eps
                lm, _ = loss_and_grad(model.forward(xs), t, kind)
                p.data[j] = orig
                num = (lp - lm) / (2 * eps)
                ana = p.grad[j]
                denom = max(1e-8, abs(num) + abs(ana))
                rel = abs(num - ana) / denom
                worst = max(worst, rel)
                nchecked += 1
        ok = worst < 1e-3
        all_ok &= ok
        print(f"  {mname:8s} params={sum(p.n for p in ps):5d} "
              f"checked={nchecked:3d}  worst_rel_err={worst:.3e}  "
              f"{'OK' if ok else 'FAIL'}")
    print("GRADCHECK:", "ALL OK" if all_ok else "FAILURES PRESENT")
    return all_ok


# ===========================================================================
# main experiment
# ===========================================================================


def run(task, mechanisms, train_lengths, test_lengths, n_train, n_test,
        epochs, lr, seeds, hidden_dim=16):
    kind = TASKS[task]["loss"]
    out_dim = TASKS[task]["out"]
    results = {}
    for mname in mechanisms:
        results[mname] = {}
        per_len = {L: [] for L in test_lengths}
        t0 = time.time()
        for s in range(seeds):
            rng = random.Random(1000 + s)
            model = MECHANISMS[mname](1, 16, out_dim, rng,
                                      hidden_dim=hidden_dim)
            data = make_data(task, train_lengths, n_train, rng)
            adam(model, data, epochs, lr, kind)
            ev = evaluate(model, task, test_lengths, n_test, rng)
            for L in test_lengths:
                per_len[L].append(ev[L])
        results[mname] = {
            "mean": {L: sum(v) / len(v) for L, v in per_len.items()},
            "per_seed": per_len,
            "secs": round(time.time() - t0, 1),
        }
    return results


def report(task, train_lengths, test_lengths, results):
    print()
    print("=" * 78)
    print(f"TASK: {task}   trained on lengths {min(train_lengths)}"
          f"-{max(train_lengths)}   '*' = length never seen in training")
    print("=" * 78)
    hdr = "  " + f"{'mechanism':<16s}"
    for L in test_lengths:
        star = "*" if L not in train_lengths else " "
        hdr += f"{str(L)+star:>8s}"
    hdr += f"{'secs':>9s}"
    print(hdr)
    print("  " + "-" * (len(hdr) - 2))
    for mname, r in results.items():
        row = "  " + f"{MECHANISMS[mname].name:<16s}"
        for L in test_lengths:
            v = r["mean"][L]
            row += f"{v:8.3f}"
        row += f"{r['secs']:9.1f}"
        print(row)
    print()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gradcheck", action="store_true")
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--seeds", type=int, default=2)
    ap.add_argument("--epochs", type=int, default=400)
    args = ap.parse_args()

    if args.gradcheck:
        ok = gradcheck()
        sys.exit(0 if ok else 1)

    seeds = 1 if args.quick else args.seeds
    epochs = 200 if args.quick else args.epochs

    summary = {}
    # --- parity: the canonical impossible-for-SSM state-tracking task ------
    train_l = list(range(1, 13))
    test_l = [8, 12, 24, 48]
    res = run("parity", ["window", "rnn", "lstm", "rotor"],
              train_l, test_l, n_train=32, n_test=64,
              epochs=epochs, lr=0.02, seeds=seeds)
    report("parity", train_l, test_l, res)
    summary["parity"] = res

    # --- flipflop: conditional state update -------------------------------
    res = run("flipflop", ["window", "rnn", "lstm", "rotor"],
              train_l, test_l, n_train=32, n_test=64,
              epochs=epochs, lr=0.02, seeds=seeds)
    report("flipflop", train_l, test_l, res)
    summary["flipflop"] = res

    # --- mod-7: cyclic group of order 7 -----------------------------------
    train_m = list(range(1, 9))
    test_m = [6, 8, 16, 32]
    res = run("mod7", ["window", "rnn", "lstm", "rotor"],
              train_m, test_m, n_train=32, n_test=64,
              epochs=epochs, lr=0.02, seeds=seeds)
    report("mod7", train_m, test_m, res)
    summary["mod7"] = res

    with open("reports/state_tracking_results.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print("wrote reports/state_tracking_results.json")


if __name__ == "__main__":
    main()
