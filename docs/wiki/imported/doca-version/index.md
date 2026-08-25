---
title: doca-version
description: Use this skill when the user is doing DOCA version handling — detecting the installed release, validating the four-way m
---

# doca-version

**Description:** Use this skill when the user is doing DOCA version handling — detecting the installed release, validating the four-way match across pkg-config doca-common, applications/VERSION, doca_caps --version, and bfver/mlnx-release on BlueField, reasoning about NGC container tags, looking up whether a capability is on the installed release, or diagnosing build-vs-runtime drift. Trigger even when the user does not explicitly say "DOCA version" or "four-way match" — typical implicit phrasings include "program built but does nothing on the wire", "undefined reference to a symbol the docs claim exists", "DOCA_ERROR_NOT_SUPPORTED at runtime", "counter didn't increment", "what does `latest` mean for this tag", or "is my LTS still supported". Refuse and route elsewhere for installing or choosing DOCA packages (doca-setup), per-library API/capability questions (matching library skill), the cross-library DOCA_ERROR_* taxonomy (doca-programming-guide), or the general debug ladder (doca-debug) — those belong to other skills.

**Lines:** 194 | **Code:** 0 | **Dir:** `doca-version`

---

---
license: Apache-2.0
name: doca-version
description: >
  Use this skill when the user is doing DOCA version handling —
  detecting the installed release, validating the four-way match
  across pkg-...