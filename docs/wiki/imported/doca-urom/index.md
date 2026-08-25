---
title: doca-urom
description: Use this skill when the user is doing hands-on DOCA UROM library work from the host side — wiring doca-urom under an HPC
---

# doca-urom

**Description:** Use this skill when the user is doing hands-on DOCA UROM library work from the host side — wiring doca-urom under an HPC / UCX / MPI stack to OFFLOAD remote memory operations (puts, gets, atomics, collectives) onto a BlueField DPU, creating a UROM Service context (doca_urom_service_*) and Worker contexts (doca_urom_worker_*) that run plugins on the DPU, discovering plugins via doca_urom_service_get_plugins_list, progressing completions, or debugging DOCA_ERROR_* from a doca_urom_* call. Trigger even without "DOCA UROM": "MPI all-reduce burning host CPU", "push UCX traffic onto the BlueField", "first doca_urom call returns NOT_PERMITTED", or "host library and DPU service look out of sync". Route elsewhere for UROM Service deployment on the DPU side, MPI / UCX collective algorithm design, and RDMA / RoCE / IB substrate bring-up.

**Lines:** 358 | **Code:** 0 | **Dir:** `doca-urom`

---

---
license: Apache-2.0
name: doca-urom
description: >
  Use this skill when the user is doing hands-on DOCA UROM library work
  from the host side — wiring doca-urom under an HPC / UCX / MPI stack
  ...