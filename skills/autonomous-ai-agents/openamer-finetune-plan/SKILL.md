---
name: openamer-finetune-plan
description: "Plan and prepare an OpenAmer-specific fine-tune from the collected brain data: data curation, ChatML JSONL, training, evaluation. 'The organism becomes its own brain'."
version: 1.0.0
author: OpenAmer
license: Apache-2.0
platforms: [linux, macos, windows]
metadata:
  openamer:
    tags: [finetune, training, llm, dataset, brain, superintelligence, openamer-model]
    homepage: https://github.com/openamer/openamer
    related_skills: [a2a-swarm, openamer-agent, huggingface-hub, llama-cpp]
---

# OpenAmer Fine-Tune Plan (the organism learns its own brain)

A step-by-step, honest plan to go from **collected activity data** → **a curated
dataset** → **an OpenAmer-specific model replica**. Do NOT promise "superintelligence
in a day"; this is a real but incremental pipeline.

## When to use
- You've accumulated enough `~/.openamer/a2a/*.jsonl` (activity/trajectories) and
  mesh insights that a specialist model would generalize.
- You want a "distilled OpenAmer brain" that encodes the swarm's learned skills
  and style (tool-calling, concise output, privacy-first defaults).

## The pipeline (data → curated → train → evaluate → deploy)

### 1. Collect (already built)
Every node already logs activity:
```
~/.openamer/a2a/activity.jsonl        # brainlog (autolog ON by default)
~/.openamer/a2a/openamer-brain.jsonl  # `a2a brain collect` output (ChatML)
~/.openamer/MEMORY-official-mesh.md   # adopted mesh insights
```
Aggregate across nodes (scp/rsync or the GitHub `directory/a2a/` for shared
curated insights). **Only ever train on redacted data** (privacy.redact runs at
write time; re-verify before training).

### 2. Curate (klein aber fein)
- De-dupe by `digest()` (already in `braindata`).
- Drop secrets and near-duplicate tool logs (keep structure, drop PII).
- Balance: prefer turns with tool calls + thinking + final answer; cap at
  ~50 messages per sample.

### 3. Prepare ChatML / messages format
Already produced by `brain collect`: JSONL `{"messages":[...,"engine":...]}`
with `system/user/thinking/tool/assistant` roles. Perfect for:
- **Supervised fine-tune (SFT)** with standard tool-call templates, or
- **LoRA/QLoRA** on limited VRAM (your RTX 3060 Ti 8GB fits a 7B-ish with QLoRA).

Tools (already in OpenAmer skills/ecosystem): `huggingface-hub` skill, `llama-cpp`
skill for GGUF inference. Use libraries like `trl`, `peft`, `unsloth`/`torchtune`,
or `mlx` (Apple).

### 4. Train
- Split train/valid (~95/5). Evaluate on a held-out set of *hoped-for* tasks
  (tool use, short answers, refusal of private-data prompts).
- Start from a strong base (e.g. a capable chat model) to avoid forgetting
  general ability; LoRA on the collected data only.
- Metrics: loss on validation + a small human-read gold set.

### 5. Evaluate honestly
- Test on: tool-call correctness, privacy refusal (must never echo a phone), and
  its own system-prompt knowledge.
- Compare vs base model. If it's not clearly better on the target slice, don't
  ship it — keep the base.

### 6. Deploy
- Export GGUF (llama.cpp skill) for local; or the standard checkpoint.
- `openamer model` points to the new endpoint/file. Keep the model name distinct
  (e.g. `openamer/...brain-v1`).

## Pitfalls
- **Data hygiene first.** One leaked private string poisons trust. Run
  `openamer_cli.a2a.privacy.redact` + scan before training.
- **Curation > volume.** 10k clean, tool-rich samples beat 1M dumps.
- **Don't overfit the swarm's niche** — you'll lose general usefulness. LoRA, low
  rank, modest epochs.
- **Neither promise instant superintelligence** — this is incremental; each
  version generalizes cheaply if the base is strong.

## Verify
```bash
openamer a2a brain collect --out brain.jsonl    # dataset exists, JSONL valid
python -c "import json; [json.loads(l) for l in open('brain.jsonl')]"  # all parse
openamer security check                          # privacy posture before publishing
```