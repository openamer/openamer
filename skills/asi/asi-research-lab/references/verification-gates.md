# Verification Gates for Research Claims

Session origin: 2026-09-21 (state-tracking / S_5 work). This is the durable
methodology extracted from that session — the part that generalises beyond the
specific experiment.

## Why a gate and not a command

The project had **no `test` script at all** (`npm error Missing script:
"test"`; `package.json` held only `check`/`fix`/`audit:*`). Meanwhile `check`
linted TypeScript workspaces the research code never touched, so it could never
go green. Reporting "no test script exists" is a blocker report; building the
gate is the fix.

Rule: when the project has no way to verify your work, **build the gate**.
A gate is a re-runnable script wired into the project's canonical command, not a
command you retype from memory.

## The pattern

`scripts/run_research_tests.sh`, wired as `npm run test` (plus
`test:research` for the slow full run).

Stage order is chosen by **evidential strength** — cheapest proofs first, so a
failure is localized:

1. `compile` — every script, `python -m py_compile`
2. `gradients` — finite-difference checks vs analytic derivatives
3. `backward proof` — model-vs-model equivalence (see below)
4. `group axioms / convention` — mathematical ground truth
5. `hygiene` — dead imports, seeded-init determinism, no exploitable prior
6. `end-to-end result` — reproduces the claim (skipped by `--fast`)

Mechanics that matter:

- **One stage per process.** A `stage "name" cmd...` helper runs each check as
  its own subprocess so one crash cannot mask the others; it prints `PASS` or
  `FAIL` plus the tail of the output only on failure.
- **Exit non-zero if any stage fails**, and list the failed names at the end.
- **`--fast` skips only the slowest stage**, never the correctness stages.

## Error class 1 — non-deterministic weight init (the silent flake)

**Symptom:** `npm run test` flips PASS/FAIL on unchanged code. The suspect check
passes 6/6 when run standalone and fails inside the suite.

**Cause:** a `randn()` helper fell back to the *global* `random` module instead
of the seeded generator its caller passed in:

```python
def randn(scale, rng=None):
    return (rng if rng is not None else random).gauss(0.0, scale)
```

Every model already received `rng`; it was simply never used, so two models
built from `random.Random(1)` had different weights.

**Proof before fix** (measure, don't assume):

```python
a = Model(..., random.Random(1))
b = Model(..., random.Random(1))
assert all(pa.data == pb.data for pa, pb in zip(a.params(), b.params()))
```

Measured before: all four models differ. After: identical, and 10/10 gradcheck
runs produced bit-identical output.

**Fix:** thread `rng` into every init call — `randn(scale, rng)` — and keep a
**determinism gate** permanently in the suite
(`scripts/seed_init_fix.py --check`: same seed → identical weights). Without the
gate this regresses silently the next time someone adds a layer.

## Error class 2 — measure the flake before "fixing" it

First hypothesis for the intermittent failure was a too-loose `1e-6` absolute
threshold in the gradient check. It was **wrong**.

`scripts/gradcheck_flaky_probe.py` ran each case 12x and recorded the actual
error distribution:

| case | worst_abs | entries above 1e-6 | grad scale |
|---|---|---|---|
| parity K=2 L=1 | 1.658e-11 | 0 | 0.581 |
| mod7 K=7 L=9 | 3.173e-11 | 0 | 0.868 |

Worst absolute error 1.5e-10, **zero** entries over the floor. The threshold was
never the cause. Had it been "fixed", the real bug (class 1) would have stayed
hidden behind a looser gate.

Rule: when a check is flaky, **first instrument the failure and collect the
distribution** — then fix what the data names. Never adjust a threshold you
have not shown to be the cause.

## Error class 3 — a broken instrument is not a failed construction

A diagnostic froze the choice weights at identity (provably perfect per-token
choice) and expected exact accuracy 1.000 — got chance.

**Cause:** the readout head was left at its random initialisation. The head is
what maps state → classes; untrained, it decodes nothing. The test measured
"perfect state + blind decoder" and returned 0.008.

**Correct instrument:** freeze the *choice* weights, **train the head**. Result:
0.928 at L=4, decaying to 0.353 at L=48 — i.e. genuinely decodable.

Rule: before concluding a construction is wrong, check whether the test could
have succeeded at all. A negative result from an untrained component is a
statement about the test.

## Error class 4 — the state was input-independent (a WRONG negative result)

The biggest find of the session, and the one that would have been lost by
stopping at the first negative answer.

**What was reported:** a new mechanism "does not break the wall", best 0.297 at
L=4 against 0.008 chance. Written up and believed.

**What was actually true:** the mechanism was correct; the *initialisation* made
its state effectively input-independent. After the fix: **0.656** — more than
double.

### The elimination order (cheapest suspect first)

| suspect | probe | verdict |
|---|---|---|
| vanishing / exploding gradient | instrument the backward walk; record ‖state-grad‖ per token position; report first/last ratio | **REFUTED** — ratio 0.44 at L=32, profile *flattens* with length |
| wrong derivative | finite-difference gradcheck | passed, `worst_rel = 0.000e+00` |
| test cannot prove the claim | freeze to a known-correct setting, confirm the claim becomes true | found a broken instrument first (class 3) |
| **input never reaches the state** | **input-dependence of the state** | **THE BUG** |

### The measurement that found it

Compute the internal state for many **different** random inputs and measure the
mean pairwise L2 distance between those states:

| init | input-dependence | per-token choice accuracy |
|---|---|---|
| small random `W` | **0.109** | 0.197 (= chance 0.20) |
| `W = I` + noise | **0.183** | **1.000** |

At 0.109 the states of different sequences are nearly the same → the readout sees
a **constant feature**, receives no usable gradient, and the input-side matrix
never learns. Nothing was wrong with the architecture; it never had a chance.

Root cause: a small random `W` makes `softmax(W·onehot(x))` near-uniform for
every token, so every per-token mixture is the same near-average matrix and the
product of T such matrices is again near-uniform. Fix: `W = I` (+ small noise)
so `argmax` is already correct at step 0.

**This is the same diffusion that killed the abelian convolution hypothesis** —
a soft mixture of group elements drifts toward uniform. Two independent failures,
one underlying mechanism.

Now a gate: `s5_init_lab.py --assert-init` (fails below 0.15; negative-tested by
forcing `init="random"`). A portable version lives in
`scripts/input-dependence-probe.py`.

### The generalisable rule

**A negative result is a claim. Instrument before believing it.** "It did not
learn" says nothing about your architecture until these are measured separately:

1. the input actually reaches the state (input-dependence probe)
2. the state can represent the answer (freeze to a known-correct state)
3. the readout can decode it (train the head on a frozen-correct state)
4. the optimiser receives a usable gradient (gradient-flow instrumentation)

Four cheap probes cost far less than abandoning a correct idea — and in this
session the abandoned idea was the good one.

## Error class 5 — verify the SPAN of your ground truth, not just its axioms

When a task is defined *relative to* a mathematical structure, checking the
structure's axioms is not enough — you must check that your chosen **generators
span the whole structure**. Otherwise you silently shrink the reachable space
and every downstream number is measured against the wrong problem.

Concrete: two 3-cycles do **not** generate A5. The BFS reach check returned
`gens_reach=False` **before any accuracy number was produced**. Fix: a 3-cycle
plus a 5-cycle. Had the check not existed, the group would have looked "harder
than it is" (or "broken") for reasons unrelated to the architecture.

The per-structure check list, run in this order before reading any measurement:

```
closure            compose(a,b) in G for all pairs
identity           compose(a,e) == a == compose(e,a)
inverses           inverse(a) in G
convention         the representation is consistent with the operation
                   (e.g. matrix(compose(a,b)) == M_b @ M_a)
span               BFS from the identity over the generators reaches ALL of G
non-commutativity  exists a,b with a·b != b·a   (confirms the hard case is real)
gradient           per-structure finite-difference check
```

Rule: **the convention (how your representation composes) is the single easiest
thing to get backwards, and it invalidates everything.** Verify it
programmatically over the whole structure — never trust a comment that states it.
Likewise a hand-derived expectation: `compose(a,b)` applying **b first** gave
`(01)·(12) = (1,2,0,3,4)`, not the "obvious" `(2,0,1,3,4)`. Derive index by
index; the red self-test was my error, not the code's.

## Rubber-stamp check (mandatory for any gate)

A gate that cannot fail proves nothing. Demonstrate it fails:

1. Temporarily set an impossible threshold / break the invariant.
2. Run the gate, confirm exit != 0 and a meaningful message.
3. Restore the file (write back the original text, preserving line endings).

Done for `s5_prior_check.py --assert-prior`: with the cap forced to `0.0001` it
exited 1 and printed the reason. Recorded as a negative test.

**Negative-test every gate you add, not just the first one.** Three more were
proven this session, each by injecting the real defect rather than faking a
threshold:

| gate | injected defect | result |
|---|---|---|
| `check_unused_imports.py` | added a genuinely unused `import sys as _x` | exit 1 |
| `seed_init_fix.py --check` | reverted one `randn(..., rng)` to the unseeded form | exit 1 |
| compile stage | added a non-existent script to the list | exit 1, names the file |
| `s5_init_lab.py --assert-init` | forced `init="random"` | exit 1 (0.1087 < 0.15) |

Injecting the **real** defect is a stronger proof than moving a threshold: it
shows the gate detects the failure mode you actually care about.

**Corollary — a simplification to a gate needs its own negative test.** The
compile loop dropped a special-case `[ -f file ] ||` check on the reasoning that
`py_compile` fails on a missing file anyway. That reasoning was then *proven* by
injecting a missing filename and confirming exit 1 with the file named. When you
delete defensive code, prove the remaining path still catches the case.

## Adding new scripts to the suite

The headline claim "the construction is proven sound" was itself put on trial:
a head could look accurate merely by predicting the **majority permutation** for
each length, and a random walk on a group *mixes* — so the prior is peaked at
short lengths and near-uniform at long ones, exactly the shape of the measured
accuracy.

Measured against the majority-class baseline:

| L | model | majority base | excess | entropy/uniform |
|---|---|---|---|---|
| 4 | 0.928 | 0.0927 | +0.836 | 0.717 |
| 48 | 0.353 | 0.0103 | **+0.343** | 0.999 |

At L=48 the walk is nearly mixed (entropy 0.999), capping a prior-exploiter at
0.010 — the model reached 0.353, so it really decodes. **But** the excess itself
decays, which the original claim did not account for. The claim was
**downgraded** in the write-up, and this check became a permanent gate
(`s5_prior_check.py --assert-prior`, <2s).

Rule: for any accuracy number on a classification task, always report the
**majority-class baseline and the target-distribution entropy** next to it.
Without them an accuracy figure is uninterpretable.

## Adding new scripts to the suite

New analysis scripts sat *beside* the gate for a while — effectively unverified
code with the appearance of being covered. Add every new script to the suite in
the same change that creates it, and prefer turning a one-off diagnostic into a
fast `--assert-*` gate plus a full diagnostic mode.

## Related

- The research-specific findings these gates protect: skill `exact-group-state`
  (user-owned — read it, do not patch it autonomously).
- Frontier selection and how to attack a published limit:
  `references/architecture-research-method.md`.
