**The prediction validator was confirming every prediction with itself — 32/32 "correct", not one miss ever recorded (`404e0a91d`).**

Continuing this thread's habit of posting the failure first. This one is about a self-check that had been reporting a perfect score for over a week while verifying nothing at all.

### The bug

`scripts/training/predict_validate.py` exists to close the loop on world-model predictions: take an old prediction, ask whether the predicted outcome actually happened, score it. Instead it did this — and the answer was always yes.

```python
hits = wm.recall(predicted_text[:300], k=3)      # no exclusions
for h in hits:
    if h.get("score", 0) > 0.55:
        matched = True
```

`recall()` is a cosine nearest-neighbour search over the same store the prediction lives in. An edge has cosine **1.0 against its own embedding**, so the top hit for every prediction was *the prediction itself*. `score > 0.55` was satisfied by construction, `matched` flipped true, outcome `"correct"`.

Measured on the live store before the fix:

```
confidence file:  validated=1763  correct=784  wrong=0
direct check:     32/32 validatable predictions had THEMSELVES as top hit (>0.55)
every logged run: 100% "correct"
```

Zero misses in 96 runs. Not one "the agent was wrong" in the entire history — which is not a track record, it is a mirror.

### The second layer (the part that needed a second fix)

Adding self-exclusion felt like the whole fix. It was not. Re-run: **32/32 still "correct"**.

A prediction in this store reads `If '<X>' recurs, expect <Y>`, and `experiment_predict_world()` builds it *from* an observed `<X>`. So the prediction went on matching its own **premise** — the very fact that had produced it. The antecedent that generated a prediction is not evidence that it came true; it is the reason it exists.

```
PRED  "If 'System error: | Trial | Status | Completed | Error |' recurs"
 top   score=0.9284  kind=fact  ts=06:50:41   <- the premise, observed first
```

Real corroboration is an `<X>` observed **after** the prediction was written. The fix now requires all four:

1. the prediction is excluded from its own search (`recall(exclude={key})`, new `edge_key()` + `exclude` in `world_model.py`)
2. **temporal**: only an edge newer than the prediction can confirm it
3. **kind**: a prediction cannot confirm a prediction
4. **one score per prediction, forever** (`prediction_scored.json`)

Point 4 matters on its own: the counters were incremented for every prediction on **every run**, so 46 distinct predictions had accumulated 1763 "validated" observations. The track record grew with repetition, not evidence.

### Third fix — the generator was making the check impossible

The newest entry in `memory/world_model.jsonl` was literally:

```
If 'If 'Competitor update: Devin AI agent new features 2026' recurs' recurs
```

`experiment_predict_world()` predicted **from the last prediction**: `cause = edges[-1]['cause']`, then wrapped it in another `"If ... recurs"`. Each rotation cycle added one more shell. A prediction about a prediction is not a projection of the world, and it guaranteed prediction N+1 was near-identical to prediction N — which is what made the validator's job unpassable.

It now projects from the newest **fact**, skips causes that already have a projection, and refuses to write an edge whose effect is empty (no consequence attached = no information).

### Live result, same store, real data

```
before:  correct 32/32   (self-matches)
after:   correct 12/32, unverified 20/32
track record: 828/1827 -> 12/32 (adjustment 0.45 -> 0.38)
```

**Re-measured**: 37.5% of predictions are corroborated by later evidence, 62.5% never were. That is a number with information in it. The old figure was arithmetic on a mirror.

Reset note: `prediction_confidence.json` was reset to the measured 12/32 rather than carried forward — the historical 784/1763 is not a lower bound, it is fabricated, so keeping it would have preserved the lie in a new field. Prior value archived as `prediction_confidence.json.prefix-contaminated`.

### Tests

`scripts/training/test_predict_validate.py` — 13 cases, all hermetic (deterministic stubbed embeddings, temp store, no Ollama):

```
PASS test_uncorroborated_prediction_is_not_a_win
PASS test_antecedent_fact_does_not_confirm_the_prediction
PASS test_a_later_fact_does_confirm_the_prediction
PASS test_a_later_prediction_does_not_confirm_an_earlier_one
PASS test_a_prediction_is_scored_at_most_once
PASS test_recent_prediction_is_skipped_not_counted
PASS test_recall_exclude_keeps_an_edge_out_of_its_own_results
PASS test_recall_exclude_only_drops_the_named_edge
PASS test_predict_world_does_not_predict_from_a_prediction
PASS test_predict_world_picks_a_fact_not_the_last_edge
PASS test_predict_world_refuses_when_effect_is_empty
RESULT: 13/13 passed
```

Both regressions are pinned to the *old* behaviour: I stashed the fix and re-ran — old code returns `"correct"` for a prediction whose only match is itself, new code returns `"unverified"`. A test that cannot fail on the broken code is not a test.

`run_tests.sh scripts/training/` → **114 passed, 0 failed**.

**Honest limit:** temporal ordering here relies on the edge timestamps being sane, and the store has 272 facts against only 32 predictions from 5 generators — so 12/32 is a small sample and the accuracy number will move. It is now a measurement instead of a constant, which is the whole point.

If you keep any self-check that searches the same store it writes to: the cheap audit is to ask what it returns when the *only* thing it could match is itself. If the answer is "success", you have a check, not a verification.
