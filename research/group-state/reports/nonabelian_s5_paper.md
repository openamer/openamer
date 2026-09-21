# Non-Abelian State Tracking: the wall that stops everyone

**Author:** OpenAmer (CPU-only research lab)
**Date:** 2026-09-21
**Status:** experimental. Part of a series; the abelian case is in
`reports/exact_group_state_paper.md`. All numbers below are produced by scripts
in this directory and are reproducible on CPU. Negative results are reported as
findings, not hidden.

---

## 1. Why a commutative state is not enough

The companion work builds `RotorSnap`: a unit-modulus **phase** state that
solves Z_K (modular counting) to 1.000 where an LSTM sits at chance, with
length generalisation to 32–170× the training length.

A phase, however, multiplies **commutatively**:

```
exp(i*a) * exp(i*b) == exp(i*b) * exp(i*a)
```

So no product of phases can encode the **order** of two operations that do not
commute. RotorSnap is *structurally* incapable of S_5 — this is a property of
the representation, not a matter of tuning.

Merrill et al. ("The Illusion of State in State-Space Models") and the
follow-up work on chain-of-thought report that transformers also fail on
**non-solvable** groups such as S_5 and A_5, *even with CoT*. S_5 is therefore
the sharpest available frontier, and it is testable on a CPU.

## 2. Ground truth, verified before use

`scripts/s5_group.py` builds S_5 and self-tests it — closure, identity,
inverses, associativity, a hand-derived composition, and a BFS over the
generators. All pass:

| property | result |
|---|---|
| \|S_5\| | 120 (expected 120) |
| closure / identity / inverses | OK |
| associativity (20³ sampled triples) | OK |
| **non-commutative** | OK — witness a=(0,1,2,4,3), b=(0,1,3,2,4); a·b=(0,1,4,2,3) ≠ b·a=(0,1,3,4,2) |
| generators (01),(12),(23),(34),id reach | **120/120** (they generate all of S_5) |
| hand-checked composition (01)·(12) | OK = (1,2,0,3,4) |

One trap worth recording: the **convention** must be pinned down or every
result is meaningless. This work verifies `matrix(compose(a,b)) == M_b @ M_a`
programmatically over the whole group rather than trusting a comment.

## 3. The construction

Replace the commutative scalar by a matrix, and let the group act by **matrix
multiplication**, which does not commute:

```
state_0  = I                        (5x5 identity permutation matrix)
choice_t = softmax(W · onehot(x_t)) (over the 5 generators)
G_t      = Σ_k choice_t[k] · M_k    (differentiable mixture)
state_t  = G_t @ state_{t-1}
```

Two evaluation modes share one trained model, so exactly one question is
isolated — *does an exactly group-valued state beat a relaxed one?*

- **soft**: the doubly-stochastic product matrix
- **exact**: recomposed from the argmax generators — the state is then a
  genuine element of S_5, with no representation error to accumulate

This mirrors the abelian finding that a *soft relaxation of a group tends to
diffuse* (`scripts/cyclic_state_lab.py`: convolving distributions is a random
walk).

## 4. Results

Trained on sequences of length 1–6. Chance = 1/120 = **0.008**.
2 seeds, 300 epochs, 24 training sequences.

| mechanism | L=4 | L=6 | L=12* | L=24* | L=48* |
|---|---|---|---|---|---|
| bag of generator counts (order-blind) | 0.156 | 0.047 | 0.031 | 0.000 | 0.016 |
| tanh RNN | 0.016 | 0.016 | 0.000 | 0.000 | 0.016 |
| LSTM | 0.047 | 0.047 | 0.000 | 0.016 | 0.016 |
| PermState, soft eval | 0.062 | 0.109 | 0.000 | 0.000 | 0.016 |
| **PermState, EXACT eval** | **0.297** | **0.375** | 0.094 | 0.031 | 0.016 |

`*` = length never seen in training.

**Result 1 (superseded, kept for the record).** In the FIRST configuration
(random init, 24 training sequences) no mechanism solved S_5 — best was the
exact group state at 0.297 / 0.375 at L=4/6. That was written up as "the wall
holds". **Result 6 shows that conclusion was an artefact of the choice-matrix
initialisation, not of the group representation.** The numbers are kept here
because deleting an overturned result is how a project loses track of what it
actually established.

**Correction on the quoted S_5 accuracy figures.** The table above, and an
earlier claim of **0.656 / 0.422 / 0.281** at L=4/6/12, were measured with the
MLP readout at tau=1.0 **before the determinism fix** — weight initialisation
then drew from the global `random` module, so those runs were not reproducible.
Re-measured over **6 seeds** with the current code (`perm_hard` = trained with
the soft path, evaluated exactly; tau=1.0, default identity init):

| L | mean | min | max |
|---|---|---|---|
| 4 | **0.510** | 0.234 | 0.766 |
| 6 | 0.414 | 0.203 | 0.609 |
| 12 | 0.245 | 0.078 | 0.422 |

So the MLP-readout configuration is **~64× chance on average but strongly
seed-dependent**, and 0.656 was the favourable end of that spread rather than a
typical result. **Treat any single-seed figure from this route as a sample, not
an estimate.** The route was superseded rather than tuned: the structural
readout (Results 9–10) removes the variance question by removing the learned
head altogether.

**Result 2.** Even in that first configuration, the exact group state was the
**only** mechanism above chance at short lengths (0.375 vs 0.016–0.047 for the
RNN and LSTM). The non-abelian representation carried real signal where
saturating recurrences carried none.

**Result 3.** Length generalisation failed at first: everything decayed toward
chance by L=12–24. Result 7 revises this too — with a correct initialisation
the mechanism holds to 0.433 at L=24 against 0.008 chance.

## 5. Separating CONSTRUCTION from OPTIMISATION — and a broken instrument

A result like this has two very different explanations, and conflating them is
how a project lies to itself:

- **H1 — construction.** The state/update is wrong, so 1.000 is unreachable.
- **H2 — optimisation.** The construction is right but under-trained.

`scripts/diagnose_s5.py` had to be **rewritten** to answer this, because the
first version was a broken instrument: it set `W = I` (a provably perfect
per-token choice) and expected exact accuracy 1.000, while leaving the
**readout head at its random initialisation**. The head is what maps the state
onto 120 classes; untrained, it decodes nothing. That test measured "perfect
state + blind decoder" and returned chance. The error was in the *test*, not
the construction.

### Result 4 — the construction is sound, with a measured qualification

Freeze `W = I` so the per-token generator choice is exactly right, then train
**only the readout head**:

| L | 4 | 6 | 8 | 12 | 24 | 48 |
|---|---|---|---|---|---|---|
| exact accuracy, W=I frozen | **0.928** | 0.840 | 0.765 | 0.653 | 0.440 | 0.353 |
| majority-class baseline (prior) | 0.0927 | 0.0595 | 0.0425 | 0.0273 | 0.0147 | 0.0103 |
| **excess over prior** | **+0.836** | +0.780 | +0.723 | +0.626 | +0.425 | **+0.343** |

Three readings of this table matter, and one of them is a correction to an
earlier claim:

1. **The head is decoding, not exploiting a class prior.** Accuracy tracks far
   above the majority-class rate at *every* length. This is decisive at L=48,
   where a random walk on S_5 has nearly mixed (normalised entropy **0.999**)
   so a prior-exploiting predictor is capped at 0.010 — the model reaches
   **0.353**. `scripts/s5_prior_check.py`.
2. **The decay is real and was not explained by the prior.** The excess itself
   falls (0.836 → 0.343), so a head that truly inverts the state should be at
   1.000 for every length (the state *is* the answer). It is not.
3. **Why the decay — measured, not guessed.** Training used lengths 1–6, and
   those reach only **49–91 of the 120** permutations. The head generalises
   imperfectly to states it rarely saw. The state path is correct; the readout
   has not learned the full group.

So the honest wording is: **the construction is sound — the correct state is
present and decodable far above chance at every length — but the readout does
not fully learn the group from short-sequence training alone.** An earlier
version of this document said "0.908 at L=4, ~113× chance, the task is
reachable", which implied length-independence that the data does not support.

### Result 5 — the bottleneck looked like credit assignment

Training everything together does **not** recover it. Per-token choice accuracy
sits at chance (0.198–0.214 against 0.20), with one unstable run briefly
reaching 0.610. So:

> **representation: works. credit assignment: appeared to fail.**

Turning a 120-way classification grade into correct per-token group choices
across a long **non-commutative** product is the apparent open problem — not the
state representation. **This diagnosis was then tested and corrected in
Result 6: the real cause was the initialisation.**

### Result 6 — the bottleneck was INITIALISATION, and fixing it breaks the wall

A gradient-flow measurement came first, and it **refuted the obvious
explanation**: the gradient does not vanish. First-token/last-token
state-gradient ratio is 0.51 at L=4 and **0.44 at L=32**, and the per-position
profile *flattens* with length (`scripts/diagnose_gradient_flow.py`).

The real cause was the initialisation of the soft state. With
`W ~ N(0, 1/sqrt(5))` the softmax over generators is near-UNIFORM at every
token, so every per-token mixture is the same near-average doubly-stochastic
matrix and the product carries almost no information about the input. Measured
directly as the mean pairwise distance between the soft states of *different*
random sequences at initialisation:

| init | input-dependence of the state |
|---|---|
| random `W ~ N(0,1/√5)` | **0.109** |
| `W = I` | **0.183** |

The state was effectively input-independent, the head saw a constant feature,
and the 25-parameter choice matrix never learned. This is the same **diffusion**
already measured for the abelian convolution case — a soft mixture of group
elements drifts toward uniform.

Initialising `W = I` (so `argmax` is correct from the first step) fixes it, and
the fix is *not* a frozen cheat — `W` keeps training:

| config | choice acc (chance 0.20) | L=4 | L=6 | L=12* | L=24* |
|---|---|---|---|---|---|
| random init | 0.395 (unstable, seeds [0.203, 0.587]) | 0.508 | 0.404 | 0.229 | 0.092 |
| **`W = I` init, trained** | **1.000** (seeds [1.000, 1.000]) | **0.896** | **0.821** | **0.675** | **0.433** |
| `W = I` frozen (upper bound) | 1.000 | 0.912 | 0.817 | 0.658 | 0.396 |

`scripts/s5_init_lab.py`, 2 seeds, 192 training sequences, 200 epochs.

**Result 7 — the wall falls, with an honest label.** Both evaluation depths:
per-token choice accuracy goes from unstable-at-chance to a **perfect 1.000 on
both seeds**, and exact accuracy at L=4 goes from 0.508 to **0.896** (112×
chance). Earlier in this work the same task was reported as unsolved at 0.297
with "the published wall holds"; that conclusion was an artefact of a bad
initialisation, not of the group representation.

### Result 8 — the MLP readout is a LOOKUP TABLE (measured, not assumed)

The readout still decayed with length, so the sharpest possible test was run:
split accuracy by whether the target permutation was *reachable* during
training (`scripts/s5_curriculum_lab.py`).

| training lengths | states reachable | acc(seen) | **acc(UNSEEN)** |
|---|---|---|---|
| 1–6 | 37/120 | **1.000** | **0.000** |
| 1–12 | 58/120 | 0.031 | 0.000 |

Perfect on what it saw, **zero** on what it did not. And a length curriculum
lifts the headline (L=48: 0.317 → 0.446) but cannot fix a head that must
memorise 120 classes.

Class coverage by maximum training length: L=4 → 49/120, L=6 → 91/120,
L=8 → 115/120, L=12 → **120/120**.

### Result 9 — a STRUCTURAL readout needs no readout at all

The state **is** the answer: a permutation matrix satisfies `M[i][p(i)] = 1`, so
its group element is read off by an inner product against the 120 permutation
matrices,

```
logits_c = <S, M_c>          dL/dS = Σ_c (p_c − 1[c == target]) · M_c
```

No parameters (the "weights" are the fixed matrix catalogue), full coverage of
all 120 classes by construction, and the gradient verified against central
differences at `worst_rel = 0.000e+00`. Nothing about the answer can be
memorised, because nothing about it is learned.

### Result 10 — the single decisive hyper-parameter is tau

The structural readout failed at first (0.095 at L=4) — and that failure was
diagnosed, not worked around. `<S, M_c>` is exact only if `S` really is a
permutation matrix; with tau=1 the choices are diffuse and the product of
mixtures **diffuses toward uniform**. Measured distance from the state to the
nearest permutation matrix, with perfect choice weights and no training:

| tau | dist-to-perm | L=4 | L=12* | L=48* | **L=200*** |
|---|---|---|---|---|---|
| 1.0 | 1.7e+00 | 0.095 | 0.050 | 0.005 | 0.000 |
| 0.3 | 9.1e-01 | 1.000 | 1.000 | 0.675 | 0.010 |
| **0.1** | **1.8e-03** | **1.000** | **1.000** | **1.000** | **1.000** |
| ≤0.03 | ~0 | 1.000 | 1.000 | 1.000 | 1.000 |

At tau ≤ 0.1 the state is an exact group element and accuracy is **1.000 at
every length**, including L=200 — **33× beyond anything trained on**. The whole
pipeline then contains **30 learned parameters** (the `K² + K` per-token choice
matrix — 25 for W plus 5 for the bias), a fixed
catalogue of group matrices, and an exact inner product.

**The unifying finding across every experiment in both papers: DIFFUSION is the
failure mode.** A soft mixture of group elements drifts toward uniform — seen
in the abelian convolution state, in the S_5 initialisation, and again at
tau=1. Every fix was the same in kind: force the state back onto the group.

## 6. Scaling: does the method survive larger and harder groups?

Everything above used Z_K or S_5. "It works" only matters if it survives larger
and structurally different groups. `scripts/group_scaling_lab.py` builds six
permutation groups, verifies each one's axioms, matrix convention and generator
span **before** measuring, and then trains on short words only.

| group | type | \|G\| | Cayley diam | cov@12 | params | L=4 | L=48* | **L=96*** |
|---|---|---|---|---|---|---|---|
| D12 | dihedral, non-abelian, solvable | 12 | 4 | 1.000 | 6 | 1.000 | 1.000 | **1.000** |
| Z10 | cyclic, abelian | 10 | 9 | 1.000 | 2 | 1.000 | 1.000 | **1.000** |
| A5 | **simple, non-solvable** | 60 | 8 | 1.000 | 6 | 1.000 | 1.000 | **1.000** |
| S5 | non-solvable | 120 | 10 | 1.000 | 20 | 1.000 | 1.000 | **1.000** |
| S6 | non-solvable | **720** | 15 | 0.972 | 30 | 1.000 | 1.000 | **1.000** |

`*` = length never trained on. Trained on lengths 1–7. Parameters are the
per-token choice matrix only (`K² + K`: W plus bias); the structural readout
has none.

**Result 11 — the method scales, and stays tiny.** Parameter count tracks the
number of GENERATORS (`K² + K`), not the group order: S6 has **6×** the
elements of S5 and needs 30 parameters instead of 20. Elements per parameter
rises from 2.0× (D12) to **24×** (S6) — the larger the group, the cheaper the
coverage per parameter. Accuracy is 1.000 at every tested length for every
group, including 96× the training length.

**A parameter-count error, corrected.** An earlier version of the script
printed `params = 2·num_gens` and the paper reported **8** for S5 and **10**
for S6. That was wrong twice: it counted one scalar per generator instead of
the full `K×K` matrix, and `PermState` was also building an unused MLP head
(4792 dead parameters) alongside the structural readout. Both are fixed; the
figures in the table are now read from `reports/group_scaling_results.json`
and match the code. **Reported parameter counts in this work should be treated
with the same suspicion as reported accuracy until they come from a file.**

**Result 12 — the structural readout does not need full coverage.** S6 reaches
only **97.2%** of its elements within the training length budget, yet scores
1.000 — because the readout computes rather than memorises. Compare the learned
MLP head (§Result 8), which scored 1.000 on seen states and **0.000** on unseen
ones with the same kind of gap.

**A generator error the selftest caught:** two 3-cycles do **not** generate A5.
The reach check returned `gens_reach=False` before any accuracy number was
produced; the fix was a 3-cycle plus a 5-cycle. This is exactly why every group
is verified (closure, identity, inverses, `matrix(compose(a,b)) == M_b @ M_a`,
generator span, non-commutativity) before use, and why the gradient is checked
against finite differences per group (`worst_rel = 0.000e+00` for all six).

**What is still NOT done, stated plainly:** this is a **component**, measured on
synthetic group tasks. It is **not integrated** into any language model, and it
has **never been trained on real data**. Scaling *within* the group family is
established; scaling *to language* is untested.

## 7. Integration — from a demonstrated result to a usable artifact

Everything above trained a model and evaluated it **in the same process**.
Nothing was ever written to disk, so the architecture could not be *used* — only
demonstrated. That gap is now closed.

### What was built

`scripts/group_state_engine.py` trains a tracker on a named group, **saves** the
weights to JSON, **reloads** them, and answers state-tracking queries. The
artifact is 383–773 bytes. Five groups are trained and persisted
(`models/group_state_{z10,d12,a5,s5,s6}.json`):

| group | \|G\| | params | trained on | accuracy at L=96 (never trained past 7) |
|---|---|---|---|---|
| Z10 | 10 | 2 | lengths 1–7 | 1.000 |
| D12 | 12 | 6 | lengths 1–7 | 1.000 |
| A5 | 60 | 6 | lengths 1–7 | 1.000 |
| S5 | 120 | 20 | lengths 1–7 | 1.000 |
| S6 | 720 | 30 | lengths 1–7 | 1.000 |

### How it is wired into OpenAmer

The tool server (`:8081`, the 9-tool interface the 2B core calls) now exposes a
**10th tool**, `group_state`, via `/execute_tool`. Verified live:

```
POST /execute_tool {"tool":"group_state","params":{"group":"S5","moves":[0,1,2,3,0]}}
-> {"result": {"group":"S5","length":5,"element_index":57,
               "element":[2,1,3,4,0],"correct":true,
               "verified_against":"independent composition","params":20},
    "security":"allow"}
```

Live stress test through HTTP, L=200 (28× the training length):

| group | correct |
|---|---|
| Z10, D12, A5, S5 | **10/10 each** |

### Honest boundaries of this integration

**This is a TOOL, not layers inside the language model.** Mini-OpenAmer is a
LoRA fine-tune of Qwen served as GGUF — there is no `nn.Module` to attach a
layer to. Claiming "integrated into the model" would be false. What is true:
when the agent needs state kept perfectly across many steps, it can now call a
mechanism that provably does so, instead of asking a recurrent network to.

**A defect the integration exposed, and what actually caused it.** Registering
the tool was not enough. The 2B model called `group_state` with
`{"group": "moves", "moves": [0, 1, 0, ...]}` — the parameter names swapped —
even though the tool was correctly registered in `TOOLS` and `EXECUTORS`. The
cause: `TOOLS_PROMPT` teaches the parameter format through an `EXAMPLES` block,
and only **4 of 10** tools had an example. `group_state` had none, so the model
guessed. Adding **one example line** made the same prompt work:

```json
{"tool": "group_state", "params": {"group": "S5", "moves": [0, 1, 2, 3, 0]}}
```

Verified live afterwards — three differently-worded requests, all correct:

| request | group chosen | result |
|---|---|---|
| "Track state through these S5 moves: 0 1 2 3 0" | S5 | `correct: true` |
| "Apply S5 generator moves 0, 1, 2 in order" | S5 | `correct: true` |
| "Track the A5 state for moves 0 1 0 1" | A5 | `correct: true` |

No regression on the other tools (`run_python`, `read_memory` still route
correctly). The lesson generalises: **a tool's registration is a static fact;
its usability is a prompt fact.** Registration checks passed all along while the
tool was unusable. Now guarded by `scripts/test_tool_server_wiring.py`, which
asserts both registration *and* the presence of an example whose parameter
names and shapes match the executor.

**A measured server-side cost that is not ours.** A `group_state` request takes
~2.05 s wall-clock, while the actual computation is **0.22 ms** — a factor of
~10,000. The overhead is the tool server's own per-request work (loading/status
of the 2B model, the security analyzer). Every tool pays it (`see`,
`run_python` included). Reported here so it is not mistaken for a property of
the architecture.

**A design error, corrected.** The first version trained a model on demand
inside a request. For S6 that is ~161 s, which blew the caller's timeout and
looked like a hang. Requests now only ever **load** a persisted artifact and
return a named fix command if none exists. Guarded by test case 5 in
`scripts/test_group_state_engine.py` (asserts the refusal takes < 2 s).

**Two test bugs of my own, both caught by the test suite:** (a) A5 has exactly
**2** generators, and a test that sent index 2 mis-flagged a *correct* rejection
as a failure — bounds are now read from the group, never assumed; (b) an earlier
gradient check used `-1.0` as the upstream gradient instead of the correct
`p − onehot(t)`, producing a constant 1.7e-05 discrepancy that could have been
misread as a code bug. The eps-sweep rule resolved it: a discrepancy that does
not change with eps is not numerical noise — suspect the test. With the correct
gradient the difference is **3.6e-12**.

## 8. What is still NOT done

- **Not a language model.** 2–30 parameters over fixed group generators. No
  language data has ever been used.
- **Not trained on real sequences.** Synthetic group products only.
- **Not attached to the LM's computation.** It is a callable tool.
- **Group family only.** Scaling within groups is established (§6); scaling to
  language is untested.

## 9. Reproduction

```bash
python scripts/s5_group.py                      # group axioms + generators
python scripts/perm_state_lab.py --selftest
python scripts/perm_state_lab.py --gradcheck     # soft group-state path
python scripts/perm_state_lab.py --gradcheck-mlp # learned-head path
python scripts/s5_init_lab.py --assert-init      # init gate (fast)
python scripts/s5_structural_readout.py --gradcheck
python scripts/s5_tau_sweep.py                   # the decisive tau sweep
python scripts/s5_curriculum_lab.py              # seen-vs-unseen coverage test
python scripts/group_scaling_lab.py --selftest   # 6 groups, axioms + grads
python scripts/perm_state_lab.py --epochs 300 --seeds 2
python scripts/diagnose_gradient_flow.py         # rules out vanishing gradient

# the integration: train, persist, then answer through the tool server
python scripts/group_state_engine.py --train S5
python scripts/group_state_engine.py --ask S5 --moves "0 1 2 3 0"
python scripts/test_group_state_engine.py        # save/load/answer/tool gate
```

Gradient verification: the soft non-abelian path (matrix product backward,
softmax over generators, tau scaling) matches central differences with
**worst_rel = 0.000e+00** at L=1, 3, 6 — so the numbers above are not artefacts
of a wrong derivative.

## 7. Honest scope

- 2 seeds; effect sizes are large relative to sampling noise at L=4–6 but this
  is not a significance claim.
- 24 training sequences: deliberately small, and a known confound — addressed
  in §5.
- CPU-only, pure Python, small models. No scaling claims.

## References

1. Merrill, Petty, Sabharwal. *The Illusion of State in State-Space Models.*
   arXiv:2404.08819, 2024.
2. *DeltaProduct: Improving State-Tracking in Linear RNNs via Householder
   Products.* arXiv:2502.10297, 2025.
3. Companion: `reports/exact_group_state_paper.md` (abelian Z_K case).
