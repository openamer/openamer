---
title: doca-dpa-hl-tracer
description: Use this skill when the user runs doca_dpa_hl_tracer to capture/decode DPA-side traces at the programming-events layer (
---

# doca-dpa-hl-tracer

**Description:** Use this skill when the user runs doca_dpa_hl_tracer to capture/decode DPA-side traces at the programming-events layer (kernel entry/exit, sync points, comm primitive calls, RDMA WR submission, completion drain) — picking TRACE vs CRIT, tuning the JSON config (file-size limits + file_size_limit_policy, thread priorities/cores), decoding against the matching DPA-side ELF, or diagnosing empty/noisy captures. Trigger even when the user does not explicitly mention "DOCA DPA tracer" or "high-level tracer" — typical implicit phrasings include "DPA kernel returns wrong result but host completions look clean", "kernel-entry to first-comm latency is huge", "RDMA WR to drain gap on the DPA", "trace file truncated mid-run", "TRACE doubled my DPA latency", or "tracer wrote a file but parser shows zero events". Refuse and route elsewhere for writing DPA kernels, DPA-Comms/DPA-Verbs programming, raw per-cycle DPA profiling, host-side doca-dpa debugging, or production DPA telemetry — those belong to other skills.

**Lines:** 367 | **Code:** 0 | **Dir:** `doca-dpa-hl-tracer`

---

---
license: Apache-2.0
name: doca-dpa-hl-tracer
description: >
  Use this skill when the user runs doca_dpa_hl_tracer to
  capture/decode DPA-side traces at the programming-events
  layer (kernel ent...