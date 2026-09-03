---
title: paidf-anomalygen
description: Full PAIDF AnomalyGen pipeline — fine-tune on a new anomaly dataset, generate synthetic anomaly images (SDG), evaluate q
---

# paidf-anomalygen

**Description:** Full PAIDF AnomalyGen pipeline — fine-tune on a new anomaly dataset, generate synthetic anomaly images (SDG), evaluate quality (nn_score), and search per-sample (guidance, crop_ratio) parameters. Three modes: full (Phase 0→7: finetune then generate), finetune_only (Phase 0→1: train only), inference_only (Phase 0, 2→7: generate from an existing checkpoint). Use when the user asks to "fine-tune AnomalyGen", "generate anomaly images", "run PAIDF SDG", "evaluate SDG output quality", "run per-sample search", or run any part of the AnomalyGen pipeline, even if they only mention one phase.
**Lines:** 376 | **Code:** 66 | **Dir:** `paidf-anomalygen`

---

---
name: paidf-anomalygen
license: Apache-2.0
compatibility: Requires docker + nvidia-container-toolkit and a CUDA GPU. Pulls the `metropolis_sdg.paidf_anomalygen` image declared in `versions.yaml` a...