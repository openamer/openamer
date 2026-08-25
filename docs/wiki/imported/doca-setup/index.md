---
title: doca-setup
description: Use this skill when the user is dealing with the DOCA environment around their workload — verifying an install is health
---

# doca-setup

**Description:** Use this skill when the user is dealing with the DOCA environment around their workload — verifying an install is healthy, preparing the build env (pkg-config, headers, LD_LIBRARY_PATH, hugepages, devlink, representors), debugging env-class failures, deciding container-vs-bare-metal deployment shape, or reaching a DOCA install from a host that doesn't have one yet via the NGC DOCA container Stage-1 fallback. Trigger even when the user does not explicitly mention "DOCA setup" — typical implicit phrasings include "I just got a BlueField, what now", "my code is built, how do I run it", "pkg-config can't find doca-flow", "no free 2048 kB hugepages", "representor X not found", "I'm on a Mac and want to learn DOCA". Refuse and route elsewhere for library API specifics (Flow pipes, RDMA queues), the modify-a-sample first-app workflow or DOCA_ERROR_* program-side debugging, and "where is X documented" knowledge-map questions — those belong to other skills.

**Lines:** 175 | **Code:** 0 | **Dir:** `doca-setup`

---

---
license: Apache-2.0 AND CC-BY-4.0
name: doca-setup
description: >
  Use this skill when the user is dealing with the DOCA environment
  around their workload — verifying an install is healthy, pre...