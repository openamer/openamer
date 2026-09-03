---
title: tao-analyze-gaps-visual-changenet
description: Performs gap analysis on NVIDIA TAO VCN Classify (Visual Component Net) experiments by invoking the pinned TAO data-serv
---

# tao-analyze-gaps-visual-changenet

**Description:** Performs gap analysis on NVIDIA TAO VCN Classify (Visual Component Net) experiments by invoking the pinned TAO data-services container directly via `docker run … gap_analysis vcn_aoi …` — picks the optimal decision threshold, ranks per-sample weakness, and emits a top-K weakest parquet expanded per-lighting for downstream augmentation. Use when analyzing VCN classification failures, picking SDA augmentation targets, or auditing PASS/NO_PASS boundary cases.
**Lines:** 214 | **Code:** 71 | **Dir:** `tao-analyze-gaps-visual-changenet`

---

---
name: tao-analyze-gaps-visual-changenet
description: Performs gap analysis on NVIDIA TAO VCN Classify (Visual Component Net) experiments by invoking the pinned TAO data-services container directly...