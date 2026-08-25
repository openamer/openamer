---
title: tao-finetune-huggingface-model
description: Fine-tune any HuggingFace CV / VLM / LLM model on local NVIDIA GPUs inside an NGC PyTorch container. Use when the user w
---

# tao-finetune-huggingface-model

**Description:** Fine-tune any HuggingFace CV / VLM / LLM model on local NVIDIA GPUs inside an NGC PyTorch container. Use when the user wants to fine-tune a HuggingFace model (full or LoRA), train a vision / VLM / LLM model end-to-end, generate a reproducible HF training pipeline, smoke-test a HuggingFace model locally before scale-up, push a fine-tuned model to the HF Hub with a model card, or emit a self-contained rerun skill for an existing HuggingFace finetune. Supports image classification, object detection, semantic / instance / panoptic segmentation, depth estimation, image-text-to-text VLM (SFT / LoRA), and LLM SFT / DPO / GRPO. Six-step workflow: inspect and qualify, hardware and NGC image, research, generate and smoke, train + eval + infer, push and emit rerun skill.

**Lines:** 373 | **Code:** 3 | **Dir:** `tao-finetune-huggingface-model`

---

---
name: tao-finetune-huggingface-model
description: >
  Fine-tune any HuggingFace CV / VLM / LLM model on local NVIDIA GPUs inside an
  NGC PyTorch container. Use when the user wants to fine-tune a ...