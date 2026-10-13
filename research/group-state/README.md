# Group-State Tracking — exact state for sequence models

Research into a recurrent mechanism that tracks **group state exactly at any
length**, where LSTMs fail. The measured headline (CPU only, minutes to
reproduce):

| task | LSTM | this mechanism |
|---|---|---|
| mod-7 (Z₇), trained on lengths 1–8 | 0.146 = chance | **1.000 at L=256** |
| parity (Z₂), trained on 1–12 | — | **1.000 at L=2048** (170×) |
| S₅ (non-solvable, 120 elements) | 0.000 at L=48 | **1.000 at L=200** (33×) |
| six groups up to \|S₆\|=720 | — | **1.000 at every tested length** |

The final S₅ pipeline contains **30 learned parameters** (`K²+K`: the per-token
choice matrix plus bias). The readout has none.

## The mechanism in one paragraph

The state is an exact group element, not a continuous vector that approximates
one. For abelian Z_K it is a K-th root of unity that is **snapped** back onto the
group after each step; for non-abelian groups it is a **permutation matrix**, and
the class is read off by an inner product against the group's own matrices
(`logits_c = <S, M_c>`), which needs no learned parameters. The one
hyper-parameter that decides everything is the softmax temperature `tau`: a
diffuse choice makes the product of per-token mixtures drift toward uniform, and
a diffuse state is no longer a group element.

**The single finding that unifies every failure in this work: diffusion.** A soft
mixture of group elements drifts to uniform. Each fix was the same in kind —
force the state back onto the group: snap the angle, initialise with correct
choices, sharpen `tau`.

## Papers

- `reports/exact_group_state_paper.md` — abelian groups (RotorSnap, Z_K)
- `reports/nonabelian_s5_paper.md` — non-abelian groups, scaling, integration

Both record negative results and corrected errors rather than deleting them:
overturned conclusions are kept with the measurement that overturned them.

## Layout

```
scripts/   the architecture, the experiments, the gates
reports/   papers + the JSON files the papers cite
models/    trained artifacts (0.4–0.8 KB each), reloadable
```

## Reproduce

Pure Python, no dependencies beyond the stdlib. Run the gate:

```bash
bash scripts/run_research_tests.sh --fast    # 44 checks, no slow E2E
bash scripts/run_research_tests.sh           # + end-to-end reproduction (~15 min)
```

Individual pieces:

```bash
python scripts/s5_group.py                  # group axioms + generators
python scripts/perm_state_lab.py --gradcheck-mlp
python scripts/s5_tau_sweep.py              # the decisive tau sweep
python scripts/group_scaling_lab.py --selftest
python scripts/free_group_lab.py --selftest
python scripts/test_group_state_engine.py   # save/load/answer
```

## Scope — what this is not

- It is a **mechanism**, measured on **synthetic group tasks**. Not a language
  model; no language data has been used.
- It is **not** attached to an LM's computation. In the host project it is a
  callable tool, because the deployed model is a LoRA fine-tune served as GGUF —
  there is no module to attach a layer to.
- Scaling **within** the group family is established (up to \|S₆\|=720, plus a
  faithful embedding of the infinite free group F₂). Scaling **to language** is
  untested.

## Verification discipline

Every gradient is checked against finite differences before any result is read.
A parameter count is obtained by summing `params()`, never by formula. Reported
accuracy is a multi-seed figure where a single seed would be misleading — one
early S₅ number (0.656) was a single seed from an un-reproducible run and is
flagged as such in the paper rather than quietly replaced.
