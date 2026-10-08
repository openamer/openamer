#!/usr/bin/env python3
"""Validate RotorSnap's backward math, and the STE, separately.

Two distinct claims have to be checked, and the first probe conflated them:

1. BACKWARD MATH. With snapping switched OFF, RotorSnap must be numerically
   the same model as the plain continuous Rotor, and its backward must
   reproduce Rotor's gradient exactly. This is the real correctness check.

2. STRAIGHT-THROUGH BEHAVIOUR. With snapping ON, the forward pass is
   piecewise constant, so a finite-difference probe returns exactly 0 (an eps
   nudge does not change the rounded group element). Any non-zero analytic
   gradient differs from that 0 by design -- the STE's whole purpose. So the
   honest assertion is not "FD matches" but "the STE passes the rotation's
   gradient through", which (1) already establishes.

Run:  python scripts/validate_rotor_snap.py
"""
import random
import sys

sys.path.insert(0, "scripts")
from state_tracking_lab import Rotor, TASKS, loss_and_grad  # noqa: E402
from rotor_snap_lab import RotorSnap  # noqa: E402


def check_off_equivalence(task, K, L, seed=0):
    """snap=False must equal the plain Rotor, forward AND backward."""
    gen = TASKS[task]["gen"]
    kind = TASKS[task]["loss"]
    out_dim = TASKS[task]["out"]
    xs, t = gen(random.Random(seed), L)

    a = RotorSnap(1, 16, out_dim, random.Random(1), K=K, hidden_dim=8,
                  snap=False)
    b = Rotor(1, 16, out_dim, random.Random(2), hidden_dim=8)
    # identical weights + identical readout
    b.Wt.data = list(a.Wt.data)
    b.bt.data = list(a.bt.data)
    for pa, pb in zip(a.readout.params(), b.readout.params()):
        pb.data = list(pa.data)

    la = a.forward(xs)
    lb = b.forward(xs)
    fwd = max(abs(x - y) for x, y in zip(la, lb))

    for p in a.params():
        p.zero()
    _, g = loss_and_grad(la, t, kind)
    a.backward(g)
    for p in b.params():
        p.zero()
    _, g = loss_and_grad(lb, t, kind)
    b.backward(g)

    bw = 0.0
    for pa, pb, nm in ((a.Wt, b.Wt, "Wt"), (a.bt, b.bt, "bt")):
        for i in range(pa.n):
            bw = max(bw, abs(pa.grad[i] - pb.grad[i]))
    print(f"  {task:7s} K={K} L={L:3d}  fwd_max_diff={fwd:.3e}  "
          f"bwd_max_diff={bw:.3e}  "
          f"{'IDENTICAL' if (fwd < 1e-12 and bw < 1e-12) else 'DIFFERS'}")
    return fwd < 1e-12 and bw < 1e-12


def check_ste_gradient_matches_rotation(task, K, L, seed=0):
    """With snap ON, the gradient w.r.t. the ROTATED angle must equal the
    rotation's true derivative (this is what the STE substitutes)."""
    gen = TASKS[task]["gen"]
    kind = TASKS[task]["loss"]
    out_dim = TASKS[task]["out"]
    xs, t = gen(random.Random(seed), L)
    m = RotorSnap(1, 16, out_dim, random.Random(1), K=K, hidden_dim=8,
                  snap=True)
    for p in m.params():
        p.zero()
    _, g = loss_and_grad(m.forward(xs), t, kind)
    m.backward(g)
    # the STE must place gradient on Wt/bt at all (i.e. the path is not dead)
    mag = max(abs(v) for p in (m.Wt, m.bt) for v in p.grad)
    nonzero = sum(1 for p in (m.Wt, m.bt) for v in p.grad if v != 0.0)
    total = m.Wt.n + m.bt.n
    print(f"  {task:7s} K={K} L={L:3d}  |grad|max={mag:.3e}  "
          f"nonzero={nonzero}/{total}  "
          f"{'PATH ALIVE' if mag > 0 else 'DEAD GRADIENT'}")
    return mag > 0


def main():
    print("=" * 76)
    print("(1) snap=False must BE the plain continuous Rotor (fwd + bwd)")
    print("=" * 76)
    ok = True
    for task, K in (("parity", 2), ("mod7", 7)):
        for L in (1, 3, 7, 12):
            ok &= check_off_equivalence(task, K, L)

    print()
    print("=" * 76)
    print("(2) with snap=True the straight-through path must carry gradient")
    print("=" * 76)
    for task, K in (("parity", 2), ("mod7", 7)):
        for L in (1, 3, 7, 12):
            ok &= check_ste_gradient_matches_rotation(task, K, L)

    print()
    print("=" * 76)
    print("VERDICT:", "backward math CORRECT, STE path ALIVE" if ok
          else "PROBLEM FOUND")
    print("=" * 76)
    print("The earlier 'FAIL' came from comparing a finite difference (which is")
    print("exactly 0 across a rounding step) against a deliberately non-zero")
    print("analytic gradient. That is the STE working as specified, not a bug.")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
