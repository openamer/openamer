---
title: doca-flow-perf
description: Use this skill when the user is measuring the host or DPU-CPU control-plane rate of a DOCA Flow pipeline with doca_flow_
---

# doca-flow-perf

**Description:** Use this skill when the user is measuring the host or DPU-CPU control-plane rate of a DOCA Flow pipeline with doca_flow_perf — picking a JSON policy from configs/, choosing the DPDK or DOCA backend, running the single-iteration smoke then the iterative eval loop, interpreting per-iteration CPU cycles and num_pushed / num_failed, or capturing the four-tuple (DOCA version, BlueField/firmware, JSON policy, worker/queue/burst config) that makes a Kops/sec number defensible. Trigger even when the user does not explicitly mention "doca-flow-perf" — typical implicit phrasings include "how many rules per second can my BlueField insert", "5-tuple hairpin rule rate", "Kops/sec for steering", "flow-perf number does not match release notes", "DPDK vs DOCA benchmark", or "rule-install variance too high". Refuse and route elsewhere for optimizing a live Flow app (doca-flow-tune), the DPA-offloaded path (doca-flow-dpa-perf), dataplane throughput or latency, or library-internal pipe semantics — those belong to other skills.

**Lines:** 332 | **Code:** 0 | **Dir:** `doca-flow-perf`

---

---
license: Apache-2.0
name: doca-flow-perf
description: >
  Use this skill when the user is measuring the host or DPU-CPU
  control-plane rate of a DOCA Flow pipeline with doca_flow_perf —
  picking...