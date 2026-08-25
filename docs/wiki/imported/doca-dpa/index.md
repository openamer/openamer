---
title: doca-dpa
description: Use this skill when the user is doing hands-on DOCA DPA host-side work on a BlueField — creating the `doca_dpa` Core con
---

# doca-dpa

**Description:** Use this skill when the user is doing hands-on DOCA DPA host-side work on a BlueField — creating the `doca_dpa` Core context, loading a DPACC-compiled DPA app image (`doca_dpa_app`), creating DPA threads, launching kernels via `doca_dpa_kernel_launch_update_*`, draining `doca_dpa_completion`, running `doca_dpa_cap_*` discovery, choosing between the DPA comm component (inter-DPA messaging) and the DPA verbs component (in-kernel RDMA), or debugging `DOCA_ERROR_*` from `doca_dpa_*`. Trigger even without "DOCA DPA" or "Data-Path Accelerator": "run compute on the DPA from my host", "DPA kernel hangs, no completion", "DOCA_ERROR_DRIVER on launch", "DOCA/DPACC version skew", or "does this BlueField expose a DPA". Route elsewhere for DPA-side kernel programming itself, DPACC compiler internals, host↔DPU messaging (doca-comch), host-side RDMA (doca-rdma), and GPU-initiated networking (doca-gpunetio).

**Lines:** 387 | **Code:** 0 | **Dir:** `doca-dpa`

---

---
license: Apache-2.0
name: doca-dpa
description: >
  Use this skill when the user is doing hands-on DOCA DPA host-side
  work on a BlueField — creating the `doca_dpa` Core context, loading
  a DPAC...