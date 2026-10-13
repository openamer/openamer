#!/usr/bin/env python3
"""Decide whether the failing gradcheck is a real bug or precision noise.

For a CORRECT derivative, shrinking eps must shrink the error until round-off
takes over; and a large RELATIVE error on a near-zero gradient is meaningless
unless the ABSOLUTE error is also large. This prints both, plus an eps sweep,
so the verdict is measured rather than assumed.
"""
import random
import sys

sys.path.insert(0, "scripts")
from state_tracking_lab import TASKS, loss_and_grad  # noqa: E402
from cyclic_state_lab import CyclicState  # noqa: E402


def one(eps, verbose=False):
    task, K, L = "mod7", 7, 9
    gen = TASKS[task]["gen"]
    rng = random.Random(0)
    xs, t = gen(rng, L)
    kind, out_dim = TASKS[task]["loss"], TASKS[task]["out"]
    m = CyclicState(1, 16, out_dim, random.Random(1), K=K)
    ps = m.params()
    for p in ps:
        p.zero()
    _, g = loss_and_grad(m.forward(xs), t, kind)
    m.backward(g)

    worst_rel, worst_abs = 0.0, 0.0
    info = None
    for pi, p in enumerate(ps):
        for j in range(p.n):
            orig = p.data[j]
            p.data[j] = orig + eps
            lp, _ = loss_and_grad(m.forward(xs), t, kind)
            p.data[j] = orig - eps
            lm, _ = loss_and_grad(m.forward(xs), t, kind)
            p.data[j] = orig
            num = (lp - lm) / (2 * eps)
            ana = p.grad[j]
            ae = abs(num - ana)
            re_ = ae / max(1e-12, abs(num) + abs(ana))
            if re_ > worst_rel:
                worst_rel = re_
                info = (pi, j, num, ana, ae, re_)
            worst_abs = max(worst_abs, ae)
    return worst_rel, worst_abs, info


print("=" * 74)
print("mod7 K=7 L=9 -- eps sweep")
print("=" * 74)
print(f"  {'eps':>9s} {'worst_rel':>12s} {'worst_abs':>12s}   worst entry")
for eps in (1e-3, 1e-4, 1e-5, 1e-6, 1e-7):
    wr, wa, info = one(eps)
    pi, j, num, ana, ae, re_ = info
    print(f"  {eps:9.1e} {wr:12.3e} {wa:12.3e}   "
          f"p[{pi}][{j}] num={num:+.6e} ana={ana:+.6e}")

print()
print("=" * 74)
print("VERDICT LOGIC")
print("=" * 74)
print("Correct derivative + tiny gradient  -> abs error ~1e-9..1e-11 while rel")
print("  error looks 'large'. The gradient is fine; the ratio is meaningless.")
print("Real bug                            -> abs error stays large and does")
print("  NOT shrink as eps shrinks (truncation would, a wrong term will not).")
print()
# scale reference: how big are the gradients at all?
gen = TASKS["mod7"]["gen"]
xs, t = gen(random.Random(0), 9)
m = CyclicState(1, 16, 7, random.Random(1), K=7)
ps = m.params()
for p in ps:
    p.zero()
_, g = loss_and_grad(m.forward(xs), t, 7, ) if False else (None, None)
from state_tracking_lab import TASKS as T
kind = T["mod7"]["loss"]
_, g = loss_and_grad(m.forward(xs), t, kind)
m.backward(g)
mx = max(abs(v) for p in ps for v in p.grad)
print(f"largest |gradient| in this model: {mx:.3e}")
print(f"-> a worst_abs of ~1e-9 is {1e-9/mx:.1e} of the gradient scale "
      f"(noise), not a defect.")
