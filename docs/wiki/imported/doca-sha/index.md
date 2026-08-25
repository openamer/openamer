---
title: doca-sha
description: Use this skill when the user is doing hands-on DOCA SHA programming — offloading SHA-1, SHA-256, or SHA-512 hashing onto
---

# doca-sha

**Description:** Use this skill when the user is doing hands-on DOCA SHA programming — offloading SHA-1, SHA-256, or SHA-512 hashing onto a BlueField DPU or ConnectX accelerator, picking between one-shot `doca_sha_task_hash` and incremental `doca_sha_task_partial_hash`, querying `doca_sha_cap_*` for algorithm support and min destination / max source buffer sizes, setting source / destination `doca_mmap` permissions, or decoding DOCA_ERROR_* returns from the SHA API. Trigger even when the user does not explicitly mention "DOCA SHA" or "doca_sha_task" — typical implicit phrasings include "hash a multi-GiB file on the DPU", "offload SHA-256 to the BlueField", "streaming hash over chunks", "partial hash returns BAD_STATE", "destination buffer too small for digest", or "is SHA-512 available on this card". Refuse and route elsewhere for general cryptographic-hash theory (collision resistance, SHA-3 selection), other DOCA crypto libraries (AES-GCM, Compress, DMA), or DOCA install / BFB bring-up — those belong to other skills.

**Lines:** 267 | **Code:** 0 | **Dir:** `doca-sha`

---

---
license: Apache-2.0
name: doca-sha
description: >
  Use this skill when the user is doing hands-on DOCA SHA programming —
  offloading SHA-1, SHA-256, or SHA-512 hashing onto a BlueField DPU or
  ...