#!/usr/bin/env python3
"""Make weight init reproducibly seeded: every randn(...) call gets its rng.

BUG BEING FIXED (measured, not assumed)
---------------------------------------
`randn()` in state_tracking_lab.py fell back to the GLOBAL random module, so
two models built with the same seeded Generator got different weights:

    CyclicState(..., random.Random(1)) vs CyclicState(..., random.Random(1))
    -> weights DIFFER

Consequence: gradient checks were not reproducible, and `npm run test` flipped
between PASS and FAIL on identical code -- an unexplained flaky gate.

The fix threads each model's own `rng` through every `randn(...)` call. The
constructors already receive `rng`; it was simply never used.

Run:  python scripts/seed_init_fix.py --check     # verify determinism
      python scripts/seed_init_fix.py --apply     # rewrite the scripts
"""
import argparse
import random
import re
import sys

sys.path.insert(0, "scripts")
from cyclic_state_lab import CyclicState  # noqa: E402
from rotor_snap_lab import RotorSnap  # noqa: E402

# Each entry: (file, [(exact old text, new text), ...])
EDITS = {
    "state_tracking_lab.py": [
        # Readout
        ("self.W1 = P([randn(1.0 / math.sqrt(feat_dim))\n"
         "                     for _ in range(hidden * feat_dim)])",
         "self.W1 = P([randn(1.0 / math.sqrt(feat_dim), rng)\n"
         "                     for _ in range(hidden * feat_dim)])"),
        ("self.W2 = P([randn(1.0 / math.sqrt(hidden))\n"
         "                     for _ in range(out_dim * hidden)])",
         "self.W2 = P([randn(1.0 / math.sqrt(hidden), rng)\n"
         "                     for _ in range(out_dim * hidden)])"),
        # SimpleRNN
        ("self.Wx = P([randn(1.0 / math.sqrt(self.in_dim))\n"
         "                     for _ in range(self.h * self.in_dim)])",
         "self.Wx = P([randn(1.0 / math.sqrt(self.in_dim), rng)\n"
         "                     for _ in range(self.h * self.in_dim)])"),
        ("self.Wh = P([randn(1.0 / math.sqrt(self.h))\n"
         "                     for _ in range(self.h * self.h)])",
         "self.Wh = P([randn(1.0 / math.sqrt(self.h), rng)\n"
         "                     for _ in range(self.h * self.h)])"),
        # LSTM
        ("self.W = P([randn(1.0 / math.sqrt(self.in_dim))\n"
         "                    for _ in range(4 * H * self.in_dim)])",
         "self.W = P([randn(1.0 / math.sqrt(self.in_dim), rng)\n"
         "                    for _ in range(4 * H * self.in_dim)])"),
        ("self.U = P([randn(1.0 / math.sqrt(H)) for _ in range(4 * H * H)])",
         "self.U = P([randn(1.0 / math.sqrt(H), rng) for _ in range(4 * H * H)])"),
        # Rotor
        ("self.Wt = P([randn(scale) for _ in range(self.d * self.in_dim)])",
         "self.Wt = P([randn(scale, rng) for _ in range(self.d * self.in_dim)])"),
        ("self.bt = P([randn(0.5) for _ in range(self.d)])   # spread of offsets",
         "self.bt = P([randn(0.5, rng) for _ in range(self.d)])  # offset spread"),
    ],
    "cyclic_state_lab.py": [
        ("self.Wk = P([randn(1.0 / math.sqrt(xs_dim))\n"
         "                     for _ in range(K * xs_dim)])",
         "self.Wk = P([randn(1.0 / math.sqrt(xs_dim), rng)\n"
         "                     for _ in range(K * xs_dim)])"),
        ("self.Wo = P([randn(1.0 / math.sqrt(K))\n"
         "                         for _ in range(out_dim * K)])",
         "self.Wo = P([randn(1.0 / math.sqrt(K), rng)\n"
         "                         for _ in range(out_dim * K)])"),
    ],
    "rotor_snap_lab.py": [
        ("self.Wt = P([randn(1.0 / math.sqrt(xs_dim)) "
         "for _ in range(self.d * xs_dim)])",
         "self.Wt = P([randn(1.0 / math.sqrt(xs_dim), rng)\n"
         "                    for _ in range(self.d * xs_dim)])"),
        ("self.bt = P([randn(0.5) for _ in range(self.d)])",
         "self.bt = P([randn(0.5, rng) for _ in range(self.d)])"),
    ],
    "perm_state_lab.py": [
        ("self.W = P([randn(1.0 / math.sqrt(self.emb))\n"
         "                    for _ in range(NUM_GENS * self.emb)])",
         "self.W = P([randn(1.0 / math.sqrt(self.emb), rng)\n"
         "                    for _ in range(NUM_GENS * self.emb)])"),
        ("self.Wx = P([randn(1.0 / math.sqrt(self.emb))\n"
         "                     for _ in range(h * self.emb)])",
         "self.Wx = P([randn(1.0 / math.sqrt(self.emb), rng)\n"
         "                     for _ in range(h * self.emb)])"),
        ("self.Wh = P([randn(1.0 / math.sqrt(h)) for _ in range(h * h)])",
         "self.Wh = P([randn(1.0 / math.sqrt(h), rng) for _ in range(h * h)])"),
        ("self.W = P([randn(1.0 / math.sqrt(self.emb))\n"
         "                    for _ in range(4 * H * self.emb)])",
         "self.W = P([randn(1.0 / math.sqrt(self.emb), rng)\n"
         "                    for _ in range(4 * H * self.emb)])"),
        ("self.U = P([randn(1.0 / math.sqrt(H)) for _ in range(4 * H * H)])",
         "self.U = P([randn(1.0 / math.sqrt(H), rng) for _ in range(4 * H * H)])"),
    ],
}


def apply():
    for fname, edits in EDITS.items():
        path = "scripts/" + fname
        src = open(path, encoding="utf-8").read()
        n = 0
        for old, new in edits:
            if old in src:
                src = src.replace(old, new, 1)
                n += 1
            else:
                print(f"  !! NOT FOUND in {fname}: {old[:60]!r}")
        open(path, "w", encoding="utf-8", newline="").write(src)
        print(f"  {fname}: {n}/{len(edits)} edits applied")


def check():
    """Two models built from the same seed must have identical weights."""
    cases = [
        ("CyclicState K=2", lambda: CyclicState(1, 16, 1, random.Random(1), K=2)),
        ("CyclicState K=7", lambda: CyclicState(1, 16, 7, random.Random(4), K=7)),
        ("RotorSnap K=2", lambda: RotorSnap(1, 16, 1, random.Random(2), K=2)),
        ("RotorSnap K=7", lambda: RotorSnap(1, 16, 7, random.Random(9), K=7)),
    ]
    ok = True
    for name, make in cases:
        a, b = make(), make()
        same = all(pa.data == pb.data
                   for pa, pb in zip(a.params(), b.params()))
        ok &= same
        print(f"  {name:16s} same seed -> identical weights: "
              f"{'YES' if same else 'NO'}")
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    if args.apply:
        apply()
    if args.check or not args.apply:
        print("=" * 66)
        print("determinism check: same seed must give identical weights")
        print("=" * 66)
        ok = check()
        print()
        print("DETERMINISM:", "OK" if ok else "STILL NON-REPRODUCIBLE")
        sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
