---
title: doca-sta
description: Use this skill when the user is doing hands-on NVMe-over-Fabrics storage-target work on a BlueField DPU or ConnectX NIC 
---

# doca-sta

**Description:** Use this skill when the user is doing hands-on NVMe-over-Fabrics storage-target work on a BlueField DPU or ConnectX NIC with DOCA STA — standing up a doca_sta DOCA Core context that accelerates the target-side NVMe-oF data path over RDMA, defining doca_sta_subsystem targets (NQN + namespaces) backed by local NVMe-PCI backend disks (doca_sta_be), checking device support via doca_sta_cap_is_supported, sizing the per-connection I/O queues, or debugging DOCA_ERROR_* from a STA call. Trigger even when the user does not say "DOCA STA" — typical implicit phrasings include "my NVMe-oF Connect never completes", "Identify Controller times out over RoCE", "16 I/O queues at depth 1024 — does this BlueField support that", "offload the nvmf target onto the DPU", or "DOCA_ERROR_IO_FAILED on an NVMe read". Refuse and route elsewhere for DOCA install, raw RDMA data movement, raw packet I/O, flow-rule programming, or initiator-side / host NVMe stack work — those belong to other skills.

**Lines:** 317 | **Code:** 0 | **Dir:** `doca-sta`

---

---
license: Apache-2.0
name: doca-sta
description: >
  Use this skill when the user is doing hands-on NVMe-over-Fabrics
  storage-target work on a BlueField DPU or ConnectX NIC with DOCA STA —
  stan...