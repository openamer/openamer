#!/usr/bin/env python3
"""The symmetric group S_5 as exact ground truth for non-abelian state tracking.

WHY A NON-ABELIAN GROUP
-----------------------
The previous result (RotorSnap, scripts/rotor_snap_lab.py) solves Z_K. But a
unit-modulus scalar MULTIPLIES COMMUTATIVELY:

    exp(i*a) * exp(i*b) == exp(i*b) * exp(i*a)

so no product of phases can ever encode ORDER of a non-commuting operation.
RotorSnap is structurally incapable of S_5 -- not a tuning issue.

Merrill et al. ("The Illusion of State in State-Space Models", and the
follow-up on CoT) show that transformers ALSO fail on non-solvable groups such
as S_5 and A_5, even with chain-of-thought. This module supplies the exact
ground truth so that claim can be tested locally rather than trusted.

WHAT IS HERE
------------
* all 120 elements of S_5 as plain tuples
* COMPOSITION: compose(a, b)(i) = a[b[i]]  -- chosen so that applying b first
  then a composes left-to-right; the operation is NON-COMMUTATIVE
* generators: the 4 adjacent transpositions, which generate all of S_5, plus
  the identity -> the per-token choice alphabet (5 symbols)
* matrix view (5x5 permutation matrix) for the continuous warm-up path
* an exhaustive self-test: closure, associativity, inverses, and the fact that
  the 5 generators really do reach all 120 elements (BFS)

Usage:
    python scripts/s5_group.py          # run the structural self-test
"""
import itertools
import sys
from collections import deque

N = 5


def _perms(n):
    return [tuple(p) for p in itertools.permutations(range(n))]


ELEMENTS = _perms(N)                      # 120 permutations
INDEX = {p: i for i, p in enumerate(ELEMENTS)}
IDENTITY = tuple(range(N))
ORDER = len(ELEMENTS)                     # 120


def compose(a, b):
    """Left-to-right composition: apply b, then a.  (a*b)(i) = a[b[i]]."""
    return tuple(a[b[i]] for i in range(N))


def inverse(a):
    inv = [0] * N
    for i, v in enumerate(a):
        inv[v] = i
    return tuple(inv)


def matrix(p):
    """5x5 permutation matrix as a flat row-major list."""
    m = [0.0] * (N * N)
    for i in range(N):
        m[i * N + p[i]] = 1.0
    return m


# --- generators: adjacent transpositions (0 1), (1 2), (2 3), (3 4), + id ---
def _swap(i, j):
    p = list(range(N))
    p[i], p[j] = p[j], p[i]
    return tuple(p)


GENERATORS = [_swap(0, 1), _swap(1, 2), _swap(2, 3), _swap(3, 4), IDENTITY]
GEN_MATRICES = [matrix(g) for g in GENERATORS]
NUM_GENS = len(GENERATORS)                # 5

# NOTE: the product task lives in scripts/perm_state_lab.py as `_task_gen`
# (it is imported from there by diagnose_s5.py and s5_anneal_lab.py) so the
# task is defined exactly once.


# ===========================================================================
# structural self-test -- no result is reported until this passes
# ===========================================================================


def self_test():
    print("=" * 72)
    print("S_5 structural self-test")
    print("=" * 72)
    ok = True

    # 1. order
    print(f"  |S_5| = {ORDER}  (expected 120)  "
          f"{'OK' if ORDER == 120 else 'FAIL'}")
    ok &= ORDER == 120

    # 2. closure + identity + inverses
    closed = ident_ok = inv_ok = True
    for a in ELEMENTS:
        if compose(a, IDENTITY) != a or compose(IDENTITY, a) != a:
            ident_ok = False
        if inverse(a) not in INDEX:
            inv_ok = False
        for b in ELEMENTS:
            if compose(a, b) not in INDEX:
                closed = False
    print(f"  closure            {'OK' if closed else 'FAIL'}")
    print(f"  identity law       {'OK' if ident_ok else 'FAIL'}")
    print(f"  inverses exist     {'OK' if inv_ok else 'FAIL'}")
    ok &= closed and ident_ok and inv_ok

    # 3. associativity on a sample (full is 120^3 = 1.7M, sample instead)
    assoc = True
    for a in ELEMENTS[:20]:
        for b in ELEMENTS[:20]:
            for c in ELEMENTS[:20]:
                if compose(compose(a, b), c) != compose(a, compose(b, c)):
                    assoc = False
    print(f"  associativity      {'OK' if assoc else 'FAIL'}"
          f"  (sampled 20^3 triples)")
    ok &= assoc

    # 4. NON-COMMUTATIVITY -- the whole point
    witness = None
    for a in ELEMENTS:
        for b in ELEMENTS:
            if compose(a, b) != compose(b, a):
                witness = (a, b)
                break
        if witness:
            break
    a, b = witness
    print(f"  NON-commutative    {'OK' if witness else 'FAIL'}")
    if witness:
        print(f"      a = {a}, b = {b}")
        print(f"      a*b = {compose(a,b)}   !=   b*a = {compose(b,a)}")
    ok &= bool(witness)

    # 5. do the 5 generators reach all 120 elements? (BFS)
    seen = {IDENTITY}
    q = deque([IDENTITY])
    while q:
        cur = q.popleft()
        for g in GENERATORS:
            nxt = compose(cur, g)
            if nxt not in seen:
                seen.add(nxt)
                q.append(nxt)
    reach = len(seen)
    print(f"  generators reach   {reach}/120  "
          f"{'OK' if reach == 120 else 'FAIL'}  (they generate all of S_5)")
    ok &= reach == 120

    # 6. sanity: a known composition, hand-checkable.
    #    compose(a,b) applies b FIRST, then a:  (a*b)(i) = a[b[i]]
    #    a = (01) = (1,0,2,3,4)     b = (12) = (0,2,1,3,4)
    #      i=0: b(0)=0 -> a(0)=1  => 1
    #      i=1: b(1)=2 -> a(2)=2  => 2
    #      i=2: b(2)=1 -> a(1)=0  => 0
    #      i=3: 3           i=4: 4
    got = compose(GENERATORS[0], GENERATORS[1])
    expected = (1, 2, 0, 3, 4)
    hand = got == expected
    print(f"  hand-checked case  {'OK' if hand else 'FAIL'}   "
          f"(01)*(12) = {got}  expected {expected}")
    ok &= hand

    print()
    print("SELF-TEST:", "ALL OK" if ok else "FAILURES PRESENT")
    return ok


if __name__ == "__main__":
    sys.exit(0 if self_test() else 1)
