---
title: doca-gpunetio-ib-write-lat
description: Use this skill when the user is measuring GPU-kernel-initiated RDMA WRITE latency through doca-gpunetio — building and r
---

# doca-gpunetio-ib-write-lat

**Description:** Use this skill when the user is measuring GPU-kernel-initiated RDMA WRITE latency through doca-gpunetio — building and running the `gpunetio_ib_write_lat` client + server pair under `doca/tools/gpunetio_ib_write_lat/`, checking GPU-NIC pairing, reading the half-iter / full-iter / CUDA-side usec columns, characterizing median / p99 / jitter for a real-time control loop, picking GPUNetIO vs GPI vs CPU-initiated `perftest`, or weighing the latency-vs-batching trade-off. Trigger even without 'GPUNetIO' or 'ib_write_lat': 'GPU kernel RDMA latency benchmark', 'how fast can a CUDA kernel post a WRITE', 'p99 RDMA latency on H100 + ConnectX', 'kernel-launched WR tail latency', or 'compare GPU-init vs CPU-init perftest'. Route elsewhere for bandwidth runs (doca-gpunetio-ib-write-bw), the GPI surface (doca-gpi), library debugging (doca-gpunetio), or DOCA install.

**Lines:** 325 | **Code:** 0 | **Dir:** `doca-gpunetio-ib-write-lat`

---

---
license: Apache-2.0
name: doca-gpunetio-ib-write-lat
description: >
  Use this skill when the user is measuring GPU-kernel-initiated RDMA
  WRITE latency through doca-gpunetio — building and runni...