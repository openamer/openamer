---
title: tao-route-visual-changenet-samples
description: Routes the weakest VCN samples (output of `tao-analyze-gaps-visual-changenet`) into per-augmentation-module subsets base
---

# tao-route-visual-changenet-samples

**Description:** Routes the weakest VCN samples (output of `tao-analyze-gaps-visual-changenet`) into per-augmentation-module subsets based on each module's label eligibility. Use when the user asks to "route VCN gap samples", "split AOI gaps for k-NN mining and AnomalyGen", or prepare the immediate next step after DEFT gap analysis in a VCN AOI SDA iteration.
**Lines:** 270 | **Code:** 145 | **Dir:** `tao-route-visual-changenet-samples`

---

---
name: tao-route-visual-changenet-samples
description: Routes the weakest VCN samples (output of `tao-analyze-gaps-visual-changenet`) into per-augmentation-module
  subsets based on each module's l...