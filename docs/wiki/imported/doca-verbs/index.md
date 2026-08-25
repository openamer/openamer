---
title: doca-verbs
description: Use this skill when the user is dropping below the higher-level DOCA libraries (doca-rdma / doca-eth / doca-rmax) into t
---

# doca-verbs

**Description:** Use this skill when the user is dropping below the higher-level DOCA libraries (doca-rdma / doca-eth / doca-rmax) into the raw-verbs escape hatch — managing QP / CQ / PD / MR / SRQ / AH / CC-group / Ethernet-SQ-RQ primitives inside DOCA Core, porting libibverbs code into the DOCA Core model, capability-querying a specific verb / opcode / WR flag / QP attribute via doca_verbs_query_device, or debugging DOCA_ERROR_* from doca_verbs_* calls. Trigger even when the user does not say "doca-verbs" — implicit phrasings include "raw QP attribute the task API doesn't expose", "keep my ibv_* code next to doca_* on the same QP", "IO_FAILED on WR submit", "QP state transition rejected", "attach a congestion- control group", or "porting my libibverbs code". The skill's first job is to route MOST users back UP to the higher-level library. Refuse and route elsewhere for general doca-rdma / doca-eth / doca-rmax workloads, DOCA install, Core internals, and general libibverbs theory — those belong to other skills.

**Lines:** 377 | **Code:** 0 | **Dir:** `doca-verbs`

---

---
license: Apache-2.0
name: doca-verbs
description: >
  Use this skill when the user is dropping below the higher-level DOCA
  libraries (doca-rdma / doca-eth / doca-rmax) into the raw-verbs escape
...