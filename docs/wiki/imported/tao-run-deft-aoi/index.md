---
title: tao-run-deft-aoi
description: Run the full DEFT AOI improvement loop for NVIDIA TAO VisualChangeNet / ChangeNet PCB inspection models: baseline evalua
---

# tao-run-deft-aoi

**Description:** Run the full DEFT AOI improvement loop for NVIDIA TAO VisualChangeNet / ChangeNet PCB inspection models: baseline evaluate, RCA, Cosmos AnomalyGen / AMP synthetic defects, k-NN mining, retraining, and deployment gating until FAR / recall KPI targets are met. Use for prompts like "run the DEFT loop", "fine-tune until FAR below 0.1% at recall=100%", or "improve my AOI ChangeNet model with RCA and synthetic defects"; do not use for standalone TAO training, one-off inference, generic anomaly generation, or RCA-only analysis.

**Lines:** 156 | **Code:** 5 | **Dir:** `tao-run-deft-aoi`

---

---
name: tao-run-deft-aoi
description: >
  Run the full DEFT AOI improvement loop for NVIDIA TAO VisualChangeNet / ChangeNet PCB inspection models:
  baseline evaluate, RCA, Cosmos AnomalyGen / AMP s...