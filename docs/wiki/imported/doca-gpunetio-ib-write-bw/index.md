---
title: doca-gpunetio-ib-write-bw
description: Use this skill when the user is building, running, or interpreting the doca/tools/gpunetio_ib_write_bw client+server ben
---

# doca-gpunetio-ib-write-bw

**Description:** Use this skill when the user is building, running, or interpreting the doca/tools/gpunetio_ib_write_bw client+server benchmark — a CUDA kernel on the client posts RDMA WRITE work requests through the doca-gpunetio device-side surface to measure sustained GPU-driven WRITE bandwidth on a GPU+IB-device pair. Trigger even when the user does not explicitly mention "doca-gpunetio-ib-write-bw" or "GPUNetIO" — typical implicit phrasings include "measure WRITE BW when the GPU posts the WRs", "BW swings between runs on the same flags", "is the NIC saturated or am I CPU-bound on the CUDA kernel", "meson compile fails for the GPUNetIO bw tool", "nvidia_peermem isn't picking up my GPU buffer", or "GPU-initiated WRITE throughput vs CPU-initiated perftest". Refuse and route elsewhere for general doca-gpunetio library work, DOCA install, the GPU-initiated WRITE latency analog, the CPU-initiated upstream perftest, or application-level end-to-end throughput — those belong to other skills.

**Lines:** 354 | **Code:** 0 | **Dir:** `doca-gpunetio-ib-write-bw`

---

---
license: Apache-2.0
name: doca-gpunetio-ib-write-bw
description: >
  Use this skill when the user is building, running, or interpreting
  the doca/tools/gpunetio_ib_write_bw client+server benchmar...