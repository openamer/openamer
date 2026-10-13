---
title: tao-run-automl
description: Run container-backed AutoML / hyperparameter optimization (HPO) for NVIDIA TAO networks using AutoMLRunner. Handles algo
---

# tao-run-automl

**Description:** Run container-backed AutoML / hyperparameter optimization (HPO) for NVIDIA TAO networks using AutoMLRunner. Handles algorithm selection (bayesian, hyperband, asha, bohb, llm, hybrid, autoresearch), WandB experiment tracking, job execution on any TAO SDK platform, result interpretation, and per-rec custom evaluation hooks. Use when the user mentions TAO AutoML, hyperparameter optimization, HPO, automl, automl_settings, AutoMLRunner, tao_automl, bayesian search, hyperband, ASHA, LLM-guided search, autoresearch, or wants to tune train/distill/prune/quantize action parameters for any TAO network. Model actions use the model skill's resolved container image by default; venv training requires an explicit user request. Platform-agnostic — runs on any SDK (Brev, SLURM, Kubernetes, Docker).
**Lines:** 391 | **Code:** 26 | **Dir:** `tao-run-automl`

---

---
name: tao-run-automl
description: Run container-backed AutoML / hyperparameter optimization (HPO) for NVIDIA TAO networks using AutoMLRunner. Handles algorithm
  selection (bayesian, hyperband, as...