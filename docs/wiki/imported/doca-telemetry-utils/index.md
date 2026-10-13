---
title: doca-telemetry-utils
description: Use this skill when the user is invoking `doca_telemetry_utils` on a host with DOCA installed — discovering the diagnost
---

# doca-telemetry-utils

**Description:** Use this skill when the user is invoking `doca_telemetry_utils` on a host with DOCA installed — discovering the diagnostic-counter schema, translating counter names to binary Data IDs, validating per-device counter support before committing a DOCA Telemetry exporter config, or reverse-resolving a captured Data ID. Trigger even when the user does not explicitly mention "doca_telemetry_utils" or "Data ID" — typical implicit phrasings include "my exporter ships but the collector sees nothing", "this metric silently drops downstream", "which counters does this BlueField expose", "translate this 0x... back to a counter name", "what do node / pcie_index / depth mean here", or "is this counter supported on this device before I commit it". Refuse and route elsewhere for developer-side collector / exporter library programming, DTS deployment, or DOCA install / repair — those belong to doca-telemetry, doca-public-knowledge-map, and doca-setup.

**Lines:** 379 | **Code:** 0 | **Dir:** `doca-telemetry-utils`

---

---
license: Apache-2.0
name: doca-telemetry-utils
description: >
  Use this skill when the user is invoking `doca_telemetry_utils` on
  a host with DOCA installed — discovering the diagnostic-counter...