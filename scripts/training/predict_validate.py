#!/usr/bin/env python3
"""Prediction Validator — closes the loop on world-model predictions.

Predictions without validation are dangerous (adversarial drift).
This script:
  1. Finds old predictions in the world model
  2. Checks if the predicted outcome actually happened (search memory/logs)
  3. Scores accuracy → feeds back into confidence for future predictions
  4. Prunes bad predictors, boosts good ones

This is ERROR-CORRECTION for the world model — the difference between
a GEIST and a HALLUZINATION.
"""
import os
import json, os, sys, datetime, re
from pathlib import Path

T = os.path.join(os.environ.get("OPENAMER_HOME", str(Path.home() / "AppData" / "Local" / "openamer")), "scripts", "training")
WM = os.path.join(os.environ.get("OPENAMER_HOME", str(Path.home() / "AppData" / "Local" / "openamer")), "memory", "world_model.jsonl")
VALID_LOG = os.path.join(T, "prediction_validation.jsonl")
CONFIDENCE_FILE = os.path.join(T, "prediction_confidence.json")
# One score per prediction, forever. Without this the same edge was re-scored
# on every run (46 distinct predictions -> 1763 "validated" observations).
SCORED_FILE = os.path.join(T, "prediction_scored.json")

def load_json(path, default):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return default

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1)

def validate_predictions():
    """Check old predictions against actual outcomes.

    HONESTY CONTRACT (fixed 12.09.2026). This function used to find the
    prediction itself as its own nearest neighbour (an edge has cosine 1.0
    against its own embedding), so every prediction scored "correct" and the
    loop could never record a miss. Measured live before the fix:

      - confidence file: validated=1763, correct=784, wrong=0
      - every logged run: 100% "correct", zero "unverified" for the newest rows
      - direct check: 32/32 validatable predictions had THEMSELVES as the
        top hit with score > 0.55

    It also incremented the counters once per prediction PER RUN, so 46
    distinct predictions accumulated 1763 "validated" observations — the
    track record inflated with repetition, not evidence.

    Now: the prediction under test is EXCLUDED from its own search (via
    wm.recall(..., exclude={key})), each prediction is scored at most once,
    and anything that cannot be corroborated by independent evidence is
    recorded as "unverified" — not silently counted as a win.
    """
    if not os.path.exists(WM):
        return {"error": "no world model"}
    lines = open(WM, encoding="utf-8").readlines()

    predictions = []
    facts = []
    for line in lines:
        try:
            d = json.loads(line)
            # world_model.py writes "kind": "prediction"; older edges used
            # "type": "prediction". Accept both so no prediction is missed.
            if d.get("kind") == "prediction" or d.get("type") == "prediction":
                predictions.append(d)
            elif "cause" in d:
                # keep the whole edge: the timestamp decides whether it can
                # serve as evidence (only a LATER edge can confirm a prediction)
                facts.append(d)
        except Exception:
            continue

    if not predictions:
        return {"status": "no predictions to validate"}

    conf = load_json(CONFIDENCE_FILE, {"validated": 0, "correct": 0,
                                       "wrong": 0, "adjustment": 1.0})

    # A consequence the store itself uses as a stock phrase is not a claim.
    # Measured 2026-10-31: 161 of 243 predictions "matched" only because their
    # effect text is the literal "Needs investigation and root-cause fix",
    # which hundreds of facts also carry as their effect.  Matching that string
    # says nothing about the world — the predictor and the store share one
    # template, so the template confirms itself.  A prediction whose
    # consequence is a stock phrase is recorded as UNMEASURABLE, never as a win.
    from collections import Counter as _Counter
    _effect_counts = _Counter((f.get("effect") or "").strip().lower() for f in facts)
    _template_cutoff = max(5, len(facts) // 50)

    def _is_stock_phrase(cons):
        # Only frequency decides.  A short but specific consequence ("writes
        # fail") is a real claim; the test suite pins that.
        return not cons or _effect_counts.get(cons, 0) >= _template_cutoff

    # Only score a given prediction once across the whole history — otherwise
    # the same edge is re-"validated" every run and inflates the track record.
    scored = load_json(SCORED_FILE, {})
    results = []

    for pred in predictions:
        # New world_model.py predictions store cause/effect; older ones used
        # a single "predicted" field. Reconstruct the text from either shape.
        predicted_text = pred.get("predicted", "").lower()
        if not predicted_text:
            predicted_text = (f"{pred.get('cause','')} {pred.get('effect','')}").lower()
        pred_ts = pred.get("ts", "")
        confidence = pred.get("confidence", 0.5)

        key = f"{pred_ts}|{pred.get('cause','')[:120]}"
        if key in scored:          # already scored in an earlier run
            continue

        # skip very recent predictions (not enough time to verify)
        try:
            pred_age = (datetime.datetime.now() -
                        datetime.datetime.fromisoformat(pred_ts)).total_seconds()
        except Exception:
            continue
        if pred_age < 3600:  # less than 1 hour old
            continue

        # check: did the predicted pattern appear in world-model facts?
        # Semantic matching via embeddings (substring matching was blind to
        # paraphrases: "disk full" never matched "Speicherplatz erschöpft").
        # CRITICAL: exclude (a) the prediction itself and (b) every edge that
        # is not NEWER than the prediction. A prediction reads
        # "If '<X>' recurs, expect <Y>" and is generated FROM an observed
        # <X>. Matching that same <X> back is tautological: the antecedent
        # that produced the prediction is not evidence that it came true.
        # Real corroboration = an <X> edge observed AFTER the prediction was
        # written. Measured live: with self-exclusion but no temporal rule,
        # 32/32 predictions still "matched" — every one of them against the
        # premise edge they had been derived from.
        matched = False
        try:
            import world_model as wm
            hits = wm.recall(predicted_text[:300], k=5, exclude={key})
            for h in hits or []:
                if h.get("score", 0) <= 0.55:
                    continue
                if h.get("key") == key:
                    continue
                if h.get("kind") != "fact":
                    continue            # a prediction cannot confirm a prediction
                if (h.get("ts") or "") <= pred_ts:
                    continue            # antecedent, not consequence
                matched = True
                break
            # fallback to substring when semantic search finds nothing
            if not matched:
                # The CONSEQUENCE must show up — not the antecedent.  Until
                # 2026-10-31 this compared `ftext[:80] in predicted_text`, so a
                # later fact starting with the same trigger ("System error:
                # disk full ...") counted as proof that the predicted outcome
                # happened.  Measured: 6 of the 19 "correct" scores were exactly
                # that — the trigger confirming itself, one layer above the
                # embedding bug this function already fixed in September.
                cons = re.sub(r"^\s*expect:\s*", "",
                              (pred.get("effect") or "").strip().lower())
                ant = (pred.get("cause") or "").strip().lower()
                for f in facts:
                    if (f.get("ts") or "") <= pred_ts:
                        continue        # only subsequent evidence counts
                    ftext = (f.get("cause", "") + " " + f.get("effect", "")).lower()
                    # a fact that merely repeats the trigger is not evidence
                    if ant and (ant[:80] in ftext or ftext[:80] in ant):
                        continue
                    if not cons or len(cons) < 12:
                        continue        # unmeasurable consequence -> stay unverified
                    if cons[:60] in ftext or ftext[:60] in cons:
                        matched = True
                        break
        except Exception:
            for f in facts:
                if (f.get("ts") or "") <= pred_ts:
                    continue
                cons = re.sub(r"^\s*expect:\s*", "",
                              (pred.get("effect") or "").strip().lower())
                ant = (pred.get("cause") or "").strip().lower()
                ftext = (f.get("cause", "") + " " + f.get("effect", "")).lower()
                if ant and (ant[:80] in ftext or ftext[:80] in ant):
                    continue
                if cons and len(cons) >= 12 and (cons[:60] in ftext or ftext[:60] in cons):
                    matched = True
                    break

        # also check learning buffer for related events
        buf_path = os.path.join(T, "online_buffer.jsonl")
        if os.path.exists(buf_path) and not matched:
            for line in open(buf_path, encoding="utf-8").readlines()[-50:]:
                try:
                    d = json.loads(line)
                except Exception:
                    continue
                if predicted_text[:30] in d.get("a", "").lower():
                    matched = True
                    break

        # score: did the prediction hold?  unverified is a real outcome —
        # never counted as a win, and never counted as "validation".
        cons_text = re.sub(r"^\s*expect:\s*", "",
                           (pred.get("effect") or "").strip().lower())
        if _is_stock_phrase(cons_text):
            # Unfalsifiable by construction.  Not a validation, not a win.
            outcome = "unmeasurable"
            conf["unmeasurable"] = conf.get("unmeasurable", 0) + 1
            scored[key] = outcome
            results.append({"predicted": predicted_text[:80], "outcome": outcome})
            continue

        outcome = "correct" if matched else "unverified"
        conf["validated"] += 1
        if matched:
            conf["correct"] += 1
        else:
            # "wrong" means VALIDATED BUT NEVER CORROBORATED.  The legacy
            # template format cannot be contradicted — its consequence is not
            # an observable claim — so there is no separate "contradicted"
            # signal to count.  Reported this way, the number is auditable:
            # correct + wrong == validated, and unmeasurable sits outside both.
            conf["wrong"] = conf.get("wrong", 0) + 1
        scored[key] = outcome

        # adjust future confidence based on track record
        if conf["validated"] >= 5:
            accuracy = conf["correct"] / conf["validated"]
            conf["adjustment"] = round(max(0.3, min(0.9, accuracy)), 2)

        results.append({"predicted": predicted_text[:80], "outcome": outcome})

    save_json(CONFIDENCE_FILE, conf)
    save_json(SCORED_FILE, scored)

    summary = {
        "status": "validated",
        "predictions_checked": len(predictions),
        "scored_this_run": len(results),
        "results": results[-5:],
        "confidence_state": conf,
    }

    with open(VALID_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": datetime.datetime.now().isoformat(), **summary},
                           ensure_ascii=False) + "\n")

    print(f"[predict-validate] {len(predictions)} predictions checked, "
          f"track record: {conf['correct']}/{conf['validated']} correct "
          f"(adjustment: {conf['adjustment']})", flush=True)
    return summary

def apply_confidence_to_new_predictions():
    """New predictions get confidence adjusted by track record."""
    conf = load_json(CONFIDENCE_FILE, {"adjustment": 1.0})
    return conf.get("adjustment", 1.0)

if __name__ == "__main__":
    validate_predictions()
