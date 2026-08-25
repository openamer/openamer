---
title: doca-telemetry
description: Use this skill to read DOCA hardware-counter events from a `doca_dev` through the per-domain Telemetry reader libraries:
---

# doca-telemetry

**Description:** Use this skill to read DOCA hardware-counter events from a `doca_dev` through the per-domain Telemetry reader libraries: `doca_telemetry_pcc`, `_dpa`, `_diag`, `_adp_retx`, `_phy`, and `_pci`. It covers capability checks, context creation, startup, and per-domain reads or samples. Trigger for implicit requests such as "read PCC counters from my BlueField app", "sample DPA counter exports", or "expose PHY, PCI, or DIAG counters from this doca_dev". This is the counter-reader surface, not a NetFlow, IPFIX, or local-socket collector. Route publishing and export to `doca-telemetry-exporter`; route deployed DOCA Telemetry Service (DTS), collectors, and plain stdout logging elsewhere.

**Lines:** 225 | **Code:** 0 | **Dir:** `doca-telemetry`

---

---
license: Apache-2.0
name: doca-telemetry
description: >
  Use this skill to read DOCA hardware-counter events from a
  `doca_dev` through the per-domain Telemetry reader libraries:
  `doca_telemet...