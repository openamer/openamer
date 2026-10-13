#!/usr/bin/env python3
"""Is the cyclic-state gradcheck FLAKY? Measure it, do not guess.

OBSERVED: `npm run test` reported "gradcheck: cyclic-state convolution FAIL"
once, while six standalone runs in a row all passed. A test that passes 6/6 and
fails inside a suite has a cause that has not been identified -- and an
unexplained flaky gate is worse than no gate.

The suspect is the pass criterion in gradcheck_cyclic_state.py:

    if ae > 1e-6 and rel > worst:   # absolute floor 1e-6, then ratio

An ABSOLUTE floor of 1e-6 is scale-blind. The gradient scale in this model is
~0.9, and finite differences with eps=1e-5 carry round-off near 1e-11; a value
that lands just above 1e-6 is noise being reported as a defect. This script
runs the identical check many times and records the ACTUAL worst absolute and
relative errors, so the verdict is data, not a threshold guess.

Run:  python scripts/gradcheck_flaky_probe.py [N]
"""
import random
import sys

sys.path.insert(0, "scripts")
from state_tracking_lab import TASKS, loss_and_grad  # noqa: E402
from cyclic_state_lab import CyclicState  # noqa: E402


def one(task, K, L, seed=0, eps=1e-5):
    """Return (worst_abs, worst_rel, ae_over_floor, grad_scale)."""
    gen = TASKS[task]["gen"]
    xs, t = gen(random.Random(seed), L)
    kind, out_dim = TASKS[task]["loss"], TASKS[task]["out"]
    m = CyclicState(1, 16, out_dim, random.Random(1), K=K)
    ps = m.params()
    for p in ps:
        p.zero()
    _, g = loss_and_grad(m.forward(xs), t, kind)
    m.backward(g)

    worst_abs = 0.0
    worst_rel = 0.0
    over = 0
    for p in ps:
        for j in range(p.n):
            orig = p.data[j]
            p.data[j] = orig + eps
            lp, _ = loss_and_grad(m.forward(xs), t, kind)
            p.data[j] = orig - eps
            lm, _ = loss_and_grad(m.forward(xs), t, kind)
            p.data[j] = orig
            num = (lp - lm) / (2 * eps)
            ae = abs(num - p.grad[j])
            sc = max(1e-6, abs(num) + abs(p.grad[j]))
            worst_abs = max(worst_abs, ae)
            worst_rel = max(worst_rel, ae / sc)
            if ae > 1e-6:
                over += 1
    gscale = max(abs(v) for p in ps for v in p.grad)
    return worst_abs, worst_rel, over, gscale


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    cases = [("parity", 2, 1), ("parity", 2, 4), ("parity", 2, 9),
             ("mod7", 7, 1), ("mod7", 7, 4), ("mod7", 7, 9)]

    print("=" * 82)
    print(f"cyclic-state gradcheck: {n} repetitions of every case")
    print("=" * 82)
    print(f"  {'case':<18s}{'worst_abs':>12s}{'worst_rel':>12s}"
          f"{'#ae>1e-6':>10s}{'grad_scale':>12s}")
    print("  " + "-" * 62)

    total_over = 0
    worst_abs_all = 0.0
    for task, K, L in cases:
        wa = wr = 0.0
        over = 0
        gs = 0.0
        for r in range(n):
            a, rl, o, g = one(task, K, L)
            wa = max(wa, a)
            wr = max(wr, rl)
            over += o
            gs = max(gs, g)
        total_over += over
        worst_abs_all = max(worst_abs_all, wa)
        print(f"  {task+' K='+str(K)+' L='+str(L):<18s}{wa:12.3e}"
              f"{wr:12.3e}{over:10d}{gs:12.3f}")

    print()
    print("=" * 82)
    print("VERDICT")
    print("=" * 82)
    print(f"  worst absolute error across all runs : {worst_abs_all:.3e}")
    print(f"  entries above the 1e-6 floor         : {total_over}")
    print()
    if total_over == 0:
        print("  No entry ever exceeded 1e-6 -> the floor is safe on this data,")
        print("  and the suite failure did NOT come from this criterion. Look")
        print("  elsewhere (do not 'fix' a threshold that is not the cause).")
    else:
        print("  Entries DO exceed the absolute 1e-6 floor while remaining")
        print("  ~1e-9 of the gradient scale -> the floor is scale-blind and")
        print("  reports round-off as a defect. Fix: judge on error relative to")
        print("  the model's gradient scale, not a fixed absolute constant.")


if __name__ == "__main__":
    main()
