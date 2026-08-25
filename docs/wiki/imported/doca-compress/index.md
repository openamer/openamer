---
title: doca-compress
description: Use this skill for hands-on DOCA Compress programming on a BlueField DPU, ConnectX NIC, or host with DOCA — enabling com
---

# doca-compress

**Description:** Use this skill for hands-on DOCA Compress programming on a BlueField DPU, ConnectX NIC, or host with DOCA — enabling compress-deflate, decompress-deflate, decompress-lz4-stream, or decompress-lz4-block tasks on a doca_compress context (the hardware supports DEFLATE both directions plus LZ4 decompress; LZ4 encode is NOT supported), sizing source / destination doca_buf against the per-task cap query, setting mmap permissions, deciding offload vs CPU zlib / zstd, validating with a round-trip smoke, or debugging DOCA_ERROR_* from a Compress call. Trigger on phrasings like "offload this gzip", "decompress incoming network data", "compress task returns INVALID_VALUE on alloc_init", "submitted a task but no completion arrives", or "decompress LZ4 on the BlueField." Refuse and route elsewhere for non-DEFLATE / non-LZ4 algorithms (zstd / Snappy / brotli), LZ4 encode (route to a CPU LZ4 library), pure mmap-to-mmap copies (doca-dma), or DOCA Core lifecycle internals.

**Lines:** 301 | **Code:** 0 | **Dir:** `doca-compress`

---

---
license: Apache-2.0
name: doca-compress
description: >
  Use this skill for hands-on DOCA Compress programming on a
  BlueField DPU, ConnectX NIC, or host with DOCA — enabling
  compress-deflate, ...