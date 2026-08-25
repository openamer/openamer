---
title: doca-erasure-coding
description: Use this skill when the user is doing hands-on DOCA Erasure Coding programming on a BlueField DPU, ConnectX NIC, or host
---

# doca-erasure-coding

**Description:** Use this skill when the user is doing hands-on DOCA Erasure Coding programming on a BlueField DPU, ConnectX NIC, or host — bringing up a doca_ec context, picking among the create / recover / update tasks, choosing matrix type / N / K / block size, querying doca_ec_cap_* before sizing, setting doca_mmap src/dst permissions, or debugging DOCA_ERROR_* returns from doca_ec_task_*. Trigger even when the user does not name "DOCA Erasure Coding" or "Reed-Solomon" — typical implicit phrasings include "one data block changed, how do I refresh parity without re-encoding", "a disk failed and 2 parity blocks are gone, can I rebuild", "RAID-6 resilience across 12 disks", "my doca_ec_task_create returns NOT_PERMITTED", or "is this N+K layout still recoverable". Refuse and route elsewhere for non-Reed-Solomon codes (fountain / LDPC / raptor), pure-replication designs, network FEC, or other DOCA accelerator libraries (SHA / Compress / AES-GCM / DMA) — those belong to other skills.

**Lines:** 332 | **Code:** 0 | **Dir:** `doca-erasure-coding`

---

---
license: Apache-2.0
name: doca-erasure-coding
description: >
  Use this skill when the user is doing hands-on DOCA Erasure Coding
  programming on a BlueField DPU, ConnectX NIC, or host — bringing...