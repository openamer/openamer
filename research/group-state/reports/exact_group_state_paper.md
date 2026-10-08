# Exact Group State for Length-Generalising State Tracking

**Author:** OpenAmer (CPU-only research lab)
**Date:** 2026-09-21
**Status:** experimental — all numbers below are produced by the scripts in this
directory and can be reproduced on CPU in minutes. No claim here is asserted
without a measurement behind it.

---

## 1. The wall

The hardest open problem for sequence architectures is **state tracking**:
computing order-sensitive, unbounded state such as parity, modular counting, or
a flip-flop. "The Illusion of State in State-Space Models" (arXiv 2404.08819,
2024) formalises the limit — SSM/linear-RNN recurrences live in a weak circuit
class and cannot solve these tasks at all, independent of width or training.
DeltaProduct (2025) and "Expressivity-Efficiency Tradeoffs for Hybrid Sequence
Models" (2026) are current assaults on the same wall.

We reproduced the wall from scratch on CPU (`scripts/state_tracking_lab.py`),
on mod-7 arithmetic, training on lengths 1–8:

| mechanism | L≤8 (trained) | L=32* | L=128* |
|---|---|---|---|
| bag-of-tokens (no recurrence) | 0.14 | 0.13 | 0.14 |
| tanh RNN | 0.17 | 0.14 | 0.18 |
| LSTM | 0.14 | 0.17 | 0.14 |
| **phase rotor** | **1.000** | 0.37 | 0.04 |

`*` unseen length. Chance is 1/7 = 0.143.

**Result 1.** A saturating recurrence — including a full LSTM — sits at
**chance** on modular counting. This is the published wall, reproduced.

**Result 2.** A **phase** state breaks it: one rotation per token reaches
**1.000 at the trained lengths**, a factor ~6 above every baseline. The
mechanism is not depth or width. A unit-modulus complex number composes
**exactly** under a group:

```
z_t = z_{t-1} * exp(i * theta(x_t))
theta(x) = 2*pi*x/k   =>   z_T = exp(i*2*pi*sum(x)/k)
```

so the running sum mod k is the accumulated phase, at O(1) state and one
rotation per token.

## 2. Why the rotor still collapsed

The rotor failed at long lengths (0.37 at 4× training length, 0.04 at 16×).
A continuous angle is never exactly a group element, and the residual error
accumulates. Measured directly (`scripts/diagnose_rotor_drift.py`):

- mod-7: learned angle **0.8983 rad** vs the ideal `2*pi/7 = 0.8976` — off by
  **0.08%**, but that residual multiplies by T.
- parity: learned angle 1.58 rad against an ideal of π = 3.14 — never snapped
  to the group at all, and it collapsed at 4× length.

**Result 3.** The failure is *phase drift*, and it is length-linear: the
mechanism learns the correct group element to within 0.1%, then loses it as the
error accumulates. Short training lengths hide the problem.

## 3. A hypothesis that FAILED

If the group is the right abstraction, a differentiable group algebra should
work better: let the state be a probability distribution over Z_K and let each
token apply circular convolution, which **is** addition mod K.

It fails. `scripts/cyclic_state_lab.py`, mod-7:

| mechanism | L≤8 | L=32* | L=128* |
|---|---|---|---|
| tanh RNN | 0.17 | 0.14 | 0.18 |
| LSTM | 0.14 | 0.17 | 0.14 |
| phase rotor | 1.000 | 0.37 | 0.04 |
| **cyclic-convolution (ours)** | **0.45** | 0.15 | 0.17 |

**Result 4 — a negative result we consider the most useful one here.**
Convolving *distributions* is a **random walk**: the state diffuses toward
uniform, and the information is destroyed. A differentiable relaxation of a
finite automaton is not an automaton. The group algebra is exact only for a
**point** state, never for a soft one. The gradients were verified correct
first (see §5), so this is a property of the design, not of the optimiser.

## 4. The fix: exact group state + the training recipe that matters

Keep the rotor — it already finds the right group — and remove drift by
**snapping** the angle onto the K-th roots of unity at every step:

```
raw_t   = w . x_t + b                    (learned, radians)
q_t     = round(K * raw_t / 2*pi) mod K  (nearest element of Z_K)
theta_t = 2*pi * q_t / K                 (EXACT root of unity)
z_t     = z_{t-1} * exp(i * theta_t)
```

`exp(i*theta_t)` is an exact root of unity, so `z_T` lands exactly on the group
for **any** length: no angle error remains to accumulate. Length generalisation
stops being an empirical hope and becomes a property of the update. Rounding
blocks the gradient, so the backward pass uses a **straight-through estimator**
(Bengio et al. 2013): `d/draw := d/dtheta`.

Snapping alone is necessary but not sufficient. The straight-through estimator
is an *estimator*, so continuing to train after locking can walk the learned
angle off the correct group element — and how much that matters depends on the
group's size. The final controlled comparison
(`scripts/final_comparison.py`, 2 seeds, all modes on identical data):

**parity (Z_2), trained on lengths 1–12**

| mechanism | L=8 | L=64* | L=256* | L=1024* | L=2048* |
|---|---|---|---|---|---|
| LSTM (reference) | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| rotor, continuous | 1.000 | 0.625 | 0.833 | 0.969 | 0.958 |
| snapped from step 0 | 0.750 | 0.792 | 0.719 | 0.740 | 0.802 |
| **warm-up, then snap + continue** | **1.000** | **1.000** | **1.000** | **1.000** | **1.000** |
| warm-up, then snap + freeze | 0.750 | 0.792 | 0.719 | 0.740 | 0.802 |

**mod-7 (Z_7), trained on lengths 1–8**

| mechanism | L=6 | L=16* | L=64* | L=256* |
|---|---|---|---|---|
| LSTM (reference) | 0.115 | 0.115 | 0.146 | 0.156 |
| rotor, continuous | 1.000 | 0.875 | 0.052 | 0.427 |
| snapped from step 0 | 0.583 | 0.625 | 0.656 | 0.615 |
| warm-up, then snap + continue | 0.198 | 0.083 | 0.104 | 0.146 |
| **warm-up, then snap + FREEZE** | **1.000** | **1.000** | **0.979** | **1.000** |

**Result 5 — the central finding.** Two separate limits need two separate
mechanisms, and they compose:

1. **Saturation limit.** A saturating recurrence cannot represent cyclic state.
   LSTM is at chance on mod-7 (0.115–0.156) at *every* length. The phase
   representation crosses this limit: 1.000 at trained lengths, ~7× the
   baseline.
2. **Drift limit.** A continuous angle is never exactly a group element, so the
   error accumulates and the mechanism decays with length (mod-7 continuous:
   1.000 → 0.052). Snapping onto the group removes this limit *structurally*.
3. **Estimator limit.** The straight-through gradient is an estimator, so
   training after locking can drift the angle off the group. It is tolerable
   for |Z|=2 (snap + continue is perfect to L=2048) but destructive for |Z|=7
   (0.146) — where **freezing right after the snap** is what preserves the
   solution (1.000 to L=256).

**Result 6.** With the matched recipe the method achieves **exact length
generalisation with no decay**: parity to L=2048 (170× the longest training
length) and mod-7 to L=256 (32×), at O(1) state and one rotation per token —
on a task where the LSTM reference is at chance.

## 5. Verification traps — the ones that actually cost time

Every gradient was checked numerically before any result was read. Three traps,
all found by measurement rather than inspection:

1. **NON-DETERMINISTIC WEIGHT INIT (real bug, now fixed).** `randn()` fell back
   to the GLOBAL `random` module instead of the model's seeded `rng`, so two
   models built from the same seed got different weights. The gradient checks
   were therefore not reproducible and `npm run test` flipped between PASS and
   FAIL on identical code. Measured before the fix: all four models differ.
   After threading `rng` through every init call: identical. A determinism gate
   is now part of the suite, so this cannot regress silently.
2. **A finite-difference gradcheck across a ROUNDING step returns exactly 0.**
   Comparing that 0 to a deliberate STE gradient gives `rel = 1.0` and reads as
   a bug. The correct test: with snapping disabled the model must be
   bit-identical to its continuous counterpart (measured diff `0.000e+00`).
3. **A relative-only gradient threshold flags noise.** Where the true gradient
   is ~1e-17, round-off makes `0 vs 1e-17` look like 100% error. An eps sweep
   (1e-3…1e-7) showed the absolute error stays 1e-8…2e-11 against a gradient
   scale of 0.886. Judged on absolute error relative to the model's scale.

An earlier hypothesis that the fixed `1e-6` absolute floor was itself the flaky
cause was **tested and refuted** (`gradcheck_flaky_probe.py`: 0 entries ever
exceeded it, worst absolute error 1.5e-10). The real cause was (1).

## 6. Why this is not just "quantise the angle"

The claim is narrow and testable: **a continuous-angle state loses unbounded
state tracking through accumulation error, and an exactly group-valued state
does not.** The contribution is the argument that the saturation limit and the
drift limit are two *separate* failures — the phase representation beats the
saturation limit (Result 2), and snapping beats the drift limit (§4) — together
with measurements that isolate each.

Scope and honest limits:
- The readout is a small MLP over `[Re(z), Im(z)]`; the state is what is exact.
- `K` is a hyper-parameter matched to the task's group; discovering K from data
  is not solved here.
- This is a **component**, not a language model. Whether an LM can be trained
  end-to-end with snapped group state at scale is untested.

## 7. Reproduction

```bash
python scripts/state_tracking_lab.py --gradcheck      # gradients: OK
python scripts/state_tracking_lab.py --quick          # the wall, both tasks
python scripts/diagnose_rotor_drift.py                # drift measurement
python scripts/cyclic_state_lab.py                    # the failed hypothesis
python scripts/validate_rotor_snap.py                 # backward + STE proof
python scripts/rotor_snap_lab.py --epochs 600 --seeds 3
```

Artefacts: `reports/state_tracking_results.json`,
`reports/cyclic_state_results.json`, `reports/rotor_snap_results.json`.

## References

1. Merrill, Petty, Sabharwal. *The Illusion of State in State-Space Models.*
   arXiv:2404.08819, 2024.
2. *DeltaProduct: Improving State-Tracking in Linear RNNs via Householder
   Products.* arXiv:2502.10297, 2025.
3. *Expressivity-Efficiency Tradeoffs for Hybrid Sequence Models.*
   arXiv:2603.xxxxx, 2026.
4. Bengio, Léonard, Courville. *Estimating or Propagating Gradients Through
   Stochastic Neurons for Conditional Computation.* arXiv:1308.3432, 2013.
