---
title: doca-gpunetio
description: Use this skill when the user is doing hands-on DOCA GPUNetIO programming — wiring a CUDA kernel on an NVIDIA GPU to a do
---

# doca-gpunetio

**Description:** Use this skill when the user is doing hands-on DOCA GPUNetIO programming — wiring a CUDA kernel on an NVIDIA GPU to a doca-eth queue via doca_gpu_eth_rxq / doca_gpu_eth_txq, standing up the per-CUDA-device doca_gpu context, designing the persistent CUDA kernel that drains the GPU-visible queue, running the dual capability check (DOCA cap-query plus cudaGetDeviceProperties), registering cudaMalloc pools via doca_buf_arr_create_*, or debugging DOCA_ERROR_* returns from the GPUNetIO API. Trigger even when the user does not explicitly mention "DOCA GPUNetIO" or "persistent kernel" — typical implicit phrasings include "CUDA kernel reading packets directly from the NIC", "GPU-initiated networking on BlueField", "DOCA_ERROR_DRIVER on doca_gpu_create", "nvidia_peermem not loaded", "kernel-per-packet is too slow", or "which GPU supports GPU-side packet I/O". Refuse and route elsewhere for general CUDA programming, DOCA Ethernet queue bring-up, DOCA DPA, or DOCA install — those belong to other skills.

**Lines:** 299 | **Code:** 0 | **Dir:** `doca-gpunetio`

---

---
license: Apache-2.0
name: doca-gpunetio
description: >
  Use this skill when the user is doing hands-on DOCA GPUNetIO
  programming — wiring a CUDA kernel on an NVIDIA GPU to a doca-eth
  queue vi...