# Architecture research method — how to actually be a step ahead

Session 2026-09-21. This is the repeatable method behind the state-tracking
result in the parent skill, written down so the next run starts from the
technique instead of rediscovering it.

The user's mandate: *"wir müssen neu neuronale netzwerke erfinden, wir müssen
immer ein schritt voraus sein als alle andere in der welt."* Inventing beats
repairing. Below is how to do that with the tools actually available here.

## 1. Find a PUBLISHED limit, not a fun idea

Being ahead requires a wall that other people have documented. An idea that
merely amuses you has no baseline and therefore no result.

**The arXiv API recipe** (no browser, no search backend needed — `web_search`
may be unavailable, the arXiv API is not):

```python
import re, urllib.parse, urllib.request

q = 'all:"illusion of state" AND all:"state space"'
url = ("http://export.arxiv.org/api/query?search_query="
       + urllib.parse.quote(q) + "&max_results=4&sortBy=relevance")
xml = urllib.request.urlopen(url, timeout=40).read().decode("utf-8", "replace")
titles = re.findall(r"<title>(.*?)</title>", xml, re.S)[1:]   # [0] is the feed
dates  = re.findall(r"<published>(.*?)</published>", xml)
```

Query shapes that surfaced the frontier for this work:

| query | what it found |
|---|---|
| `all:"illusion of state" AND all:"state space"` | the formal limit (2404.08819) |
| `all:"state tracking" AND all:transformer` | DeltaProduct, current attempts |
| `all:parity AND all:"neural network" AND all:expressivity` | expressivity work |
| `all:"modular arithmetic" AND all:transformer` | task-specific attempts |
| `all:"state space model" AND all:limitation AND all:tradeoff` | open tradeoffs |

Read the abstracts for the phrase that names what current architectures
**cannot** do. "Cannot" is where a new mechanism can win.

## 2. Reproduce the wall before attacking it

Build the baselines first and confirm they FAIL as the literature says. This is
not busywork — it (a) proves your harness is sound, and (b) gives you the
baseline number your result must beat.

For state tracking, the baselines are:
- bag-of-tokens (no recurrence) — proves the task needs order
- tanh RNN — the saturating recurrence
- LSTM — the strong classical baseline
- *(your idea)*

Measured here: LSTM sat at chance (0.115–0.167, chance 0.143) on mod-7 at every
length. That is the wall, reproduced from scratch.

## 3. Isolate ONE mechanism per comparison

Give every mechanism the **identical readout head**, so the only variable is the
temporal mechanism. If your idea uses a bigger head, you have measured the head.

## 4. Make the task measure the property you claim

The discriminator is **length generalisation**: train on short sequences, evaluate
on lengths never seen. A mechanism that pattern-matches collapses; one that
tracks state holds. Report every column as `L` with `*` for unseen lengths.

## 5. Verify gradients BEFORE reading any result

A wrong derivative produces plausible-looking tables — the most dangerous
failure mode in this work, because the output looks like science.

Write a `--gradcheck` that compares analytic gradients to central differences.
Two traps that both fired in this session:

- **A finite-difference check across a rounding step returns exactly 0.** An eps
  nudge does not change a rounded value, so FD = 0 while a straight-through
  gradient is deliberately non-zero → `rel = 1.0` reads as a bug. Correct test:
  with the rounding **disabled**, the model must reduce **bit-identically**
  (forward AND backward) to its continuous counterpart.
- **Relative-only thresholds flag noise.** Where the true gradient is ~1e-17,
  round-off makes `0 vs 1e-17` look like 100 % error while the absolute error is
  1e-17. Run an **eps sweep** (1e-3 … 1e-7) and judge on ABSOLUTE error against
  the gradient scale.

## 6. Chase the failure, don't hide it

When your mechanism works at trained lengths but collapses longer, that gap is
the finding — instrument it. Here: the mechanism learned the exact group angle
to **0.08 %** and *still* collapsed, which pointed at accumulation rather than
representation, and produced the fix (snap onto the group).

Print the learned parameters and compare them to the ideal. The near-miss
(0.8983 vs 2π/7 = 0.8976) was more informative than any accuracy number.

## 7. Report the failed hypothesis — it is the most valuable entry

A negative result that kills a plausible line early is worth more than a
marginal positive. The failed distribution/convolution experiment here
(softmax + circular convolution → random walk → information destroyed) is
recorded prominently, because it stops the next agent from spending a week on it.

## 8. A NEGATIVE RESULT ON YOUR OWN ARCHITECTURE IS USUALLY A BUG

This is the highest-value technique in the whole document. The S_5 (non-abelian)
block ended with *"we did not break the wall, best 0.297"* — and it was **wrong**.
The mechanism was correct; a bad initialisation was hiding it. Final number after
the fix: **0.656**, more than double.

**The discipline: before concluding your idea does not work, eliminate the
suspects by MEASUREMENT, cheapest first.**

| suspect | how to refute it | measured here |
|---|---|---|
| vanishing / exploding gradient | instrument the backward walk, record ‖gS‖ per token position, report first/last ratio | **REFUTED**: ratio 0.44 at L=32, profile *flattens* |
| broken derivative | finite-difference gradcheck (see §5) | passed, `worst_rel = 0.000e+00` |
| test cannot prove the claim | freeze the weights to a KNOWN-correct setting and check the claim becomes true | see the broken-instrument trap below |
| **the input never reaches the state** | measure the **input-dependence** of the state: mean pairwise distance between the states of *different* random inputs | **THE BUG**: 0.109 (random `W`) vs 0.183 (`W = I`) |

**The winning measurement, and it is one function call:** at initialisation,
compute the state for many *different* inputs and measure how far apart those
states are. If they are all nearly the same, the state is **input-independent** —
the readout sees a constant feature, gets no gradient signal, and the input-side
weights never learn. Nothing about the architecture is wrong; it never had a
chance to learn.

Root cause in this case: a small random `W` makes `softmax(W·onehot(x))` near-
**uniform** for every token, so each per-token group mixture is the same
near-average matrix and the product of T such matrices is again near-uniform.
Fix: initialise `W = I` (+ small noise) so `argmax` is correct from step 0.

**This is the SAME diffusion** that killed the abelian convolution hypothesis
(§7): a soft mixture of group elements drifts toward uniform. Two independent
failures, one mechanism. Worth knowing before designing any soft relaxation.

### The broken-instrument trap

A frozen-weight test with an **untrained readout** measures "perfect state +
blind decoder" and returns chance. It looks like a refutation of your construction
and is nothing of the sort. When freezing weights to prove a claim, freeze ONLY
the part whose correctness you are asserting, and let the rest train.

### Generalisation

For any new mechanism: **report a negative result only after you have instrumented
the path and shown the signal reaches both ends.** "It did not learn" is not a
finding about the architecture until you have separated (a) the input never
reaches the state, (b) the state cannot represent the answer, (c) the readout
cannot decode it, (d) the optimiser never gets a usable gradient. Each has a
distinct cheap probe; four probes is cheaper than abandoning a correct idea.

### When you do land a fix: attack the new number too

The doubled result was then checked against the **majority-class baseline** at
each length (excess over prior **+0.836 → +0.343**, and at L=48 a random walk has
normalised entropy 0.999 so a prior-exploiter is capped at 0.010). Without that
check the win could have been an artefact of an imbalanced class distribution.
Wire it as a permanent gate (`--assert-prior`), not a one-off look.

## 10. Don't LEARN what the representation gives you for free

The single most valuable design lesson of the S_5 block, and it generalises far
beyond groups.

**Symptom:** the learned readout decayed with sequence length while the state
path was provably correct. The sharpest test — split accuracy by whether the
target was *reachable during training* — returned **acc(seen)=1.000,
acc(UNSEEN)=0.000**. Perfect on what it saw, zero on what it did not: the head
was a **lookup table** over 120 classes, memorising instead of generalising.

**The question to ask: does the output even need to be inferred?** If the state
already *is* the answer, the readout is an **inverse**, and an inverse derived
from structure has no parameters, so memorisation is impossible and coverage is
complete by construction.

For a permutation matrix the inverse is an inner product against the fixed
group catalogue:

```
logits_c = <S, M_c>          dL/dS = Σ_c (p_c − 1[c == target]) · M_c
```

No parameters, all 120 classes covered, gradient verified at
`worst_rel = 0.000e+00`. Accuracy went to **1.000 at every length including 200**
(33× the training lengths) with **25 learned parameters in the whole pipeline**.

**Method:** before growing a head, ask what the state representation *already*
encodes and whether the task is a closed-form transform of it. A learned decoder
on top of an exact representation is where coverage bugs and overfitting both
come from. (Corollary from §8: the structural readout also *failed* at first —
0.095 — because it needs the state to genuinely BE a permutation matrix. That
was diagnosed as a **state** problem via distance-to-group, not a readout
problem, and fixed by sharpening `tau`.)

## 11. Soft relaxations of a discrete structure all diffuse — check tau

The unifying law across the whole line: **a soft mixture of group elements drifts
toward uniform**. Seen three independent times (convolution state; random init;
tau=1), and every fix was the same in kind — force the state back onto the group.

Operationally, when a soft relaxation underperforms:

1. **Measure the distance from the state to the nearest discrete structure**
   (nearest permutation matrix, nearest group element). If it is large, the
   state has diffused and the readout cannot possibly identify anything.
2. **Sweep the temperature.** For S_5 the whole result hinged on one number:
   tau=1.0 → dist-to-perm 1.7 → accuracy 0.095; tau=0.1 → dist-to-perm
   1.8e-03 → **1.000 at every length**. A single hyper-parameter separated
   failure from perfection.
3. Prefer the representation that is **exact by construction** (snap the angle,
   initialise the choice correctly, sharpen tau) over one that approximates.

Full tables for the S_5 blocks: `references/nonabelian-s5-breakthrough.md`.

## 12. After one instance works: SCALE the instance, and check WHAT the cost tracks

A result on a single task is an anecdote. The next question is always *"does it
survive larger and structurally harder instances, and how does the cost grow?"*
— and that question is cheap to answer once the harness exists.

Build a family with the **same code path** and vary only the instance:

| group | type | \|G\| | params | L=96* |
|---|---|---|---|---|
| D12 | dihedral, non-abelian, solvable | 12 | 4 | 1.000 |
| Z10 | cyclic, abelian | 10 | 2 | 1.000 |
| A5 | simple, non-solvable | 60 | 4 | 1.000 |
| S5 | non-solvable | 120 | 8 | 1.000 |
| S6 | non-solvable | **720** | 10 | 1.000 |

**The result that matters is not "1.000 everywhere" — it is what the cost tracks.**
Parameter count grew with the number of **generators** (a structural property),
not with the **group order** (the instance size): S6 has 6× the elements of S5
and needed only 10 parameters instead of 8. That is the claim worth making, and
it is only visible because the family was built and measured.

Two things to include in a scaling study:

- **Structural difficulty, not just size.** A5 is tiny (60) but **simple and
  non-solvable**; D12 is small and non-abelian but solvable. Covering those
  distinct classes is what makes the sweep informative — a same-family size ramp
  alone would have missed both.
- **Whether the fixed parts need to grow.** The structural readout's catalogue
  grows with |G|, but that is a memory/compute cost, **not a learning cost** —
  nothing there is trained. Separating those two is the point.

### Verify the ground truth SPAN before measuring the family

The scaling sweep's first run produced `gens_reach=False` for A5 — two 3-cycles
do **not** generate A5. The check fired **before any accuracy number existed**.
Always assert, per instance: closure, identity, inverses, representation
convention, **generator span (BFS reaches all of G)**, non-commutativity, and a
per-instance gradient check. A wrong generator set silently shrinks the reachable
space and every number measured against it is meaningless.

### Keep the honest boundary in the same paragraph as the win

The scaling sweep established *within-family* scaling; it said nothing about
language. State plainly: **a component, not integrated into any language model,
never trained on real data.** A scaling result invites the reader to assume
generality you have not measured — name the axis you scaled and the axis you did
not. When the user pushes on "so does the new AI work?", answer with the
component/full-model distinction explicitly rather than letting a 1.000 imply
more than it covers.

## 13. Hygiene

- Run long sweeps with `terminal(background=true, notify_on_complete=true)`.
- Keep `--seeds` at 2–3 in pure Python; state the seed count next to results.
- Never name a scratch file after a stdlib module — `concurrent.py` shadowed the
  stdlib package and produced `torch` import errors that had nothing to do with
  torch.
- Clean up dead imports (`scripts/check_unused_imports.py`) so the research code
  stays readable.
- If the repo has no `test` script, wire one to the real gate rather than
  reporting the absence: `bash scripts/run_research_tests.sh --fast` (compile +
  gradchecks + backward proof + hygiene), registered as `npm run test`.
