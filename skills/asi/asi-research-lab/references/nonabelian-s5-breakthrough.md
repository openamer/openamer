# Non-abelian S_5 state tracking — the breakthrough, block by block

Session 2026-09-21, continuation of the Z_K work. Every number below was
measured in the session; reproduced from `reports/nonabelian_s5_paper.md` and
the `s5_*.py` / `perm_state_lab.py` scripts.

The wall: Merrill et al. ("The Illusion of State in State-Space Models") also
report that transformers fail on **non-solvable** groups (S_5, A_5) even with
chain-of-thought. S_5 is testable on a CPU, so it was attacked directly.

---

## 0. Why abelian machinery cannot even start

A unit-modulus scalar multiplies commutatively:

```
e^{i·a} · e^{i·b} == e^{i·b} · e^{i·a}
```

So no product of phases can encode the ORDER of non-commuting operations.
`RotorSnap` (which solves Z_K) is **structurally incapable** of S_5 — that is a
property of the representation, not a tuning problem. The state must be a
**matrix**, and the group must act by **matrix multiplication**.

## 1. Ground truth must be verified before use (`s5_group.py`)

| property | result |
|---|---|
| \|S_5\| | 120 |
| closure / identity / inverses | OK |
| associativity (20³ sampled triples) | OK |
| **non-commutative** | OK — witness a=(0,1,2,4,3), b=(0,1,3,2,4); a·b=(0,1,4,2,3) ≠ b·a=(0,1,3,4,2) |
| generators (01),(12),(23),(34),id reach | **120/120** via BFS |
| hand-checked composition | OK |

### Trap: the convention must be VERIFIED, not commented

`matrix(compose(a,b)) == M_b @ M_a` — verify it programmatically over the whole
group (`perm_state_lab.py --selftest`), or every number is meaningless.

### Trap: a hand-derived expectation is easy to get backwards

`compose(a,b)` applies **b first**: `(a*b)(i) = a[b[i]]`. Therefore

```
(01)·(12) = (1,2,0,3,4)     NOT (2,0,1,3,4)
```

Derive index by index; an "obvious" expectation written the other way produced
a red self-test that was my error, not the code's.

## 2. The construction (`perm_state_lab.py`)

```
state_0  = I                        (5×5 identity permutation matrix)
choice_t = softmax(W · onehot(x_t)) (over the 5 generators)
G_t      = Σ_k choice_t[k] · M_k    (differentiable mixture)
state_t  = G_t @ state_{t-1}
```

Generators = four adjacent transpositions + identity; they generate all of S_5.
The reachable state space is the full symmetric group, and order matters
because the matrix product does not commute.

## 3. First conclusion was WRONG — "the wall holds"

Initial (random init, 24 training sequences, 300 epochs), chance 0.008:

| mechanism | L=4 | L=6 | L=12* |
|---|---|---|---|
| bag of generator counts (order-blind) | 0.156 | 0.047 | 0.031 |
| tanh RNN | 0.016 | 0.016 | 0.000 |
| LSTM | 0.047 | 0.047 | 0.000 |
| PermState soft eval | 0.062 | 0.109 | 0.000 |
| PermState EXACT eval | 0.297 | 0.375 | 0.094 |

Written up as *"no mechanism solves S_5; the published wall holds."*
**That conclusion was later overturned** (see §5). Keep overturned results in
the artefact with a "superseded, kept for the record" label — deleting them is
how a project loses track of what it actually established.

## 4. Ruling out suspects by MEASUREMENT, cheapest first

### 4a. Suspect 1: vanishing gradient — **REFUTED**

`scripts/diagnose_gradient_flow.py` replicated the soft backward loop and
recorded ‖gS‖ per token position:

| L | first-token / last-token ratio | profile |
|---|---|---|
| 4 | 0.51 | — |
| 16 | 0.38 | flattens |
| 32 | **0.44** | 6.07e-01 → 2.65e-01, then flat |

Gradient reaches the **first token intact**. Credit assignment was not blocked
by a vanishing gradient. (Had this been "fixed" directly, the real bug would
have been hidden.)

### 4b. Suspect 2: the instrument is broken — **TRUE**

The first construction-vs-optimisation test froze `W = I` (per-token choice
provably perfect) and expected exact accuracy 1.000 — while leaving the
**readout head at random init**. The head maps state → 120 classes; untrained
it decodes nothing. That test measured "perfect state + blind decoder" and
returned chance. **The error was in the test, not the construction.**

Correct version: freeze `W = I`, train **only the readout head** → 0.908 at
L=4 (113× chance). The construction is sound.

### 4c. Suspect 3: class-prior exploitation — **REFUTED (measured)**

The head could have been riding the majority-class rate. Tested
(`s5_prior_check.py`): majority share 0.0927 @ L=4 → 0.0103 @ L=48, with
normalised entropy 0.999 at L=48 (a random walk on a group mixes). A
prior-exploiter is capped at 0.010 at L=48; the model reached 0.353. **The head
decodes.** Excess over prior: +0.836 (L=4) → +0.343 (L=48).

But the excess ITSELF falls — so "0.908 at L=4, construction proven" was
**softened** in the paper: the correct wording is "sound, but the readout does
not fully learn the group from short-sequence training alone".

This became a permanent gate: `s5_prior_check.py --assert-prior` (<2 s).

## 5. THE REAL CAUSE: initialisation (`s5_init_lab.py`)

With `W ~ N(0, 1/√5)` the softmax over generators is near-**UNIFORM** at every
token, so every per-token mixture is the same near-average doubly-stochastic
matrix and the product carries almost no information about the input. Measured
as mean pairwise L2 distance between the soft states of *different* random
sequences at init:

| init | input-dependence |
|---|---|
| random `W ~ N(0,1/√5)` | **0.109** |
| `W = I` | **0.183** |

The head saw a constant feature and the 25-parameter choice matrix never
learned. Same **diffusion** as the abelian convolution case.

Fix — initialise `W = I` (+0.05 noise); it is NOT a frozen cheat, `W` keeps
training:

| config | choice acc (chance 0.20) | L=4 | L=6 | L=12* | L=24* |
|---|---|---|---|---|---|
| random init | 0.197 (seeds [0.203, 0.192]) | 0.463 | 0.396 | 0.179 | 0.046 |
| **`W = I`, trained** | **1.000** (seeds [1.000, 1.000]) | **0.917** | **0.833** | **0.592** | **0.383** |
| `W = I` frozen (upper bound) | 1.000 | 0.921 | 0.821 | 0.646 | 0.417 |

**Doubled the headline result** (0.297 → 0.656 at L=4 in the main runner).

Gate: `s5_init_lab.py --assert-init` asserts input-dependence > 0.15
(0.1826 OK / 0.1087 FAIL on random init). Negative-tested.

## 6. The learned readout is a LOOKUP TABLE (`s5_curriculum_lab.py`)

Sharpest possible test — accuracy split by whether the target permutation was
**reachable in training**:

| training lengths | states reachable | acc(seen) | **acc(UNSEEN)** |
|---|---|---|---|
| 1–6 | 37/120 | **1.000** | **0.000** |
| 1–12 | 58/120 | 0.031 | 0.000 |

Perfect on what it saw, **zero** on what it did not.

Class coverage by maximum training length (BFS over generators):

| max len | reachable |
|---|---|
| 4 | 49/120 |
| 6 | 91/120 |
| 8 | 115/120 |
| 12 | **120/120** |

A length curriculum (grow max length 1 → 12 over training) lifts the headline —
L=48: 0.317 → **0.446**, L=4: 0.904 → **0.950** — but cannot fix a head that
must memorise 120 classes.

## 7. The fix: a STRUCTURAL readout

The state **IS** the answer: a permutation matrix satisfies `M[i][p(i)] = 1`, so
the group element is read off by an inner product against the 120 permutation
matrices:

```
logits_c = <S, M_c> = Σ_ij S_ij · M_c_ij
dL/dS    = Σ_c (p_c − 1[c == target]) · M_c
```

No parameters — the "weights" are the fixed matrix catalogue — so
**memorisation is impossible** and coverage is always 120/120. Gradient verified
against central differences at `worst_rel = 0.000e+00`.

### It failed at first (0.095 at L=4) — and that was diagnosed, not worked around

`<S, M_c>` is exact only if `S` really is a permutation matrix. At tau=1 the
choices are diffuse, the product of mixtures diffuses toward uniform, and the
state is not a group element at all.

## 8. THE DECISIVE HYPER-PARAMETER: tau (`s5_tau_sweep.py`)

Perfect choice weights (`W = I`), **no training**, distance from the final state
to the nearest permutation matrix:

| tau | dist-to-perm | L=4 | L=12* | L=48* | **L=200*** |
|---|---|---|---|---|---|
| 1.000 | 1.694e+00 | 0.095 | 0.050 | 0.005 | 0.000 |
| 0.300 | 9.128e-01 | 1.000 | 1.000 | 0.675 | 0.010 |
| **0.100** | **1.750e-03** | **1.000** | **1.000** | **1.000** | **1.000** |
| 0.030 | 1.286e-13 | 1.000 | 1.000 | 1.000 | 1.000 |
| ≤0.010 | ~0 | 1.000 | 1.000 | 1.000 | 1.000 |

At tau ≤ 0.1 the state is an exact group element and accuracy is **1.000 at
every length**, including L=200 — **33× beyond anything trained on**. The whole
pipeline then contains **25 learned parameters** (the per-token choice), a fixed
catalogue of group matrices, and an exact inner product.

## 9. The unifying law

**DIFFUSION is the failure mode.** A soft mixture of group elements drifts
toward uniform. Observed independently three times in this research line:

1. abelian convolution state (`cyclic_state_lab.py`) — convolving distributions
   is a random walk; accuracy decays to chance
2. S_5 initialisation (`s5_init_lab.py`) — random small W makes the state
   input-independent (0.109)
3. S_5 structural readout at tau=1 (`s5_tau_sweep.py`) — dist-to-perm 1.7

Every fix was the same in kind: **force the state back onto the group.**
Snap the angle (Z_K) · initialise with correct choices (S_5) · sharpen tau (S_5).

**Operational rule: if a group-state model underperforms, measure how far the
state is from the group BEFORE changing anything else.**

## 10. Gradient-flow instrumentation recipe

To measure per-token gradient flow in a product recurrence, replicate the
backward loop explicitly (it is short) and record norms per position:

- `‖gS‖` — state-gradient norm entering each backward step
- `‖graw‖` — generator-choice gradient produced at that step

Walk backwards; index 0 is the LAST token. Healthy models show roughly constant
values; vanishing shows first entries ≫ last. For S_5 at L=32 the profile was
6.07e-01 → 2.65e-01 then flat — i.e. healthy.

## 11. SCALING — does it survive larger and harder groups?

Everything above used Z_K or S_5. "It works" only matters if it survives larger
and structurally different groups. `scripts/group_scaling_lab.py` builds six
permutation groups, verifies each one's **axioms, matrix convention, generator
span and per-group gradient** before measuring anything, then trains on short
words only (lengths 1–7).

| group | type | \|G\| | Cayley diam | cov@12 | params | L=4 | L=48* | **L=96*** |
|---|---|---|---|---|---|---|---|---|
| D12 | dihedral, non-abelian, solvable | 12 | 4 | 1.000 | 4 | 1.000 | 1.000 | **1.000** |
| Z10 | cyclic, abelian | 10 | 9 | 1.000 | 2 | 1.000 | 1.000 | **1.000** |
| A5 | **simple, non-solvable** | 60 | 8 | 1.000 | 4 | 1.000 | 1.000 | **1.000** |
| S5 | non-solvable | 120 | 10 | 1.000 | 8 | 1.000 | 1.000 | **1.000** |
| S6 | non-solvable | **720** | 15 | 0.972 | 10 | 1.000 | 1.000 | **1.000** |

**Parameters track the number of GENERATORS, not the group order.** S6 has
**6×** the elements of S5 and needs only 10 params instead of 8 (+25%). The
structural readout's catalogue grows with |G| (S7 would need 5040 matrices of
49 floats) but that is a **memory/compute** cost, not a **learning** cost —
nothing is trained there.

**The structural readout does not need full coverage.** S6 reaches only
**97.2 %** of its elements within the training budget, yet scores 1.000 —
because it COMPUTES rather than memorises. Contrast the learned MLP head (§6):
1.000 on seen states, **0.000** on unseen ones with the same kind of gap. This
is the cleanest demonstration of *why* the structural readout was necessary.

### Trap: verify the GENERATORS, not just the group

Two 3-cycles do **NOT** generate A5. The BFS reach check returned
`gens_reach=False` **before any accuracy number was produced**; the fix was a
3-cycle plus a 5-cycle. A wrong generator set silently shrinks the reachable
state space and every downstream number becomes meaningless.

The per-group check that catches it, in order, before reading any measurement:

```
closure          compose(a,b) in G for all pairs
identity         compose(a,e) == a == compose(e,a)
inverses         inverse(a) in G
convention       matrix(compose(a,b)) == M_b @ M_a
generator span   BFS from e over the generators reaches ALL of G   <-- caught A5
non-commutativity  exists a,b with a·b != b·a
gradient         per-group finite-difference check on dL/dS (0.000e+00 for all)
```

`python scripts/group_scaling_lab.py --selftest` runs all of the above and exits
non-zero on any failure — it is wired into the suite as a gate.

**Honest boundary that remains:** this is a **component**, measured on synthetic
group tasks. It is **not integrated** into any language model and has **never
been trained on real data**. Scaling *within the group family* is established;
scaling *to language* is untested.

## 12. Scripts and artefacts

| script | purpose |
|---|---|
| `s5_group.py` | S_5 ground truth + axioms/generator self-test |
| `perm_state_lab.py` | non-abelian matrix state + gradcheck + structural readout |
| `diagnose_gradient_flow.py` | rules out (or confirms) vanishing gradient |
| `diagnose_s5.py` | construction-vs-optimisation separation |
| `s5_init_lab.py` | the init fix + `--assert-init` gate |
| `s5_prior_check.py` | class-prior control + `--assert-prior` gate |
| `s5_curriculum_lab.py` | coverage + seen-vs-unseen test |
| `s5_structural_readout.py` | structural readout + `--gradcheck` |
| `s5_tau_sweep.py` | the decisive tau sweep |
| `s5_anneal_lab.py` | tau annealing (helped: 0.207 → 0.308; not sufficient alone) |
| `group_scaling_lab.py` | 6-group scaling + `--selftest` (axioms/convention/generators/grads) |
| `reports/nonabelian_s5_paper.md` | the write-up |
