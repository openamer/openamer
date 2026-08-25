---
title: doca-aes-gcm
description: Use this skill when the user is doing hands-on DOCA AES-GCM work on a BlueField DPU or ConnectX NIC — configuring `doca_
---

# doca-aes-gcm

**Description:** Use this skill when the user is doing hands-on DOCA AES-GCM work on a BlueField DPU or ConnectX NIC — configuring `doca_aes_gcm_task_encrypt` / `_task_decrypt`, querying `doca_aes_gcm_cap_*` for per-key-type (only `DOCA_AES_GCM_KEY_128` / `_256` — AES-192 not supported) and per-task support, sizing plaintext against the max-buf cap, setting source / destination mmap permissions, validating with a NIST GCMVS or RFC 5288 vector, or debugging DOCA_ERROR_* including the security-critical tag-verification-failed outcome on decrypt. Trigger even when the user does not explicitly mention "DOCA AES-GCM" or "AEAD" — typical implicit phrasings: "decrypt completion IO_FAILED", "auth tag isn't verifying", "NOT_PERMITTED on my encrypt buffer", "is AES-192-GCM on this BlueField" (no), or "encrypted record came back tampered". Refuse and route elsewhere for non-GCM AES modes (CBC / CTR / XTS — CPU OpenSSL), key management (KMS / HSM / rotation), SHA (doca-sha), or general AEAD background.

**Lines:** 322 | **Code:** 0 | **Dir:** `doca-aes-gcm`

---

---
license: Apache-2.0
name: doca-aes-gcm
description: >
  Use this skill when the user is doing hands-on DOCA AES-GCM
  work on a BlueField DPU or ConnectX NIC — configuring
  `doca_aes_gcm_task_enc...