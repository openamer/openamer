---
title: doca-sha-offload-engine
description: Use this skill when wiring the DOCA SHA Offload Engine (an OpenSSL ENGINE) into an existing OpenSSL pipeline to offload 
---

# doca-sha-offload-engine

**Description:** Use this skill when wiring the DOCA SHA Offload Engine (an OpenSSL ENGINE) into an existing OpenSSL pipeline to offload one-shot SHA-1, SHA-256, or SHA-512 (EVP_Digest) onto DOCA SHA hardware without rewriting against doca-sha. Covers engine load mechanics (`openssl engine dynamic`, `set_pci_addr` ctrl, `-engine_impl`), the SHA-224 negative test that proves offload engaged, the message-size window where offload beats CPU SHA, and engine-vs-library selection. Trigger even when the user does not say "DOCA SHA Offload Engine" or "OpenSSL ENGINE" — typical implicit phrasings: "speed up openssl SHA on BlueField", "offload SHA without code changes", "is openssl using the accelerator or falling back to software", "prove DOCA SHA actually ran", "openssl dgst hashed but I'm not sure it was offloaded". Refuse and route elsewhere for new SHA pipelines (use doca-sha), MD5 / SHA-3 / SHA-224 / HMAC-SHA offload, incremental hashing via chained `EVP_DigestUpdate`, or OpenSSL PROVIDER authoring.

**Lines:** 342 | **Code:** 0 | **Dir:** `doca-sha-offload-engine`

---

---
license: Apache-2.0
name: doca-sha-offload-engine
description: >
  Use this skill when wiring the DOCA SHA Offload Engine
  (an OpenSSL ENGINE) into an existing OpenSSL pipeline
  to offload one-s...