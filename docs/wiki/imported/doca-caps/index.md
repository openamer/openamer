---
title: doca-caps
description: Use this skill when the user wants to invoke the read-only doca_caps CLI to ask what DOCA sees on this host — listing DO
---

# doca-caps

**Description:** Use this skill when the user wants to invoke the read-only doca_caps CLI to ask what DOCA sees on this host — listing DOCA devices and PCIe addresses, listing representor devices, asking which DOCA libraries are available on the current OS, checking per-device per-library capabilities, scoping output to a specific PCIe address, or capturing a side-effect-free capability snapshot for a debug session or install smoke-test. Trigger even when the user does not explicitly mention "doca_caps" or "capabilities print tool" — typical implicit phrasings include "what does DOCA actually see on this box", "is my BlueField PF visible to DOCA", "is Flow available on my RHEL host", "enumerate VF representors for pf0", "doca_caps: command not found", or "empty output for RDMA, is the tool broken". Refuse and route elsewhere for DOCA installation, library-internal capability matrices (Flow pipe creation, RDMA verbs features), streaming telemetry / DTS, or modifying the shipped binary — those belong to other skills.

**Lines:** 204 | **Code:** 0 | **Dir:** `doca-caps`

---

---
license: Apache-2.0
name: doca-caps
description: >
  Use this skill when the user wants to invoke the read-only
  doca_caps CLI to ask what DOCA sees on this host — listing
  DOCA devices and PCIe...