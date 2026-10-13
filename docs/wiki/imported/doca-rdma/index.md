---
title: doca-rdma
description: Use this skill when the user is doing hands-on DOCA RDMA programming on a BlueField DPU, ConnectX NIC, or DOCA host — br
---

# doca-rdma

**Description:** Use this skill when the user is doing hands-on DOCA RDMA programming on a BlueField DPU, ConnectX NIC, or DOCA host — bringing up an RDMA context on a doca_dev, picking a connection method (RDMA CM, bridge/OOB, or gRPC exchange of doca_rdma_export()), enabling one of the eleven task types (Send/Receive/Send-Imm, Read/Write/Write-Imm, Atomic CmpSwap/FetchAdd, Get/Set/Add Remote Sync Event), setting matching mmap + RDMA permissions, sizing queues and connections, querying doca_rdma_cap_*, or debugging DOCA_ERROR_* from an RDMA call. Trigger even when the user does not mention "DOCA RDMA" — typical implicit phrasings include "one-sided read returns permission denied", "completions never arrive after submit", "connection callback never fires", "how do I do atomic compare-and-swap over RoCE", or "send queue hits DOCA_ERROR_FULL under burst". Refuse and route elsewhere for general RDMA / ibverbs theory (queue pairs, MRs, RoCE vs IB), installing DOCA itself, or non-RDMA DOCA libraries.

**Lines:** 275 | **Code:** 0 | **Dir:** `doca-rdma`

---

---
license: Apache-2.0
name: doca-rdma
description: >
  Use this skill when the user is doing hands-on DOCA RDMA programming
  on a BlueField DPU, ConnectX NIC, or DOCA host — bringing up an RDMA
  c...