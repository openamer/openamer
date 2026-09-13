#!/usr/bin/env python3
"""calibration.py - epistemic self-honesty: can this system be WRONG, and does it know?

Gap this fills: an audit of our own code found ZERO files implementing
calibration (while causal/prediction/analogy/self_model were all "REAL"). The
system could forecast, but had no way to ask whether its forecasts were any
good.

It also found the deeper problem, in scripts/training/prediction_validation.jsonl
(123 runs, self-described as "validated"):

    checked 2782 | scored 73 | correct 12 | WRONG 0 | unverified 20
    confidence_state.adjustment = 0.3

Zero wrong. Not "accurate" -- a loop that has never once recorded a failure is
not measuring anything. 97.4% of predictions are never scored at all, and
"unverified" is the room where inconvenient cases wait. An ASI that cannot be
wrong is the dangerous kind, so this tool treats one-sided evidence as a FAILURE
of the measurement, not as good news.

Two faculties, deliberately separated:

  audit   - inspect the existing loop: scored/checked ratio, the falsifiability
            test (has it ever recorded a wrong call?), and whether the records
            even carry a probability (without one, calibration is impossible in
            the strict sense and we say so instead of faking buckets).
  record  - append a (probability, outcome) pair to a real calibration ledger.
  score   - Brier score + reliability buckets from that ledger, and it REFUSES
            to report a bucket with too few samples.

Usage:
  calibration.py audit
  calibration.py record 0.8 1            # predicted 80%, event happened
  calibration.py record 0.2 0            # predicted 20%, event did not happen
  calibration.py score [--json]
Exit codes: 0 ok, 2 unfalsifiable measurement detected (audit), 1 usage.
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

OA_HOME = Path(r"C:\Users\damir\AppData\Local\openamer-laptop")
VALIDATION = OA_HOME / "scripts" / "training" / "prediction_validation.jsonl"
LEDGER = OA_HOME / "memory" / "calibration_ledger.jsonl"
OUT = OA_HOME / "reports" / "calibration.json"

MIN_BUCKET_N = 5          # below this, a bucket is not evidence


def load_validation():
    if not VALIDATION.exists():
        return []
    rows = []
    for line in VALIDATION.read_text(encoding="utf-8", errors="ignore").splitlines():
        if line.strip():
            try:
                rows.append(json.loads(line))
            except Exception:
                pass
    return rows


def audit():
    """Falsifiability test on the EXISTING loop."""
    rows = load_validation()
    if not rows:
        return {"verdict": "FAIL", "reason": "no validation log", "findings": []}

    checked = sum(r.get("predictions_checked") or 0 for r in rows)
    scored = sum(r.get("scored_this_run") or 0 for r in rows)
    conf = (rows[-1].get("confidence_state") or {})
    correct = conf.get("correct")
    wrong = conf.get("wrong")
    unverified = conf.get("unverified")

    findings, verdict = [], "OK"

    if checked and scored is not None:
        ratio = 100.0 * scored / checked
        findings.append(f"{checked} predictions checked, only {scored} ever scored "
                        f"({ratio:.1f}%) -- {100 - ratio:.1f}% are never tested.")
        if ratio < 50:
            verdict = "FAIL"
            findings.append("Most predictions are never scored, so the loop's own "
                            "hit rate describes a small, self-selected slice.")

    # THE test: a measurement that cannot fail is not a measurement.
    if isinstance(wrong, int) and isinstance(correct, int):
        n = correct + wrong
        findings.append(f"scored outcomes: correct={correct}, wrong={wrong} "
                        f"(n={n}), unverified={unverified}")
        if n >= 10 and wrong == 0:
            verdict = "FAIL"
            findings.append(
                f"ONE-SIDED EVIDENCE: {n} scored outcomes and ZERO failures. "
                f"Either the predictions are unfalsifiable, or the scoring only "
                f"counts cases that are easy to confirm. Both mean the loop "
                f"cannot detect being wrong.")
        if n < 10:
            verdict = "WARN" if verdict == "OK" else verdict
            findings.append(f"Only {n} scored outcomes -- far too few to support "
                            f"any accuracy claim.")

    # probability present? without p, "calibration" would be theatre
    sample = next((r for r in rows if r.get("results")), None)
    has_p = False
    if sample:
        for item in sample.get("results") or []:
            if isinstance(item, dict) and any(
                    k in item for k in ("probability", "p", "confidence")):
                has_p = True
    adj = conf.get("adjustment")
    if not has_p:
        verdict = "FAIL"
        findings.append(
            "Predictions are recorded as TEXT + outcome with no probability. "
            "Strict calibration (does 80% mean 80%?) is therefore IMPOSSIBLE on "
            "this data. The loop applies a scalar adjustment"
            + (f" ({adj})" if adj is not None else "")
            + " on top of it, which is a guess dressed as a number.")

    return {"verdict": verdict, "checked": checked, "scored": scored,
            "correct": correct, "wrong": wrong, "unverified": unverified,
            "adjustment": adj, "findings": findings}


def record(p, y, note=""):
    """Append a real (probability, outcome) observation.

    p = the probability the system assigned BEFORE the outcome was known.
    y = 1 if the event happened, 0 if it did not.
    A ledger that never receives a y=0 is the failure mode this tool exists to
    prevent, so outcomes are stored verbatim and never smoothed.
    """
    try:
        p = float(p)
    except (TypeError, ValueError):
        print(f"bad probability: {p!r} (expected 0..1)")
        return 1
    if not 0.0 <= p <= 1.0:
        print(f"probability out of range: {p} (expected 0..1) -- clamping refused, "
              f"an out-of-range probability is a bug upstream")
        return 1
    y = 1 if str(y).strip() in ("1", "true", "yes", "y") else 0
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with LEDGER.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                            "p": p, "y": y, "note": note}, ensure_ascii=False) + chr(10))
    print(f"recorded p={p} y={y}" + (f"  ({note})" if note else ""))
    return 0


def load_ledger():
    if not LEDGER.exists():
        return []
    out = []
    for line in LEDGER.read_text(encoding="utf-8", errors="ignore").splitlines():
        if line.strip():
            try:
                r = json.loads(line)
                out.append((float(r["p"]), int(r["y"]), r.get("at", "")))
            except Exception:
                pass
    return out


def score():
    """Brier score + reliability buckets. Refuses to invent calibration.

    Brier = mean((p - y)^2). 0.25 is the score of always saying 50%; a model
    that cannot beat 0.25 is not informative, whatever its story.
    """
    rows = load_ledger()
    res = {"n": len(rows), "buckets": [], "brier": None, "baseline_brier": 0.25,
           "verdict": "OK", "findings": []}
    if not rows:
        res["verdict"] = "WARN"
        res["findings"].append(
            "calibration ledger is EMPTY. Nothing about this system's confidence "
            "is currently measured -- record (probability, outcome) pairs to fix "
            "that. An empty honesty ledger is not a clean record.")
        return res

    res["brier"] = round(sum((p - y) ** 2 for p, y, _ in rows) / len(rows), 4)
    res["mean_p"] = round(sum(p for p, _, _ in rows) / len(rows), 4)
    res["base_rate"] = round(sum(y for _, y, _ in rows) / len(rows), 4)

    edges = [0, .1, .2, .3, .4, .5, .6, .7, .8, .9, 1.0001]
    for i in range(len(edges) - 1):
        lo, hi = edges[i], edges[i + 1]
        sel = [(p, y) for p, y, _ in rows if lo <= p < hi]
        if not sel:
            continue
        b = {"range": f"{lo:.1f}-{min(hi, 1.0):.1f}", "n": len(sel),
             "mean_p": round(sum(p for p, _ in sel) / len(sel), 3),
             "observed": round(sum(y for _, y in sel) / len(sel), 3)}
        b["gap"] = round(b["mean_p"] - b["observed"], 3)
        b["reportable"] = len(sel) >= MIN_BUCKET_N
        res["buckets"].append(b)

    thin = [b for b in res["buckets"] if not b["reportable"]]
    if thin:
        res["findings"].append(
            f"{len(thin)} of {len(res['buckets'])} bucket(s) have n<{MIN_BUCKET_N} "
            f"and are marked reportable=false -- they are not evidence and must "
            f"not be quoted as calibration.")
    if res["brier"] > 0.25:
        res["verdict"] = "FAIL"
        res["findings"].append(
            f"Brier {res['brier']} is WORSE than always saying 50% (0.25). The "
            f"confidence signal is actively harmful.")
    elif res["brier"] > 0.20:
        res["verdict"] = "WARN"
        res["findings"].append(f"Brier {res['brier']} is barely informative.")
    else:
        res["findings"].append(f"Brier {res['brier']} beats the 0.25 baseline.")
    if res["base_rate"] in (0.0, 1.0):
        res["verdict"] = "FAIL"
        res["findings"].append(
            f"all outcomes are {res['base_rate']} -- the ledger cannot distinguish "
            f"a calibrated model from a constant. Record outcomes that go BOTH ways.")
    return res


def main(argv):
    cmd = argv[0] if argv else "audit"
    if cmd == "audit":
        a = audit()
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps({"at": datetime.now(timezone.utc).isoformat(
            timespec="seconds"), "audit": a, "ledger": score()},
            indent=2, ensure_ascii=False), encoding="utf-8")
        print("CALIBRATION AUDIT - can this system be wrong, and does it know?")
        print("=" * 72)
        print(f"VERDICT: {a['verdict']}")
        for f in a["findings"]:
            print(f"  - {f}")
        s = score()
        print(f"\nledger: n={s['n']}  brier={s['brier']}"
              + (f"  (baseline 0.25)" if s["brier"] is not None else ""))
        for f in s["findings"]:
            print(f"  - {f}")
        print("=" * 72)
        return 2 if a["verdict"] == "FAIL" else (1 if a["verdict"] == "WARN" else 0)
    if cmd == "record":
        if len(argv) < 3:
            print("usage: calibration.py record <probability> <0|1> [note]")
            return 1
        return record(argv[1], argv[2], " ".join(argv[3:]))
    if cmd == "score":
        s = score()
        if "--json" in argv:
            print(json.dumps(s, indent=2, ensure_ascii=False))
        else:
            print(f"CALIBRATION LEDGER  n={s['n']}  brier={s['brier']}  "
                  f"(always-50% = 0.25)  base_rate={s.get('base_rate')}")
            print(f"{'bucket':<10} {'n':>4} {'said':>6} {'happened':>9} {'gap':>7}  reportable")
            print("-" * 62)
            for b in s["buckets"]:
                print(f"{b['range']:<10} {b['n']:>4} {b['mean_p']:>6} "
                      f"{b['observed']:>9} {b['gap']:>7}  {b['reportable']}")
            for f in s["findings"]:
                print(f"  - {f}")
        return 0 if s["verdict"] == "OK" else (2 if s["verdict"] == "FAIL" else 1)
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
