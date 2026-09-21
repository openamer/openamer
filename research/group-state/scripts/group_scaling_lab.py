#!/usr/bin/env python3
"""SCALING AXIS A: does the group-state method scale with GROUP SIZE?

WHY THIS IS THE HONEST OPEN QUESTION
------------------------------------
Everything measured so far used Z_K (small, abelian) or S_5 (120 elements,
non-solvable). "It works" is only interesting if it survives larger and
structurally harder groups. Three concrete scaling threats:

  1. |G| grows, so the structural readout's catalogue grows. S_5 needs 120
     matrices of 25 floats; S_7 needs 5040 of 49. Is that a wall?
  2. the diameter of the Cayley graph grows, so the number of tokens needed to
     reach all elements grows -> the coverage problem returns at a larger scale.
  3. non-solvability is not the only hardness: A_5 is simple of order 60,
     D_n is solvable but non-abelian, S_n is non-solvable and grows fast.

WHAT IS MEASURED PER GROUP
--------------------------
  |G|                  order (how big the class set is)
  Cayley diameter      minimum max-word-length needed to reach every element
  coverage(L)          fraction of G reachable by words of length <= L
  accuracy             structural readout, trained on short words, tested on
                       lengths never seen -- and on lengths beyond the diameter

Every group's axioms AND its matrix convention are verified before use; a wrong
convention would silently invalidate every number.

Run:  python scripts/group_scaling_lab.py --selftest
      python scripts/group_scaling_lab.py --quick
      python scripts/group_scaling_lab.py --groups S5 S6 A5 D12 Z10
"""
import argparse
import itertools
import json
import math
import random
import sys
import time
from collections import deque

sys.path.insert(0, "scripts")
from state_tracking_lab import P, mv, mv_back, vec_add, add_into_bias


# ===========================================================================
# groups as permutation groups (one code path, one matrix convention)
# ===========================================================================
def sign(p):
    seen = [False] * len(p)
    s = 1
    for i in range(len(p)):
        if not seen[i]:
            j = i
            c = 0
            while not seen[j]:
                seen[j] = True
                j = p[j]
                c += 1
            if c % 2 == 0:
                s = -s
    return s


def compose(a, b):
    """Apply b first, then a:  (a*b)(i) = a[b[i]].   NON-COMMUTATIVE in general."""
    return tuple(a[b[i]] for i in range(len(a)))


def inverse(a):
    inv = [0] * len(a)
    for i, v in enumerate(a):
        inv[v] = i
    return tuple(inv)


def cyc(n, *idx):
    """Cycle notation -> permutation tuple (apply left to right as written)."""
    p = list(range(n))
    for k in range(len(idx) - 1):
        p[idx[k]] = idx[k + 1]
    p[idx[-1]] = idx[0]
    return tuple(p)


class Group:
    def __init__(self, name, elements, generators, n):
        self.name = name
        self.n = n
        self.elements = elements
        self.identity = tuple(range(n))
        self.index = {e: i for i, e in enumerate(elements)}
        self.order = len(elements)
        # reduce generators to the non-identity ones + keep identity available
        gens = [g for g in generators if g in self.index]
        self.generators = gens
        self.num_gens = len(gens)
        self.matrices = [self.matrix(e) for e in elements]
        self.dim = n * n
        self._diameter = None
        self._coverage = None

    def matrix(self, p):
        m = [0.0] * (self.n * self.n)
        for i in range(self.n):
            m[i * self.n + p[i]] = 1.0
        return m

    @property
    def diameter(self):
        """Cayley-graph diameter: max over elements of the shortest word length.

        This is the number that decides whether a curriculum can ever show the
        readout every element -- and it grows with the group.
        """
        if self._diameter is None:
            dist = {self.identity: 0}
            frontier = [self.identity]
            d = 0
            while frontier:
                nxt = []
                for cur in frontier:
                    for g in self.generators:
                        s = compose(cur, g)
                        if s not in dist:
                            dist[s] = d + 1
                            nxt.append(s)
                frontier = nxt
                d += 1
            self._diameter = max(dist.values())
            self._cov_by_len = {}
            for e, dl in dist.items():
                self._cov_by_len[dl] = self._cov_by_len.get(dl, 0) + 1
        return self._diameter

    def coverage(self, max_len):
        """Fraction of G reachable using words of length <= max_len (BFS)."""
        if self._coverage is None:
            self._coverage = {}
        if max_len in self._coverage:
            return self._coverage[max_len]
        dist = {self.identity: 0}
        frontier = [self.identity]
        d = 0
        while frontier and d < max_len:
            nxt = []
            for cur in frontier:
                for g in self.generators:
                    s = compose(cur, g)
                    if s not in dist:
                        dist[s] = d + 1
                        nxt.append(s)
            frontier = nxt
            d += 1
        frac = len(dist) / self.order
        self._coverage[max_len] = frac
        return frac


def build_group(name):
    if name == "S5":
        n = 5
        els = [tuple(p) for p in itertools.permutations(range(n))]
        gens = [cyc(n, i, i + 1) for i in range(n - 1)]
    elif name == "S6":
        n = 6
        els = [tuple(p) for p in itertools.permutations(range(n))]
        gens = [cyc(n, i, i + 1) for i in range(n - 1)]
    elif name == "S7":
        n = 7
        els = [tuple(p) for p in itertools.permutations(range(n))]
        gens = [cyc(n, i, i + 1) for i in range(n - 1)]
    elif name == "A5":
        n = 5
        els = [tuple(p) for p in itertools.permutations(range(n))
               if sign(p) == 1]
        # A 3-cycle plus a 5-cycle generate all of A5. NOTE: two 3-cycles do
        # NOT -- the selftest caught exactly that (gens_reach=False with
        # cyc(5,0,1,2) + cyc(5,0,1,3)), which is why the reach check exists.
        gens = [cyc(n, 0, 1, 2), cyc(n, 0, 1, 2, 3, 4)]
    elif name == "D12":
        # dihedral of order 12 acting on 6 points: rotation r, reflection s
        n = 6
        r = tuple((i + 1) % n for i in range(n))
        s = tuple(((-i) % n) for i in range(n))
        els = []
        cur = tuple(range(n))
        for _ in range(n):
            els.append(cur)
            els.append(compose(cur, s))
            cur = compose(cur, r)
        els = list(dict.fromkeys(els))
        gens = [r, s]
    elif name == "Z10":
        # cyclic of order 10 as a permutation group on 10 points
        n = 10
        g = tuple((i + 1) % n for i in range(n))
        els = []
        cur = tuple(range(n))
        for _ in range(n):
            els.append(cur)
            cur = compose(cur, g)
        els = list(dict.fromkeys(els))
        gens = [g]
    else:
        raise ValueError(f"unknown group {name}")
    return Group(name, els, gens, len(els[0]))


# ===========================================================================
# the architecture: group state + structural readout (no learned readout)
# ===========================================================================
class GroupState:
    def __init__(self, group, rng, tau=0.1, hidden_dim=None):
        self.G = group
        K = group.num_gens
        d = group.n
        self.tau = tau
        # W = I + noise: the measured-necessary init (see s5_init_lab.py)
        data = [0.0] * (K * K)
        for k in range(K):
            data[k * K + k] = 1.0
        for i in range(len(data)):
            data[i] += rng.gauss(0.0, 0.05)
        # one-hot of the GENERATOR INDEX -> K choice logits
        self.W = P(data)
        self.b = P([0.0] * K)

    def params(self):
        return [self.W, self.b]

    def _choices(self, xs):
        K = self.G.num_gens
        out = []
        for x in xs:
            xv = [1.0 if i == x else 0.0 for i in range(K)]
            out.append((xv, vec_add(mv(self.W, xv, K, K), self.b.data)))
        return out

    def forward(self, xs):
        G = self.G
        d = G.dim
        S = [0.0] * d
        for i in range(G.n):
            S[i * G.n + i] = 1.0
        cache = []
        for xv, raw in self._choices(xs):
            sc = [v / self.tau for v in raw]
            m = max(sc)
            ex = [math.exp(v - m) for v in sc]
            den = sum(ex)
            a = [e / den for e in ex]
            Gm = [0.0] * d
            for k in range(G.num_gens):
                ak = a[k]
                if ak == 0.0:
                    continue
                Mk = G.matrices_of_gen[k]
                for i in range(d):
                    Gm[i] += ak * Mk[i]
            S_prev = S
            S = [0.0] * d
            for i in range(G.n):
                for k in range(G.n):
                    g = Gm[i * G.n + k]
                    if g == 0.0:
                        continue
                    for j in range(G.n):
                        S[i * G.n + j] += g * S_prev[k * G.n + j]
            cache.append((S_prev, a, Gm, xv))
        self._S = S
        self._cache = cache
        # STRUCTURAL readout: logits_c = <S, M_c>, exact, no parameters
        return [sum(S[i] * M[i] for i in range(d)) for M in G.matrices]

    def backward_S(self, target):
        """dL/dS for CE over the structural logits."""
        G = self.G
        logits = [sum(self._S[i] * M[i] for i in range(G.dim))
                  for M in G.matrices]
        m = max(logits)
        ex = [math.exp(v - m) for v in logits]
        s = sum(ex)
        p = [e / s for e in ex]
        gS = [0.0] * G.dim
        for c in range(G.order):
            w = p[c] - (1.0 if c == target else 0.0)
            if w == 0.0:
                continue
            M = G.matrices[c]
            for i in range(G.dim):
                gS[i] += w * M[i]
        loss = -math.log(max(p[target], 1e-12))
        return loss, gS

    def backward(self, gS):
        G = self.G
        d = G.dim
        for t in range(len(self._cache) - 1, -1, -1):
            S_prev, a, Gm, xv = self._cache[t]
            gG = [0.0] * d
            for i in range(G.n):
                for k in range(G.n):
                    acc = 0.0
                    for j in range(G.n):
                        acc += gS[i * G.n + j] * S_prev[k * G.n + j]
                    gG[i * G.n + k] = acc
            gS_new = [0.0] * d
            for k in range(G.n):
                for j in range(G.n):
                    acc = 0.0
                    for i in range(G.n):
                        acc += gS[i * G.n + j] * Gm[i * G.n + k]
                    gS_new[k * G.n + j] = acc
            gA = [0.0] * G.num_gens
            for k in range(G.num_gens):
                Mk = G.matrices_of_gen[k]
                gA[k] = sum(gG[p] for p in range(d) if Mk[p] != 0.0)
            dot = sum(gA[k] * a[k] for k in range(G.num_gens))
            graw = [a[k] * (gA[k] - dot) / self.tau
                    for k in range(G.num_gens)]
            add_into_bias(self.b, graw)
            mv_back(self.W, xv, graw, G.num_gens, G.num_gens)
            gS = gS_new


# generators as matrices, attached per group (used by the state update)
def _attach(group):
    group.matrices_of_gen = [group.matrix(g) for g in group.generators]
    return group


# ===========================================================================
def task(group, rng, L):
    xs = [rng.randrange(group.num_gens) for _ in range(L)]
    st = group.identity
    for g in xs:
        st = compose(st, group.generators[g])
    return xs, group.index[st]


def train(m, data, epochs, lr):
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
            _, gS = m.backward_S(t)
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


def accuracy(m, group, L, n=200, seed=0):
    rng = random.Random(seed + L)
    hit = 0
    for _ in range(n):
        xs, t = task(group, rng, L)
        lo = m.forward(xs)
        hit += (max(range(len(lo)), key=lambda i: lo[i]) == t)
    return hit / n


def selftest():
    print("=" * 86)
    print("group axioms + matrix convention, per group")
    print("=" * 86)
    ok_all = True
    for name in ("S5", "S6", "S7", "A5", "D12", "Z10"):
        g = build_group(name)
        _attach(g)
        closed = all(compose(a, b) in g.index for a in g.elements[:25]
                     for b in g.elements[:25])
        ident = all(compose(a, g.identity) == a and
                    compose(g.identity, a) == a for a in g.elements[:25])
        invs = all(inverse(a) in g.index for a in g.elements[:25])
        # matrix convention: matrix(compose(a,b)) == M_b @ M_a
        conv = True
        for a in g.elements[:12]:
            for b in g.elements[:12]:
                lhs = g.matrix(compose(a, b))
                rhs = [0.0] * g.dim
                Mb, Ma = g.matrix(b), g.matrix(a)
                for i in range(g.n):
                    for k in range(g.n):
                        x = Mb[i * g.n + k]
                        if x == 0.0:
                            continue
                        for j in range(g.n):
                            rhs[i * g.n + j] += x * Ma[k * g.n + j]
                if max(abs(x - y) for x, y in zip(lhs, rhs)) > 1e-12:
                    conv = False
        # generators generate the whole group
        reach = {g.identity}
        dq = deque([g.identity])
        while dq:
            cur = dq.popleft()
            for gen in g.generators:
                s = compose(cur, gen)
                if s not in reach:
                    reach.add(s)
                    dq.append(s)
        gen_ok = len(reach) == g.order
        nonab = any(compose(a, b) != compose(b, a)
                    for a in g.elements[:40] for b in g.elements[:40])
        ok = closed and ident and invs and conv and gen_ok
        ok_all &= ok
        print(f"  {name:4s} |G|={g.order:5d} gens={g.num_gens:2d} "
              f"diam={g.diameter:3d}  closure={closed} ident={ident} "
              f"inv={invs} conv={conv} gens_reach={gen_ok} nonab={nonab}  "
              f"{'OK' if ok else 'FAIL'}")
    print()
    print("SELFTEST:", "ALL OK" if ok_all else "FAILURES PRESENT")
    return ok_all


def gradcheck():
    print()
    print("=" * 86)
    print("gradcheck: structural dL/dS per group (finite differences)")
    print("=" * 86)
    ok_all = True
    for name in ("S5", "A5", "D12", "Z10", "S6"):
        g = build_group(name)
        _attach(g)
        rng = random.Random(1)
        m = GroupState(g, rng, tau=0.1)
        xs, t = task(g, random.Random(2), 4)
        m.forward(xs)
        _, gS = m.backward_S(t)
        eps = 1e-7
        worst = 0.0
        for i in range(0, g.dim, max(1, g.dim // 12)):
            orig = m._S[i]
            m._S[i] = orig + eps
            lp = -math.log(max(
                math.exp(_logit(m, t)) /
                sum(math.exp(v) for v in _logits(m)), 1e-12))
            m._S[i] = orig - eps
            lm = -math.log(max(
                math.exp(_logit(m, t)) /
                sum(math.exp(v) for v in _logits(m)), 1e-12))
            m._S[i] = orig
            num = (lp - lm) / (2 * eps)
            ae = abs(num - gS[i])
            if ae > 1e-6:
                worst = max(worst, ae / max(1e-6, abs(num) + abs(gS[i])))
        ok = worst < 1e-3
        ok_all &= ok
        print(f"  {name:4s} |G|={g.order:5d}  worst_rel(dL/dS)={worst:.3e}  "
              f"{'OK' if ok else 'FAIL'}")
    print("GRADCHECK:", "ALL OK" if ok_all else "FAILURES PRESENT")
    return ok_all


def _logits(m):
    G = m.G
    return [sum(m._S[i] * M[i] for i in range(G.dim)) for M in G.matrices]


def _logit(m, t):
    return _logits(m)[t]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--groups", nargs="*", default=None)
    ap.add_argument("--epochs", type=int, default=250)
    ap.add_argument("--n-train", type=int, default=256)
    args = ap.parse_args()

    if args.selftest:
        sys.exit(0 if (selftest() and gradcheck()) else 1)

    names = args.groups or ["S5", "A5", "D12", "Z10", "S6"]
    print("=" * 86)
    print("SCALING AXIS A: group state + structural readout vs GROUP SIZE")
    print("=" * 86)

    results = {}
    for name in names:
        g = build_group(name)
        _attach(g)
        tr = range(1, 8)
        te = [4, 6, 12, 24, 48, 96]
        per = {L: [] for L in te}
        t0 = time.time()
        rng = random.Random(7000)
        m = GroupState(g, rng, tau=0.1)
        data = [task(g, rng, random.choice(tr)) for _ in range(args.n_train)]
        train(m, data, args.epochs, 0.05)
        for L in te:
            per[L] = accuracy(m, g, L, n=150, seed=11)
        cov12 = g.coverage(12)
        # The ONLY learned parameters are the per-token choice matrix W (K x K)
        # and its bias b (K). The structural readout is parameter-free. An
        # earlier version printed 2*num_gens, which was wrong: it counted one
        # scalar per generator instead of the full K x K matrix.
        n_params = g.num_gens * g.num_gens + g.num_gens
        results[name] = {"order": g.order, "diameter": g.diameter,
                         "coverage_12": cov12,
                         "num_generators": g.num_gens,
                         "params": n_params,
                         "acc": {str(L): per[L] for L in te},
                         "secs": round(time.time() - t0, 1)}
        print()
        print(f"  [{name}]  |G|={g.order}  Cayley diameter={g.diameter}  "
              f"coverage(L<=12)={cov12:.3f}  params=K^2+K={n_params}  "
              f"({results[name]['secs']}s)")
        print("    L    : " + "".join(f"{str(L)+('*' if L not in tr else ' '):>8s}"
                                      for L in te))
        print("    acc  : " + "".join(f"{per[L]:8.3f}" for L in te))

    print()
    print("=" * 86)
    print("SUMMARY: does accuracy scale with group size?")
    print("=" * 86)
    print(f"  {'group':6s}{'|G|':>7s}{'diam':>6s}{'cov@12':>9s}"
          f"{'acc L=4':>9s}{'acc L=48':>10s}{'acc L=96':>10s}")
    for name, r in results.items():
        print(f"  {name:6s}{r['order']:7d}{r['diameter']:6d}"
              f"{r['coverage_12']:9.3f}{r['acc']['4']:9.3f}"
              f"{r['acc']['48']:10.3f}{r['acc']['96']:10.3f}")

    with open("reports/group_scaling_results.json", "w") as f:
        json.dump(results, f, indent=2)
    print("\nwrote reports/group_scaling_results.json")


if __name__ == "__main__":
    main()
