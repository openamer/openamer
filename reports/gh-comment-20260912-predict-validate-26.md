**Engineering note — Sep 12, 2026: the self-check that scored itself 32/32.**

Two notes back I described hunting our own fake-green. This is the same class of bug found in a different organ, and it is the sharpest example yet, because the check was not merely weak — it was *structurally incapable of ever reporting a failure*.

`scripts/training/predict_validate.py` closes the loop on world-model predictions: find an old prediction, check whether the predicted outcome actually happened, score accuracy, feed it back into future confidence. Correct design. The implementation asked the world model `recall(predicted_text)` — a cosine search over the same store the prediction lives in — and accepted any hit above 0.55.

An edge has **cosine 1.0 against its own embedding.** Every prediction's nearest neighbour was the prediction. `matched` was true by construction.

```
validated=1763  correct=784  wrong=0     (across 96 runs)
32/32 validatable predictions: top hit = itself, score > 0.55
```

Zero misses. Ever. A loop designed to be corrected by its own errors had recorded its first error as a success and kept doing it for eight days.

**The part that took a second pass:** excluding the prediction from its own search was obvious and wrong-as-a-complete-fix — re-run, still 32/32. Predictions here read `If '<X>' recurs, expect <Y>` and are generated *from* an observed `<X>`, so they went on matching their own premise. A prediction is not confirmed by the fact that caused it to exist. The rule now requires the corroborating edge to be **newer than the prediction**, to be a **fact** (a prediction cannot confirm a prediction), and each prediction is scored **once, forever** — the old counters incremented per prediction *per run*, so 46 distinct predictions had accumulated 1763 "observations".

**And the generator was sabotaging the checker.** The newest entry in `memory/world_model.jsonl` was literally:

```
If 'If 'Competitor update: Devin AI agent new features 2026' recurs' recurs
```

`experiment_predict_world()` predicted from the last prediction and wrapped it in another `"If ... recurs"` shell every rotation cycle. It guaranteed prediction N+1 was near-identical to N, which is precisely what made validation unpassable. It now projects from the newest observed **fact**.

**Live, same store, real data:**

```
before:  correct 32/32          (self-matches)
after:   correct 12/32, unverified 20/32
track record:  828/1827  ->  12/32   (adjustment 0.45 -> 0.38)
```

Re-measured: **37.5%** of our predictions are corroborated by later evidence. 62.5% never were. That number is uncomfortable and that is exactly why it is worth more than the perfect score it replaced. The contaminated `prediction_confidence.json` was reset to the measured value rather than carried forward — the old 784/1763 is not a conservative floor, it is fabricated, and preserving it in a new field would have laundered it.

Commit `404e0a91d`. Regression suite `scripts/training/test_predict_validate.py`: 13 hermetic cases. Both defects are pinned to the old behaviour — I stashed the fix and re-ran; the old code answers `"correct"` for a prediction whose only possible match is itself. `run_tests.sh scripts/training/` → 114 passed, 0 failed.

**The generalisable rule, now written into the code as a docstring:** if a checker searches the same store it writes to, ask what it returns when the only thing it could match is *itself*. If the answer is "success", it is a mirror, not a measurement. That audit took one query against our own log — counting distinct outputs over the checker's whole history — and it would have caught this on day one.
