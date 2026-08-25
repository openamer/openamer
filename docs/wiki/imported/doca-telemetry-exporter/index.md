---
title: doca-telemetry-exporter
description: Use this skill when the user is doing hands-on DOCA Telemetry Exporter programming on a host where DOCA is installed — d
---

# doca-telemetry-exporter

**Description:** Use this skill when the user is doing hands-on DOCA Telemetry Exporter programming on a host where DOCA is installed — defining a doca_telemetry_exporter_schema and event types, creating sources, picking a publish surface (typed events / opaque events / the metrics counter-gauge-histogram API / OTLP logs / NetFlow), walking the schema-then-source lifecycle, or debugging DOCA_ERROR_* failures from the exporter API. Trigger even when the user does not explicitly mention "DOCA Telemetry Exporter" or "doca_telemetry_exporter_*" — typical implicit phrasings include "publishing counters from my DOCA app", "BAD_STATE when I report an event", "consumer/DTS sees nothing but my report succeeded", "how do I export NetFlow/IPFIX records", or "should I link the exporter or the telemetry service". Refuse and route elsewhere for the receiving DOCA Telemetry Service (DTS), plain stdout logging via doca_log, or real-time event subscription back into the app via doca-comch — those belong to other skills.

**Lines:** 322 | **Code:** 0 | **Dir:** `doca-telemetry-exporter`

---

---
license: Apache-2.0
name: doca-telemetry-exporter
description: >
  Use this skill when the user is doing hands-on DOCA Telemetry
  Exporter programming on a host where DOCA is installed — defining...