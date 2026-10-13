---
title: doca-gpi
description: Use this skill for hands-on DOCA GPI programming — wiring a GPU-Packet-Initiator context so a CUDA kernel drives RDMA qu
---

# doca-gpi

**Description:** Use this skill for hands-on DOCA GPI programming — wiring a GPU-Packet-Initiator context so a CUDA kernel drives RDMA queues directly from GPU memory without host CPU mediation. Covers picking GPI vs doca-gpunetio, the doca_gpi / domain / channel object model, the GPU-side handle handoff (doca_gpu_gpi_channel*), attaching GPU memory to a GPI domain, the domain and channel attribute objects, and debugging DOCA_ERROR_* from doca_gpi_* calls. Trigger even when the user does not explicitly mention "DOCA GPI" — implicit phrasings include "my CUDA kernel needs to post RDMA directly from GPU memory", "DOCA_ERROR_* from doca_gpi_gpu_channel_get", "how do I hand a GPU handle to my CUDA kernel", "how many channels can a GPI domain hold", or "GPU kernel driving RDMA without the host CPU on the path". Refuse and route elsewhere for the doca-gpunetio Send/Receive surface, the doca-rdma queue lifecycle, DPA-side initiation (doca-rdmi), or the CUDA programming model — those belong to other skills.

**Lines:** 311 | **Code:** 0 | **Dir:** `doca-gpi`

---

---
license: Apache-2.0
name: doca-gpi
description: >
  Use this skill for hands-on DOCA GPI programming
  — wiring a GPU-Packet-Initiator context so a CUDA kernel drives
  RDMA queues directly from G...