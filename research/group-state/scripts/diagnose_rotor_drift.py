#!/usr/bin/env python3
"""Diagnose: WHY does the phase rotor break on long sequences?

Observed: rotor solves parity/mod-k at the trained lengths but collapses at
2-4x the length (parity L=48 -> 0.016, mod7 L=32 -> 0.000), while LSTM stays
perfect on parity. Two competing explanations:

  H1 PHASE DRIFT  -- theta is a learned float, so it is never exactly pi.
                     After T steps the phase is T*(theta - pi), an error that
                     grows LINEARLY with length. Short lengths hide it.
  H2 READOUT LIMIT-- the readout sees Re/Im but cannot resolve the phase at
                     the precision long lengths need.

This script measures the learned angles directly and checks the drift law.
No guessing: if the phase error is proportional to T, it is H1.
"""
import math
import random
import sys

sys.path.insert(0, "scripts")
from state_tracking_lab import (  # noqa: E402
    Rotor, adam, make_data, mv, vec_add, TASKS, accuracy,
)


def train_rotor(task, lengths, epochs=400, lr=0.02, hidden_dim=2, seed=7,
                n_train=32):
    rng = random.Random(seed)
    out_dim = TASKS[task]["out"]
    kind = TASKS[task]["loss"]
    m = Rotor(1, 16, out_dim, rng, hidden_dim=hidden_dim)
    data = make_data(task, lengths, n_train, rng)
    adam(m, data, epochs, lr, kind)
    return m, kind, out_dim


def phase_trace(m, xs):
    """Return the per-step total phase and the final z."""
    d = m.d
    a, b = [1.0] * d, [0.0] * d
    phases = []
    for x in xs:
        xv = [x]
        th = vec_add(mv(m.Wt, xv, d, 1), m.bt.data)
        cs = [math.cos(v) for v in th]
        sn = [math.sin(v) for v in th]
        a = [a[k] * cs[k] - b[k] * sn[k] for k in range(d)]
        b = [a[k] * sn[k] + b[k] * cs[k] for k in range(d)]
        phases.append(list(th))
    return phases, a, b


def main():
    print("=" * 76)
    print("DIAGNOSIS: rotor phase behaviour")
    print("=" * 76)

    for task, k in (("parity", 2), ("mod7", 7)):
        print()
        print(f"--- task={task}  (group Z_{k}, target angle per 1 unit = "
              f"2*pi/{k} = {2*math.pi/k:.4f} rad) ---")
        m, kind, out_dim = train_rotor(task, list(range(1, 9)))
        print(f"  d={m.d}  learned rotation weights Wt = "
              f"{[round(v,4) for v in m.Wt.data]}")
        print(f"  learned offsets       bt = "
              f"{[round(v,4) for v in m.bt.data]}")

        per_unit = [m.Wt.data[i] for i in range(m.d)]
        target = 2 * math.pi / k
        print(f"  target per unit       = {target:.4f} rad")
        print(f"  mismatch (Wt-target)  = "
              f"{[round(per_unit[i]-target, 5) for i in range(m.d)]}")

        # --- drift law: does the phase error grow with T? -----------------
        print()
        print("  L   frac_correct   mean |phase err| (rad)   theory T*eps")
        for L in (8, 16, 32, 48, 64, 96):
            rng = random.Random(99)
            gen = TASKS[task]["gen"]
            correct = 0
            errs = []
            for _ in range(60):
                if task == "parity":
                    xs, t = gen(rng, L)
                else:
                    xs, t = gen(rng, L)
                logits = m.forward(xs)
                correct += accuracy(logits, t, kind)
                # analytic expected phase for this sequence
                exp_phase = target * sum(xs)
                ph, a, b = phase_trace(m, xs)
                got = math.atan2(b[0], a[0])
                # compare on the unit circle
                de = abs((got - exp_phase + math.pi) % (2 * math.pi)
                         - math.pi)
                errs.append(de)
            eps = abs(per_unit[0] - target)
            print(f"  {L:3d}   {correct/60:11.3f}   {sum(errs)/len(errs):18.4f}"
                  f"   {L*eps:11.4f}")

    print()
    print("=" * 76)
    print("INTERPRETATION")
    print("=" * 76)
    print("If 'mean |phase err|' tracks 'theory T*eps', the rotor's failure on")
    print("long sequences is PHASE DRIFT: a learned angle that is off by eps")
    print("accumulates T*eps of phase error, so the readout sees the wrong")
    print("group element. Short training lengths hide it.")
    print("Fix direction: keep the phase in the group (quantise the angle) so")
    print("no drift can accumulate.")


if __name__ == "__main__":
    main()
