---
title: tao-run-automl-deft-pipeline
description: Run the canonical NVIDIA AOI three-phase training pipeline — Phase 1 AutoML baseline (HPO), Phase 2 DEFT loop (RCA → SDG
---

# tao-run-automl-deft-pipeline

**Description:** Run the canonical NVIDIA AOI three-phase training pipeline — Phase 1 AutoML baseline (HPO), Phase 2 DEFT loop (RCA → SDG → mining → plain-train retrain), Phase 3 AutoML refinement on the DEFT-augmented dataset. Use when the user asks to "run the AOI workflow", "fine-tune my PCB AOI model end-to-end", "improve my AOI ChangeNet model", or "AOI workflow with AutoML" request — route here instead of tao-run-deft-aoi directly unless the user explicitly asks for the DEFT loop ONLY (e.g. "run JUST the DEFT loop", "skip AutoML, only DEFT"). Also handles the same three-phase pattern for non-AOI DEFT applications — AutoML baseline then DEFT loop warm-started from AutoML's winning HPs then post-DEFT AutoML refinement on the iteration-augmented dataset. Trigger phrases include "run the AOI workflow", "AOI end-to-end", "AutoML + DEFT", "AutoML then DEFT", "tune hyperparameters then DEFT", "DEFT with AutoML at both ends", "warm-start DEFT", "improve my AOI model".

**Lines:** 201 | **Code:** 14 | **Dir:** `tao-run-automl-deft-pipeline`

---

---
name: tao-run-automl-deft-pipeline
description: >
  Run the canonical NVIDIA AOI three-phase training pipeline — Phase 1 AutoML baseline (HPO),
  Phase 2 DEFT loop (RCA → SDG → mining → plain-trai...