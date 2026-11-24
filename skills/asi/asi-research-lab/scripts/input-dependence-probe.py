#!/usr/bin/env python3
"""Input-dependence probe -- the one measurement that caught a WRONG negative result.

WHY THIS EXISTS
---------------
A new architecture was reported as "does not work" (best 0.297 on S_5) when the
real cause was that its state was INPUT-INDEPENDENT at initialisation: the
readout saw a constant feature, so the input-side weights never learned. After
the fix the same mechanism scored 0.656 -- more than double.

Before concluding "my architecture cannot do this", run this probe. If the state
barely changes across DIFFERENT inputs, nothing about your architecture has been
tested yet.

THE MEASUREMENT
---------------
Build the model, then compute its internal state for many DIFFERENT random
inputs and report the mean pairwise L2 distance between those states.

    ~0        -> state is input-independent; the readout sees a constant and
                 the input-side weights cannot learn. THIS IS A BUG, not a
                 negative result.
    clearly >0-> the state carries input information; a negative result now
                 says something about the mechanism.

Typical measured values (S_5 permutation state):
    small random W  : 0.109   <- broken
    W = I + noise   : 0.183   <- works, per-token choice accuracy 1.000

USAGE
-----
Run against the OpenAmer research lab (default), or point --scripts at any dir
containing perm_state_lab.py:

    python input-dependence-probe.py
    python input-dependence-probe.py --floor 0.15
    python input-dependence-probe.py --scripts C:/path/to/scripts

Exit code 0 = state carries input information, 1 = likely-init bug.
"""
import argparse
import math
import os
import random
import sys

DEFAULT_SCRIPTS = os.path.expanduser(
    "~/AppData/Local/openamer-laptop/scripts")


def mean_pairwise_distance(vectors, stride=4):
    """Mean L2 distance between nearby pairs, sampled with `stride`.

    Sampling rather than all-pairs keeps it O(n*stride) so this stays a
    sub-second probe even for large states.
    """
    total, pairs = 0.0, 0
    for i in range(0, len(vectors), stride):
        for j in range(i + 1, min(i + stride, len(vectors))):
            total += math.sqrt(sum((a - b) ** 2
                                   for a, b in zip(vectors[i], vectors[j])))
            pairs += 1
    return total / max(1, pairs)


def probe_perm_state(scripts_dir, seed=11, n=64, length=6):
    """S_5 permutation state: measure input-dependence of the soft state."""
    sys.path.insert(0, scripts_dir)
    from perm_state_lab import PermState, _task_gen

    out = {}
    for label, init in (("random", "random"), ("identity", "identity")):
        try:
            m = PermState(random.Random(seed), tau=1.0, init=init)
        except TypeError:
            # older signature without an `init` kwarg -- only the random path
            if init != "random":
                continue
            m = PermState(random.Random(seed), tau=1.0)
        rng = random.Random(seed)
        states = []
        for _ in range(n):
            xs, _ = _task_gen(rng, length)
            S, _ = m._soft_state(m._choices(xs))
            states.append(S)
        out[label] = mean_pairwise_distance(states)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scripts", default=DEFAULT_SCRIPTS,
                    help="dir containing perm_state_lab.py")
    ap.add_argument("--floor", type=float, default=0.15,
                    help="minimum acceptable input-dependence")
    ap.add_argument("--length", type=int, default=6)
    ap.add_argument("--samples", type=int, default=64)
    args = ap.parse_args()

    if not os.path.isfile(os.path.join(args.scripts, "perm_state_lab.py")):
        print(f"perm_state_lab.py not found under {args.scripts}")
        print("pass --scripts <dir> pointing at the research lab scripts")
        return 2

    print("=" * 72)
    print("input-dependence probe: does the STATE depend on the INPUT?")
    print("=" * 72)
    res = probe_perm_state(args.scripts, n=args.samples, length=args.length)
    for label, val in res.items():
        print(f"  init={label:9s}  distance = {val:.4f}")
    print()

    # The DEFAULT init is what ships, so it is what the gate must judge.
    default = res.get("identity", res.get("random"))
    ok = default is not None and default > args.floor
    print(f"  default init must exceed {args.floor} -> "
          f"{'OK' if ok else 'FAIL'} ({default:.4f})")
    if not ok:
        print()
        print("  The state is near input-INDEPENDENT at initialisation. The")
        print("  readout sees a constant feature and the input-side weights")
        print("  cannot learn. This is a BUG, not a negative result about the")
        print("  architecture. Check the init of the choice/input matrix")
        print("  (e.g. W = I + small noise instead of small random W).")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
