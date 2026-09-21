#!/usr/bin/env python3
"""Correct separation of CONSTRUCTION from OPTIMISATION on S_5.

The first version of this diagnosis was itself wrong, and the error is
instructive. It set W = I (a perfect per-token generator choice) and measured
exact accuracy -- expecting 1.000 -- while leaving the READOUT HEAD at its
random initialisation. The head is what maps the state to one of 120 classes;
untrained, it cannot decode anything. So that test measured "perfect state +
blind decoder" and returned chance. It was a broken instrument, not a result.

THE CORRECT TEST
----------------
Freeze W = I so the per-token choice is provably perfect, then train ONLY the
readout head. If the task is reachable through this construction, this must
converge to 1.000, because the state path is already correct.

  * STEP 1: W frozen at I, head trained  -> tests the CONSTRUCTION
  * STEP 2: everything trained           -> tests OPTIMISATION
  * STEP 3: per-token choice accuracy    -> locates the bottleneck

Run:  python scripts/diagnose_s5.py
"""
import random
import sys
import time

sys.path.insert(0, "scripts")
from s5_group import NUM_GENS
from perm_state_lab import PermState, _task_gen, accuracy, train_phase

rng = random.Random(7)

# ---------------------------------------------------------------------------
print("=" * 78)
print("STEP 1 -- CONSTRUCTION: W frozen at I (choice provably perfect),")
print("          train the readout head only.")
print("=" * 78)

m = PermState(random.Random(1), tau=1.0)
m.eval_hard = True
m.W.data = [0.0] * (NUM_GENS * NUM_GENS)
for k in range(NUM_GENS):
    m.W.data[k * NUM_GENS + k] = 1.0
m.b.data = [0.0] * NUM_GENS

# Freeze W and b by handing train_phase only the head's parameters. The state
# path stays exactly correct (argmax(raw) == x for every token), so this
# isolates "can the readout decode a correct state?" from "can the model find
# correct choices?".
m.params = lambda: [m.head.W1, m.head.b1, m.head.W2, m.head.b2]

data = [_task_gen(rng, random.choice(range(1, 7))) for _ in range(192)]
t0 = time.time()
train_phase(m, data, 400, 0.05)
print(f"  (trained head only, {time.time()-t0:.0f}s)")
for L in (4, 6, 8, 12, 24, 48):
    h = 0
    for _ in range(120):
        xs, tg = _task_gen(rng, L)
        h += accuracy(m.forward(xs), tg)
    print(f"  L={L:3d}   EXACT accuracy, W=I frozen : {h/120:.3f}")

print()
print("  Near 1.000 here => the CONSTRUCTION is sound (correct state path).")
print("  Stays at chance => the state representation itself is at fault.")

# ---------------------------------------------------------------------------
print()
print("=" * 78)
print("STEP 2 -- OPTIMISATION: W and head trained together")
print("=" * 78)
for n_train, epochs in ((192, 200), (768, 300)):
    rng2 = random.Random(11)
    m2 = PermState(rng2, tau=1.0)
    m2.eval_hard = True
    d2 = [_task_gen(rng2, random.choice(range(1, 7))) for _ in range(n_train)]
    t0 = time.time()
    train_phase(m2, d2, epochs, 0.05)
    ev = {}
    for L in (6, 12, 24):
        h = 0
        for _ in range(120):
            xs, tg = _task_gen(rng2, L)
            h += accuracy(m2.forward(xs), tg)
        ev[L] = h / 120
    # per-token choice accuracy
    tot = good = 0
    for _ in range(200):
        xs, tg = _task_gen(rng2, 6)
        for x, (xv, raw) in zip(xs, m2._choices(xs)):
            tot += 1
            good += (max(range(NUM_GENS), key=lambda i: raw[i]) == x)
    print(f"  n_train={n_train:4d} ep={epochs:4d}  choice_acc={good/tot:.3f}  "
          f"EXACT L6={ev[6]:.3f} L12={ev[12]:.3f} L24={ev[24]:.3f}  "
          f"({time.time()-t0:.0f}s)")

print()
print("=" * 78)
print("WHERE THE DIFFICULTY IS")
print("=" * 78)
print("STEP 1 ~1.000 and STEP 2 low  => representation fine, CREDIT ASSIGNMENT")
print("   is the bottleneck: turning a 120-way grade into correct per-token")
print("   group choices across a long product.")
print("STEP 1 low                    => the construction itself is wrong.")
print(f"(chance: choice = 1/{NUM_GENS} = {1/NUM_GENS:.2f}, class = 1/120 = 0.008)")
