---
title: nemo-mbridge-perf-activation-recompute
description: Validate and use selective and full activation recompute in Megatron Bridge to reduce GPU memory usage at the cost of ex
---

# nemo-mbridge-perf-activation-recompute

**Description:** Validate and use selective and full activation recompute in Megatron Bridge to reduce GPU memory usage at the cost of extra compute. Use for activation memory OOMs or regressions involving recompute_granularity, recompute_num_layers, recompute_modules, recompute_method, selective recompute, full recompute, or activation checkpointing.
**Lines:** 268 | **Code:** 5 | **Dir:** `nemo-mbridge-perf-activation-recompute`

---

---
name: nemo-mbridge-perf-activation-recompute
description: >-
  Validate and use selective and full activation recompute in Megatron Bridge
  to reduce GPU memory usage at the cost of extra compute...