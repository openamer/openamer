#!/usr/bin/env python3
"""Multi-seed confirmation for the Z_K rotor snap (1 seed != a measurement).

Re-evaluates the SAVED group_state_z10.json at large unseen lengths across
several sampling seeds, and reports mean/min/max so a single lucky seed
cannot masquerade as a result.
"""
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPTS = HERE.parent
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(HERE))

from group_state_engine import load, model_path, DEFAULT_DIR   # noqa: E402
from group_scaling_lab import accuracy                          # noqa: E402

SEEDS = [0, 1, 2, 3, 4]
LENGTHS = [512, 1024, 2048]
N = 200


def main():
    model, group, payload = load(model_path("Z10"))
    out = {"experiment": "group_state_zk_multiseed",
           "params": payload["stats"]["params"], "tau": payload["tau"],
           "seeds": SEEDS, "n_per_seed": N, "lengths": {}}
    for L in LENGTHS:
        accs = [round(accuracy(model, group, L, n=N, seed=s), 4) for s in SEEDS]
        out["lengths"][str(L)] = {
            "accs": accs,
            "mean": round(sum(accs) / len(accs), 4),
            "min": min(accs), "max": max(accs)}
        print(f"  L={L:>5} mean={out['lengths'][str(L)]['mean']:.4f} "
              f"min={min(accs):.4f} max={max(accs):.4f}")
    p = os.path.join(DEFAULT_DIR, "group_state_z10_multiseed.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1)
    print(json.dumps(out["lengths"]["2048"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
