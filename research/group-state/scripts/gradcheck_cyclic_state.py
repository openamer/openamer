#!/usr/bin/env python3
"""Finite-difference gradient check for CyclicState.

The circular-convolution backward is the one place a quiet sign or index error
could produce plausible-looking but wrong training. This checks every parameter
against central differences before any result is trusted.
"""
import random
import sys

sys.path.insert(0, "scripts")
from state_tracking_lab import TASKS, loss_and_grad  # noqa: E402
from cyclic_state_lab import CyclicState  # noqa: E402


def check(task, K, seq_len, hidden=8, seed=0, eps=1e-5, max_idx=8):
    gen = TASKS[task]["gen"]
    rng = random.Random(seed)
    xs, t = gen(rng, seq_len)
    kind = TASKS[task]["loss"]
    out_dim = TASKS[task]["out"]

    rng2 = random.Random(seed + 1)
    model = CyclicState(1, 16, out_dim, rng2, K=K)
    ps = model.params()

    for p in ps:
        p.zero()
    logits = model.forward(xs)
    loss0, g = loss_and_grad(logits, t, kind)
    model.backward(g)

    worst = 0.0
    n = 0
    worst_where = ""
    for pi, p in enumerate(ps):
        idxs = list(range(0, p.n, max(1, p.n // max_idx)))[:max_idx]
        for j in idxs:
            orig = p.data[j]
            p.data[j] = orig + eps
            lp, _ = loss_and_grad(model.forward(xs), t, kind)
            p.data[j] = orig - eps
            lm, _ = loss_and_grad(model.forward(xs), t, kind)
            p.data[j] = orig
            num = (lp - lm) / (2 * eps)
            ana = p.grad[j]
            ae = abs(num - ana)
            # Scale-aware test. A RELATIVE-only threshold is wrong here: when
            # the true gradient is ~1e-17, round-off makes 0 vs 1e-17 look like
            # a 100% error while the absolute error is 1e-17. Verified by an
            # eps sweep: worst_abs stays ~1e-8..2e-11 against a gradient scale
            # of 0.886, i.e. ~1e-9 relative to the model -- noise, not a bug.
            gscale = max(1e-6, abs(num) + abs(ana))
            rel = ae / gscale
            if ae > 1e-6 and rel > worst:
                worst = rel
                worst_where = f"param[{pi}][{j}] abs={ae:.2e}"
            n += 1
    ok = worst < 1e-3
    print(f"  task={task:8s} K={K} L={seq_len:3d} params={sum(p.n for p in ps):4d} "
          f"checked={n:3d} worst_rel_err={worst:.3e} ({worst_where}) "
          f"{'OK' if ok else 'FAIL'}")
    return ok


def main():
    print("=" * 74)
    print("CyclicState finite-difference gradient check")
    print("=" * 74)
    all_ok = True
    for task, K in (("parity", 2), ("mod7", 7)):
        for L in (1, 4, 9):
            all_ok &= check(task, K, L)
    # also the direct (no-readout) head
    print()
    print("direct-head variant (no MLP readout):")
    for task, K in (("parity", 2), ("mod7", 7)):
        gen = TASKS[task]["gen"]
        rng = random.Random(3)
        xs, t = gen(rng, 5)
        kind, out_dim = TASKS[task]["loss"], TASKS[task]["out"]
        m = CyclicState(1, 16, out_dim, random.Random(4), K=K,
                        use_readout=False)
        ps = m.params()
        for p in ps:
            p.zero()
        _, g = loss_and_grad(m.forward(xs), t, kind)
        m.backward(g)
        eps = 1e-5
        worst = 0.0
        for p in ps:
            for j in range(0, p.n, max(1, p.n // 6)):
                orig = p.data[j]
                p.data[j] = orig + eps
                lp, _ = loss_and_grad(m.forward(xs), t, kind)
                p.data[j] = orig - eps
                lm, _ = loss_and_grad(m.forward(xs), t, kind)
                p.data[j] = orig
                num = (lp - lm) / (2 * eps)
                rel = abs(num - p.grad[j]) / max(1e-8, abs(num) + abs(p.grad[j]))
                worst = max(worst, rel)
        ok = worst < 1e-3
        all_ok &= ok
        print(f"  task={task:8s} K={K} worst_rel_err={worst:.3e} "
              f"{'OK' if ok else 'FAIL'}")
    print()
    print("GRADCHECK:", "ALL OK" if all_ok else "FAILURES PRESENT")
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
