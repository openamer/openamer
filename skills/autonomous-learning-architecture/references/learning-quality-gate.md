# Learning-Quality Gate — ein Label, das aus den Features folgt, ist kein Lernen

Measured 2026-09-22 in `scripts/self_learning.py` (OpenAmer laptop, CPU-only).
This is the class-level rule for **every** learning loop in this architecture
(Darwin, KTA, meta_learn, self_improve, self_learning): before any loop is allowed
to print a success line, its metric must be separated from its own input.

## The observed failure

```
=== ASI Self-Learning: Session-Daten → Neuronales Netz ===
Extrahiert: 52 Trainingssamples
  Ep   0: loss = 0.174645
  Ep 250: loss = 0.000092
✅ Training abgeschlossen — oa_ripple hat gelernt
```

Loss fell 0.17 → 0.0001 and training accuracy was **1.000/1.000**. Nothing was learned.

The label was `role == "assistant"`. The 7-feature vector contained
`role == "user"` **and** `tool_name is not None`. Cross-tab over the window, exact
and unambiguous:

```
role='assistant'  tool_name=NULL   n=12
role='tool'       tool_name set    n=40
role='user'       tool_name=NULL   n=1
```

Per-feature separation (n=52, newest-80 window of `state.db`):

| feature | direct acc | reverse acc | reading |
|---|---|---|---|
| `tool_name` present | 0.019 | **0.981** | leaks the label, inverted |
| `len(content)/500 >= 0.5` | 0.192 | **0.808** | leaks the label, inverted |
| `role == "user"` | 0.788 | 0.212 | circular by construction |
| majority class | 0.808 | — | — |

## Three rules

### 1. Score every feature against the label in BOTH directions

`strength = max(acc, 1 - acc)`.

The strongest leak here was **inverted** (`tool_name` at 0.019 direct = 98%
inverted). The first version of the honesty gate used `if base >= 0.70` and stayed
completely silent about a 0.981 separator. If your gate only looks one way, it is not
a gate.

### 2. Ablation is not a fix

Zeroing `role == "user"` — the obvious circular channel — left accuracy at **1.000**,
because `tool_name` still carried the label. A gate whose report is empty after the
ablation has missed the second channel, not solved the problem.

Corollary for the test: assert the leak report is **non-empty** after ablation. An
empty report is the failure signal, not the success signal.

### 3. Always carry the majority-class baseline

It was already **0.808**. You cannot beat the majority class by "learning" when the
label is identical to one of the inputs. Report it next to the accuracy, every run.

## Non-reproducibility: a metric from a random subsample is not a metric

The same script used `ORDER BY RANDOM()`, so consecutive runs sampled different rows:

```
n = 60 → 48 → 54 → 53 → 52 → 65   (positives 10–13)
```

Every accuracy figure from it was incomparable to every other. Make the extraction
deterministic (`ORDER BY id DESC`) *before* quoting any number.

Trap found while writing the verifier: the live window is "newest 80 rows" of a
store that **grows as the agent works**, so *which* features leak is not a stable
assertion. Assert invariants (structural relations, crafted cases with answers
knowable a priori), never a named member of a set the live contents decide.

## The gate, as shipped

`scripts/verify_self_learning.py` — 11 checks, targets any copy via argv:

```bash
python scripts/verify_self_learning.py                                    # AppData copy
python scripts/verify_self_learning.py C:/Users/damir/openamer-repo/scripts/self_learning.py
```

Proven in both directions — a gate only ever seen passing is untested:

| run | result |
|---|---|
| against the fix | 11 passed, exit 0 |
| against injected regression (`strength = base`, reverse term dropped) | **4 failed, exit 1** |

The repo-level test is `tests/scripts/test_self_learning_label_leak.py` (6 tests)
and runs on the canonical runner:

```bash
npm run test -- tests/scripts/ -q     # 24 files, 301 tests passed, 0 failed
```

Hermetic via a **function-parameter** seam: `extract_training_data(limit, drop_role,
db_path=None)`. Do NOT add an `OPENAMER_*` env var for this — AGENTS.md forbids new
env vars for non-secret config. A parameter is the seam.

## Data-source trap

The cron pre-run collector reported `no_session_data: true` by scanning
`sessions/*.json` (278 request dumps). The real corpus is in `state.db`:

```
messages : 260,723   (tool 125,143 / assistant 121,034 / user 14,546)
sessions :  12,679
tools    :      35
```

`no_session_data` is a claim about where the collector looked, not about whether
training data exists. Check the store before believing a "no data" signal.
