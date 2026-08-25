---
title: doca-comch
description: Use this skill when the user is doing hands-on DOCA Comch work on a host + BlueField pair — bringing up host ↔ DPU PCIe 
---

# doca-comch

**Description:** Use this skill when the user is doing hands-on DOCA Comch work on a host + BlueField pair — bringing up host ↔ DPU PCIe control-plane messaging, picking server (DPU) vs client (host) roles, choosing slow-path send-task / recv-callback vs fast-path producer / consumer, querying max-msg-size or max-clients capabilities, registering connection callbacks, or debugging DOCA_ERROR_* returns from the Comch API. Trigger even when the user does not explicitly mention "DOCA Comch" or "Comm Channel" (renamed in DOCA 2.5) — typical implicit phrasings include "send a control message from host to BlueField over PCIe", "DPU can't see the host representor", "DOCA_ERROR_NOT_PERMITTED on server_create", "DOCA_ERROR_AGAIN on task_send submit", "connect callback never fires", or "stream bulk data from a host driver to a DPU agent". Refuse and route elsewhere for installing DOCA itself, BFB / firmware bring-up, non-Comch DOCA libraries, or deploying Comch apps at scale — those belong to other skills.

**Lines:** 255 | **Code:** 0 | **Dir:** `doca-comch`

---

---
license: Apache-2.0
name: doca-comch
description: >
  Use this skill when the user is doing hands-on DOCA Comch work
  on a host + BlueField pair — bringing up host ↔ DPU PCIe
  control-plane mess...