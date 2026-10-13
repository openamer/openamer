---
title: tao-train-single-step
description: Standard single-step train/eval/export workflow for any TAO model. Use when training a TAO model on a dataset without it
---

# tao-train-single-step

**Description:** Standard single-step train/eval/export workflow for any TAO model. Use when training a TAO model on a dataset without iterative data augmentation, AutoML, or DEFT loops. Trigger phrases include "single train run", "train then evaluate then export", "plain TAO training", "normal training", "no AutoML", "skip the loop". Routes through the per-model SKILL.md for action specifics and through `tao-launch-workflow` for platform/credentials/dataset intake.
**Lines:** 86 | **Code:** 0 | **Dir:** `tao-train-single-step`

---

---
name: tao-train-single-step
description: Standard single-step train/eval/export workflow for any TAO model. Use when training a TAO model on a dataset
  without iterative data augmentation, AutoML...