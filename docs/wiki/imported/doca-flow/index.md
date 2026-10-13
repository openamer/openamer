---
title: doca-flow
description: Build and debug DOCA Flow applications on supported NVIDIA NICs/DPUs: define match/action pipes, initialize ports and re
---

# doca-flow

**Description:** Build and debug DOCA Flow applications on supported NVIDIA NICs/DPUs: define match/action pipes, initialize ports and representors, choose forwarding targets, validate pipes before hardware programming, read counters, match the Flow version to the installed DOCA release, and diagnose Flow API errors. Trigger on DOCA packet steering, classifier, representor, rule-matching, hairpin, or 5-tuple-to-queue questions even when "DOCA Flow" is not named. Route plain DPDK `rte_flow`, kernel TC, OVS, BFB bring-up, and DPU OS installation elsewhere. DPU OS installation is destructive and always requires explicit confirmation.

**Lines:** 270 | **Code:** 8 | **Dir:** `doca-flow`

---

---
name: doca-flow
license: Apache-2.0
description: >
  Build and debug DOCA Flow applications on supported NVIDIA NICs/DPUs:
  define match/action pipes, initialize ports and representors, choose
  ...