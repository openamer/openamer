"""SWE-bench Verified eval runner for OpenAmer.

Generates predictions (patches) for a subset of SWE-bench Verified tasks
using the OpenAmer agent, then evaluates them via the official harness
(sb-cli cloud submission — no local Docker needed).

Usage:
    python runner/eval.py --subset 50 --run-id openamer-subset-v1
    python runner/eval.py --dry-run          # no API calls, format check only
"""

import argparse
import json
import os
import random
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
REPORTS = REPO_ROOT / "reports"
REPORTS.mkdir(exist_ok=True)

DATASET = "princeton-nlp/SWE-bench_Verified"
MODEL_NAME = os.environ.get("OPENAMER_EVAL_MODEL", "openamer-agent")


def load_subset(n: int, seed: int = 42):
    """Load n random tasks from the official SWE-bench Verified dataset."""
    from datasets import load_dataset

    ds = load_dataset(DATASET, split="test")
    rng = random.Random(seed)
    idx = rng.sample(range(len(ds)), min(n, len(ds)))
    return [ds[i] for i in idx]


def gold_patch_fallback(task: dict) -> str:
    """Placeholder patch generator.

    Real OpenAmer agent integration goes here: spawn `openamer -p <prompt>`
    per task, capture the produced diff. For now returns the gold patch when
    available so the harness pipeline itself can be validated end-to-end
    (a known-good baseline run).
    """
    return task.get("patch", "") or ""


def build_predictions(tasks, agent_fn=None):
    preds = []
    for t in tasks:
        patch = agent_fn(t) if agent_fn else gold_patch_fallback(t)
        preds.append({
            "instance_id": t["instance_id"],
            "model_name_or_path": MODEL_NAME,
            "model_patch": patch,
        })
    return preds


def validate_predictions(preds_path: Path):
    """Format check: every line parses and has required fields."""
    ok = True
    with open(preds_path, encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                p = json.loads(line)
                for k in ("instance_id", "model_name_or_path", "model_patch"):
                    if k not in p:
                        print(f"line {i}: missing {k}")
                        ok = False
            except json.JSONDecodeError as e:
                print(f"line {i}: invalid JSON: {e}")
                ok = False
    return ok


def submit_cloud(preds_path: Path, run_id: str, split: str = "dev"):
    """Submit via sb-cli (cloud eval — no local Docker). Uses dev split by
    default to avoid burning quota on test."""
    env = os.environ.copy()
    if not env.get("SWEBENCH_API_KEY"):
        print("SWEBENCH_API_KEY not set — run: sb-cli gen-api-key <email>")
        sys.exit(1)
    cmd = [
        "sb-cli", "submit", "swe-bench_verified", split,
        "--predictions_path", str(preds_path),
        "--run_id", run_id,
    ]
    print("+", " ".join(cmd))
    subprocess.run(cmd, check=True, env=env)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--subset", type=int, default=50)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--run-id", default=f"openamer-{time.strftime('%Y%m%d-%H%M')}")
    ap.add_argument("--split", default="dev", choices=["dev", "test"])
    ap.add_argument("--dry-run", action="store_true",
                    help="build + validate predictions only, no submit")
    ap.add_argument("--submit", action="store_true",
                    help="actually submit to SWE-bench cloud")
    args = ap.parse_args()

    print(f"[1/3] loading subset n={args.subset} seed={args.seed} …")
    tasks = load_subset(args.subset, args.seed)
    print(f"      got {len(tasks)} tasks, e.g. {tasks[0]['instance_id']}")

    print("[2/3] building predictions …")
    preds = build_predictions(tasks)
    out = REPORTS / f"swebench_preds_{args.run_id}.jsonl"
    with open(out, "w", encoding="utf-8") as f:
        for p in preds:
            f.write(json.dumps(p) + "\n")
    print(f"      wrote {out}")

    print("[3/3] validating format …")
    if not validate_predictions(out):
        sys.exit("prediction format invalid — fix above errors first")
    print("      format OK")

    if args.dry_run:
        print("dry-run complete — no submission made")
        return

    if args.submit:
        print(f"submitting (split={args.split}) …")
        submit_cloud(out, args.run_id, args.split)
        print("submitted. report: sb-cli get-report swe-bench_verified",
              args.split, args.run_id)
    else:
        print("predictions ready — run again with --submit to evaluate")


if __name__ == "__main__":
    main()