---
title: openamer-brain-train
description: "Train your OWN OpenAmer-specific small model from the collected brain data — dataset, QLoRA, eval, export. Works on any install; QLoRA needs an NVIDIA GPU."
---

# OpenAmer Brain Train — how to train your own model

> "The organism becomes its own brain." OpenAmer accumulates brain data from your usage,
> and **you can train your own small, specialized model tuned for OpenAmer** (tool-calling,
> concise output, your style and privacy defaults).

This feature is available to **every OpenAmer user** — it ships in the official repo and just
needs to be enabled. On a laptop without an NVIDIA GPU you **verify** the pipeline; the real
model training (QLoRA) needs a GPU with enough VRAM (e.g. RTX 3060 Ti 8 GB → 7B).

---

## Prerequisites (one-time)

1. OpenAmer installed from GitHub (git clone + pip install).
2. Brain data collected (`openamer a2a brain collect`), or you already have
   `~/.openamer/a2a/openamer-brain.jsonl` from your usage.
3. **For real training:** a machine with an NVIDIA GPU (unsloth picks CUDA automatically).
   Laptop without GPU → use `--smoke` to check the pipeline only.

## Install the training libraries (reproducible)

```bash
# in the openamer-agent repo root:
pip install -e '.[train]'
# or with uv:
uv pip install -e '.[train]'
```

This installs `unsloth`, `trl`, `peft`, `datasets`, `accelerate` — everything training needs.
If you have no GPU / do not intend to train, you can skip it (use only `--dataset` / `--smoke`).

## The pipeline (step by step)

### 1. Curate the brain data → `--dataset`
```bash
OPENAMER_HOME="<your home>" python scripts/brain_train.py --dataset
```
- Reads `<home>/a2a/openamer-brain.jsonl` (the collected sessions).
- Strips secrets (privacy redact), dedupes, balances (max ~50 messages/sample).
- Writes a clean ChatML dataset to `<home>/training/train.jsonl`.

### 2. Train the model → `--train`
```bash
python scripts/brain_train.py --train         # full QLoRA (NVIDIA GPU)
python scripts/brain_train.py --train --smoke   # CPU smoke-test (laptop, no real model)
```
- **NVIDIA path:** base = strong chat model, low-rank LoRA, 95/5 split. Output in `<home>/training/out/`.
- **Laptop path:** `--smoke` only checks the data/pipeline with a few samples (exit 0 = ok), no usable model.

### 3. Evaluate honestly → `--eval`
```bash
python scripts/brain_train.py --eval
```
- Checks tool-call correctness, short answers, privacy refusal; compares against the base model.
- **Do not deploy unless clearly better** (curation > volume).

### 4. Export + deploy → `--export` / `--deploy-check`
```bash
python scripts/brain_train.py --export
python scripts/brain_train.py --deploy-check
```
- Exports GGUF (via llama.cpp) for local inference.
- `deploy-check` shows the `openamer model` config (e.g. `openamer/brain-v1`) for A/B against the base.

### Everything in one go (on the GPU machine)
```bash
python scripts/brain_train.py --all
```

## Honest notes / limits

- **Real 7B training needs an NVIDIA GPU** — there is no "zero-GPU trick". Without GPU use `--smoke`,
  but you still get your curated dataset for later.
- **Curation > volume**: 10k clean, tool-rich samples > 1M dumps. Fewer, but clean.
- **Privacy first**: the `--dataset` step redacts secrets, but re-verify before any public sharing
  (`openamer security check`).
- No promise of "superintelligence overnight" — this is an incremental, honest pipeline.

## Verify (on this machine)

```bash
OPENAMER_HOME="<your home>" python scripts/brain_train.py --dataset
python scripts/brain_train.py --train --smoke
```
Both exit 0 = pipeline ok → then run `--all` on the GPU machine.

See also: `skills/autonomous-ai-agents/openamer-brain-train` (skill) and
`docs/wiki/autonomous-ai-agents/openamer-finetune-plan` (design/plan).