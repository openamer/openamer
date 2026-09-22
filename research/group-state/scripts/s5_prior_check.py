#!/usr/bin/env python3
"""Does the S_5 result reduce to exploiting the CLASS PRIOR?

WHY THIS CHECK MATTERS
----------------------
scripts/diagnose_s5.py (STEP 1) froze W = I so the per-token generator choice
is provably perfect, trained only the readout head, and reported exact accuracy
0.908 at L=4 falling to 0.342 at L=48. That decay is suspicious.

A head that truly DECODED the permutation state would be perfect at EVERY
length -- the state is already the right answer, so the readout is a bijection
over 120 classes and length is irrelevant to it. Decay therefore means the head
is not decoding; it is partly guessing.

And a guesser is rewarded by an imbalanced target distribution. A random word
over the generators is a random walk on S_5, and a random walk on a group
MIXES: at short lengths the product lands on some permutations far more often
than others (e.g. the identity and its neighbours are reachable in few ways),
while at long lengths the distribution approaches uniform. So a head that
predicts "the most likely permutation for this length" scores high at L=4 and
low at L=48 -- EXACTLY the observed shape.

If the head's accuracy merely tracks the majority-class rate, then 0.908 does
not demonstrate decoding. This script measures the majority-class baseline at
each length so the claim can be corrected rather than defended.

Run:  python scripts/s5_prior_check.py
"""
import math
import random
import sys
from collections import Counter

sys.path.insert(0, "scripts")
from perm_state_lab import PermState, _task_gen, accuracy, train_phase
from s5_group import NUM_GENS, ORDER


def class_stats(L, n=20000, seed=0):
    """(majority_share, n_classes_seen, normalised_entropy) for length L.

    normalised entropy: 1.0 == uniform over S_5. A random walk on a group
    MIXES, so a shorter product is more peaked -- which is exactly the shape a
    prior-exploiting predictor would ride.
    """
    rng = random.Random(seed)
    c = Counter(_task_gen(rng, L)[1] for _ in range(n))
    tot = sum(c.values())
    H = -sum((v / tot) * math.log(v / tot) for v in c.values())
    return max(c.values()) / tot, len(c), H / math.log(ORDER)


def main():
    if "--assert-prior" in sys.argv[1:]:
        # FAST gate (<2s): the task must not be solvable by predicting the most
        # likely permutation. If the prior were exploitable, every accuracy
        # claim in the S_5 paper could be prior-riding rather than decoding.
        for L, cap in ((4, 0.15), (48, 0.02)):
            maj, _, Hn = class_stats(L, n=4000)
            ok = maj <= cap
            print(f"  L={L:3d} majority={maj:.4f} (cap {cap}) "
                  f"entropy={Hn:.4f}  {'OK' if ok else 'FAIL'}")
            if not ok:
                print("  -> the class prior is exploitable; accuracy claims")
                print("     cannot be attributed to decoding.")
                sys.exit(1)
        print("PRIOR CHECK: the task has no trivially exploitable prior")
        sys.exit(0)

    print("=" * 80)
    print("Is 0.908 decoding, or class-prior exploitation?")
    print("=" * 80)

    lengths = [4, 6, 8, 12, 24, 48]

    # ---- 1. how peaked is the target distribution at each length? ---------
    print()
    print("1) class distribution over 120 permutations (20000 samples)")
    print(f"   {'L':>4s}{'majority share':>16s}{'#classes seen':>15s}"
          f"{'entropy/uniform':>18s}")
    print("   " + "-" * 53)
    maj = {}
    for L in lengths:
        m, seen, Hn = class_stats(L)
        maj[L] = m
        print(f"   {L:4d}{m:16.4f}{seen:15d}{Hn:18.4f}")

    print()
    print("   A random walk on a group mixes, so the majority share FALLS with")
    print("   length. That is exactly the shape of the measured accuracy.")

    # ---- 2. train the frozen-W model, compare against the prior ----------
    print()
    print("2) frozen W=I, head trained; accuracy vs majority-class baseline")
    m = PermState(random.Random(1), tau=1.0)
    m.eval_hard = True
    m.W.data = [0.0] * (NUM_GENS * NUM_GENS)
    for k in range(NUM_GENS):
        m.W.data[k * NUM_GENS + k] = 1.0
    m.b.data = [0.0] * NUM_GENS
    m.params = lambda: [m.head.W1, m.head.b1, m.head.W2, m.head.b2]

    rng = random.Random(7)
    data = [_task_gen(rng, random.choice(range(1, 7))) for _ in range(192)]
    train_phase(m, data, 400, 0.05)

    print()
    print(f"   {'L':>4s}{'model acc':>12s}{'majority base':>15s}"
          f"{'excess over prior':>19s}")
    print("   " + "-" * 50)
    for L in lengths:
        rng2 = random.Random(500)
        hit = 0
        for _ in range(2000):
            xs, tg = _task_gen(rng2, L)
            hit += accuracy(m.forward(xs), tg)
        acc = hit / 2000
        excess = acc - maj[L]
        print(f"   {L:4d}{acc:12.3f}{maj[L]:15.4f}{excess:19.4f}")

    print()
    print("=" * 80)
    print("READING IT")
    print("=" * 80)
    print("If 'model acc' tracks 'majority base', the head is mostly predicting")
    print("the length's most likely permutation -- the 0.908 is NOT evidence of")
    print("decoding, and the 'construction proven sound' claim must be weakened.")
    print("A large 'excess over prior' at long lengths IS evidence of decoding,")
    print("because there the prior is nearly uniform.")


if __name__ == "__main__":
    main()
