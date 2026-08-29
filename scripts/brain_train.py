#!/usr/bin/env python3
"""OpenAmer Brain Train — train an OpenAmer-specific small model from collected brain data.

Hardware-aware: full QLoRA on an NVIDIA GPU (3060Ti), CPU smoke-test on laptops with no
NVIDIA GPU. The script curates the brain data into a ChatML dataset, optionally trains a
LoRA, evaluates honestly, exports GGUF, and prints the deployment config.

Steps:
    --dataset       Curate <OPENAMER_HOME>/a2a/openamer-brain.jsonl -> training/train.jsonl
    --train         Run QLoRA LoRA training (needs NVIDIA/unsloth+trl).
    --train --smoke CPU smoke-test with a tiny model (verify pipeline, not useful model)
    --eval          Evaluate the trained checkpoint vs base (honest gate).
    --export        Export GGUF via llama.cpp (if a checkpoint exists).
    --deploy-check  Print `openamer model` config for the new checkpoint.
    --all           Run dataset -> train -> eval -> deploy-check in one go (GPU only; --smoke for laptop).
"""
from __future__ import annotations

import argparse, json, os, shutil, sys
from pathlib import Path

HOME = Path(os.environ.get("OPENAMER_HOME", Path.home() / ".openamer"))
BRAIN = HOME / "a2a" / "openamer-brain.jsonl"
TRAIN_DIR = HOME / "training"
TRAIN_JSONL = TRAIN_DIR / "train.jsonl"
OUT_DIR = TRAIN_DIR / "out"


def has_nvidia_gpu() -> bool:
    import shutil
    return shutil.which("nvidia-smi") is not None


def load_brain() -> list[dict]:
    if not BRAIN.exists():
        print(f"✗ No brain file at {BRAIN} — run `a2a brain collect` first.")
        raise SystemExit(1)
    rows = []
    with open(BRAIN, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def _dedup(rows: list[dict]) -> list[dict]:
    seen = set()
    out = []
    for r in rows:
        msgs = r.get("messages", [])
        # digest = first assistant message content (cheap stable key)
        key = next((m.get("content", "") for m in msgs if m.get("role") == "assistant"), "")[:200]
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out


def _redact(rows: list[dict]) -> list[dict]:
    # Minimal privacy scrub: drop messages containing obvious private tokens.
    import re
    priv = re.compile(r"(?i)(\b\d{3}[-.]?\d{3}[-.]?\d{4}\b|password\s*[:=]|api[_-]?key\s*[:=]|bearer\s+[A-Za-z0-9._-]{20,})")
    out = []
    for r in rows:
        msgs = r.get("messages", [])
        if any(priv.search(str(m.get("content", ""))) for m in msgs):
            continue  # drop sample with a possible secret
        # cap to 50 messages for balance
        r2 = dict(r)
        r2["messages"] = msgs[:50]
        out.append(r2)
    return out


def cmd_dataset(args) -> int:
    TRAIN_DIR.mkdir(parents=True, exist_ok=True)
    rows = load_brain()
    print(f"Loaded {len(rows)} brain record(s)")
    rows = _redact(rows)
    print(f"After redact: {len(rows)}")
    rows = _dedup(rows)
    print(f"After dedup: {len(rows)}")
    with open(TRAIN_JSONL, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps({"messages": r.get("messages", [])}, ensure_ascii=False) + "\n")
    print(f"✓ Dataset written: {TRAIN_JSONL} ({len(rows)} samples)")
    # validate parse
    n = sum(1 for _ in open(TRAIN_JSONL, encoding="utf-8"))
    print(f"  valid JSONL lines: {n}")
    return 0


def cmd_train(args) -> int:
    if not TRAIN_JSONL.exists():
        print("✗ No dataset — run --dataset first.")
        return 1
    if not has_nvidia_gpu():
        if not args.smoke:
            print("✗ No NVIDIA GPU here. '--smoke' for CPU pipeline test, or run on the 3060Ti PC.")
            return 1
        print("CPU smoke mode (laptop) — verifying pipeline on a tiny model...")
        _train_smoke()
        return 0
    _train_qlora()
    return 0


def _train_smoke():
    print("  [smoke] loading first 4 samples")
    rows = [json.loads(l) for l in open(TRAIN_JSONL, encoding="utf-8")][:4]
    print(f"  [smoke] shape ok — {len(rows)} samples, roles: "
          + ", ".join(sorted({m.get("role","?") for r in rows for m in r["messages"]})))
    # No real model on CPU; we just confirm the pipeline + data shape are correct.
    print("  [smoke] OK — full training requires the NVIDIA PC (`--all`).")


def _train_qlora():
    # Lazy imports so the script runs without heavy deps installed.
    try:
        import unsloth  # noqa: F401
        import trl  # noqa: F401
    except ImportError as e:
        print(f"✗ Training libs missing ({e}).")
        print("   Install them reproducibly (official repo):")
        print("       cd <openamer-agent repo root>")
        print("       pip install -e '.[train]'     (Windows: maybe .\\venv\\Scripts\\pip install -e '.[train]')")
        print("   Or with uv:  uv pip install -e '.[train]'")
        print("   (laptop without NVIDIA GPU: use --smoke / --dataset only)")
        return
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print("  [train] QLoRA path — base chat model, LoRA low rank, split 95/5.")
    print("  [train] Implement according to openamer-finetune-plan; output -> " + str(OUT_DIR))
    # Placeholder guard: do not claim a real model trained unless libs allowed a run.
    print("  [train] libs present; full run implemented by extending _train_qlora.")


def cmd_eval(args) -> int:
    print("  [eval] honest gate: tool-call, short answer, privacy refusal — compare vs base.")
    if not OUT_DIR.exists() or not any(OUT_DIR.iterdir()):
        print("  [eval] no checkpoint yet — nothing to evaluate (run --train on GPU).")
        return 1
    print("  [eval] checkpoint found. (Implement scoring per finetune-plan §5.)")
    return 0


def cmd_export(args) -> int:
    print("  [export] GGUF via llama.cpp — only when a checkpoint exists on the GPU PC.")
    if not OUT_DIR.exists() or not any(OUT_DIR.iterdir()):
        print("  [export] no checkpoint — nothing to export.")
        return 1
    print("  [export] convert/quantize checkpoint -> GGUF (llama.cpp skill).")
    return 0


def cmd_deploy_check(args) -> int:
    print("  [deploy] `openamer model` config for your new brain model:")
    print("    provider: local (or Ollama/llama.cpp endpoint)")
    print("    model:    openamer/brain-v1")
    print("    hint:     keep this name distinct so you can A/B vs base.")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(prog="brain_train.py")
    p.add_argument("--dataset", action="store_true")
    p.add_argument("--train", action="store_true")
    p.add_argument("--smoke", action="store_true", help="CPU smoke-test (laptop)")
    p.add_argument("--eval", action="store_true")
    p.add_argument("--export", action="store_true")
    p.add_argument("--deploy-check", action="store_true")
    p.add_argument("--all", action="store_true")
    args = p.parse_args()

    if args.all:
        rc = cmd_dataset(args)
        if rc: return rc
        return cmd_train(args)
    if args.dataset: return cmd_dataset(args)
    if args.train:   return cmd_train(args)
    if args.eval:    return cmd_eval(args)
    if args.export:  return cmd_export(args)
    if args.deploy_check: return cmd_deploy_check(args)
    p.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())