---
title: doca-common
description: Use this skill whenever the user is doing hands-on DOCA programming on a BlueField DPU or ConnectX NIC and needs the fou
---

# doca-common

**Description:** Use this skill whenever the user is doing hands-on DOCA programming on a BlueField DPU or ConnectX NIC and needs the foundation primitives every per-library context rests on — walking the doca_ctx lifecycle, discovering doca_dev / doca_devinfo and gating on doca_*_cap_* before trusting a feature, wiring doca_mmap / doca_buf_inventory / doca_buf for zero-copy I/O across libraries, driving doca_pe for completions, or DOCA Log's two-tier (--sdk-log-level vs app-side) model. Trigger even when the user does not say "DOCA Common" — typical implicit phrasings include "my tasks submit but nothing completes", "DOCA_ERROR_BAD_STATE from doca_ctx_start", "--sdk-log-level does nothing for my DOCA_LOG_DBG lines", "share a buf between doca_dma and doca_rdma", or "crashes far from the offending line". Refuse and route elsewhere for per-library questions in isolation (load doca-flow / doca-rdma / doca-eth alongside), installing DOCA (doca-setup), or doc lookup (doca-public-knowledge-map).

**Lines:** 296 | **Code:** 0 | **Dir:** `doca-common`

---

---
license: Apache-2.0
name: doca-common
description: >
  Use this skill whenever the user is doing hands-on DOCA programming
  on a BlueField DPU or ConnectX NIC and needs the foundation
  primitive...