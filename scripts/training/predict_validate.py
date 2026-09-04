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
import json, os, sys, datetime, re

T = r"C:/Users/damir/AppData/Local/openamer-laptop/scripts/training"
WM = r"C:/Users/damir/AppData/Local/openamer-laptop/memory/world_model.jsonl"
VALID_LOG = os.path.join(T, "prediction_validation.jsonl")
CONFIDENCE_FILE = os.path.join(T, "prediction_confidence.json")

def load_json(path, default):
    try:
        return json.load(open(path, encoding="utf-8"))
    except Exception:
        return default

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1)

def validate_predictions():
    """Check old predictions against actual outcomes."""
    if not os.path.exists(WM):
        return {"error": "no world model"}
    lines = open(WM, encoding="utf-8").readlines()

    predictions = []
    facts = []
    for line in lines:
        try:
            d = json.loads(line)
            if d.get("type") == "prediction":
                predictions.append(d)
            elif "cause" in d:
                facts.append(d.get("cause", "") + " " + d.get("effect", ""))
        except Exception:
            continue

    if not predictions:
        return {"status": "no predictions to validate"}

    conf = load_json(CONFIDENCE_FILE, {"validated": 0, "correct": 0, "wrong": 0, "adjustment": 1.0})
    results = []

    for pred in predictions:
        predicted_text = pred.get("predicted", "").lower()
        pred_ts = pred.get("ts", "")
        confidence = pred.get("confidence", 0.5)

        # skip very recent predictions (not enough time to verify)
        pred_age = (datetime.datetime.now() -
                    datetime.datetime.fromisoformat(pred_ts)).total_seconds()
        if pred_age < 3600:  # less than 1 hour old
            continue

        # check: did the predicted pattern appear in world-model facts?
        matched = False
        for fact in facts:
            if fact.lower()[:80] in predicted_text or predicted_text[:40] in fact.lower():
                matched = True
                break

        # also check learning buffer for related events
        buf_path = os.path.join(T, "online_buffer.jsonl")
        if os.path.exists(buf_path) and not matched:
            for line in open(buf_path, encoding="utf-8")[-50:]:
                d = json.loads(line)
                if predicted_text[:30] in d.get("a", "").lower():
                    matched = True
                    break

        # score: did the prediction hold?
        outcome = "correct" if matched else "unverified"
        conf = load_json(CONFIDENCE_FILE, {"validated": 0, "correct": 0, "wrong": 0, "adjustment": 1.0})
        if matched:
            conf["correct"] += 1
        conf["validated"] += 1

        # adjust future confidence based on track record
        if conf["validated"] >= 5:
            accuracy = conf["correct"] / conf["validated"]
            conf["adjustment"] = round(max(0.3, min(0.9, accuracy)), 2)

        save_json(CONFIDENCE_FILE, conf)
        results.append({"predicted": predicted_text[:80], "outcome": outcome})

    summary = {
        "status": "validated",
        "predictions_checked": len(predictions),
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
