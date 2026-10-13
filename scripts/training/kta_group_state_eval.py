#!/usr/bin/env python3
"""KTA -> Architecture experiment: GROUP-STATE generalization on Z_K (rotor snap).

Closes the knowledge->action loop with a MEASUREMENT instead of a log line.

The stored artifact group_state_z10.json was trained on lengths 1-7. The
hypothesis under test (the same one recorded for Z_K in the self-model):
the structural readout (tau <= 0.1) is exact for the Z_10 rotor snap out to
L = 2048 -- i.e. accuracy at UNSEEN lengths stays 1.000.

This script rebuilds the SAVED model from disk (no retraining), evaluates at
fresh unseen lengths, and writes the measured curve to group_state_z10_eval.json.
"""
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPTS = HERE.parent          # scripts/ holds group_state_engine + group_scaling_lab
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(HERE))

from group_state_engine import load, model_path, DEFAULT_DIR          # noqa: E402
from group_scaling_lab import task, accuracy, build_group, GroupState  # noqa: E402

GROUP = "Z10"
LENGTHS = [8, 16, 32, 64, 128, 256, 512, 1024, 2048]
N_PER_LENGTH = 200


def main():
    path = model_path(GROUP)
    if not os.path.exists(path):
        print(json.dumps({"ok": False, "error": f"no model at {path}"}))
        return 1
    t0 = time.time()
    model, group, payload = load(path)
    print(f"[eval] loaded {os.path.basename(path)} |G|={group.order} "
          f"params={payload['stats']['params']} tau={payload['tau']}")

    curve = {}
    for L in LENGTHS:
        try:
            a = accuracy(model, group, L, n=N_PER_LENGTH, seed=1234 + L)
        except Exception as e:  # noqa: BLE001
            curve[str(L)] = {"acc": None, "error": f"{type(e).__name__}: {e}"}
            continue
        curve[str(L)] = {"acc": round(a, 4), "n": N_PER_LENGTH}
        print(f"  L={L:>5}  acc={a:.4f}")

    vals = [v["acc"] for v in curve.values() if v.get("acc") is not None]
    passed = [int(k) for k, v in curve.items()
              if v.get("acc") is not None and v["acc"] >= 1.0]
    res = {
        "experiment": "group_state_generalization_zk",
        "group": group.order,
        "params": payload["stats"]["params"],
        "tau": payload["tau"],
        "trained_on": payload["stats"].get("trained_on"),
        "eval_lengths": LENGTHS,
        "n_per_length": N_PER_LENGTH,
        "curve": curve,
        "min_acc": round(min(vals), 4) if vals else None,
        "exact_lengths": passed,
        "exact_out_to": max(passed) if passed else None,
        "secs": round(time.time() - t0, 2),
    }
    out = os.path.join(DEFAULT_DIR, "group_state_z10_eval.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(res, f, indent=1)
    print(json.dumps({k: res[k] for k in
                      ("experiment", "group", "params", "tau", "min_acc",
                       "exact_out_to", "secs")}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
