---
title: doca-flow-dpa-provider
description: Use this skill when the user is doing hands-on DOCA Flow DPA Provider work — exporting a `doca-flow` pipe or external re
---

# doca-flow-dpa-provider

**Description:** Use this skill when the user is doing hands-on DOCA Flow DPA Provider work — exporting a `doca-flow` pipe or external resource (index-selector/memory) into BlueField DPA address space so a DPACC-built kernel can read counters, mutate hash-pipe entries, and update/read memory or index-selector resources inline with Flow. Covers per-port `doca_flow_dpa_ctx`, three queue types (general/resources-write/resources-read), the order-sensitive export handshake (`_export_prepare` → add entries → `_export` → `_get_device_addr`), and DPA-side device API. Trigger even when the user does not say "DOCA Flow DPA Provider" — implicit phrasings include "DPA kernel never sees entries in the exported pipe", "BAD_STATE from `_pipe_export`", "how do I disable a hash entry from a DPA kernel", "DPA memory read returns no value", or "DPA-side post keeps returning AGAIN". Refuse and route elsewhere for `doca-flow` pipe construction, generic host-side DPA (`doca-dpa`), or DPA-side kernel-writing — those belong to other skills.

**Lines:** 371 | **Code:** 0 | **Dir:** `doca-flow-dpa-provider`

---

---
license: Apache-2.0
name: doca-flow-dpa-provider
description: >
  Use this skill when the user is doing hands-on DOCA Flow DPA
  Provider work — exporting a `doca-flow` pipe or external
  resource...