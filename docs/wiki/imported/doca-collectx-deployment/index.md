---
title: doca-collectx-deployment
description: Use this skill to deploy and operate a CollectX (clx) based DOCA telemetry collector on a host or BlueField — wiring pro
---

# doca-collectx-deployment

**Description:** Use this skill to deploy and operate a CollectX (clx) based DOCA telemetry collector on a host or BlueField — wiring providers / counters into the collector, running the collection daemon, and shaping its exporters (Prometheus pull, Fluent Bit push, NetFlow, file / IPC) so the metrics actually leave the box. Trigger even when the user never says CollectX or clx — implicit phrasings: {collector emits nothing downstream}, {add a provider to the clx collector}, {turn on the Prometheus endpoint}, {ship counters to Fluent Bit from the DPU}, {daemon starts but no schema rows appear}. This skill owns the CollectX collection mechanism plus the operator's own doca-telemetry / doca-telemetry-exporter usage; it ROUTES the productized DOCA Telemetry Service (DTS) to public docs (AGENTS.md Non-goal #7), the reader API to doca-telemetry, and the publisher API to doca-telemetry-exporter. Refuse to invent clx symbols, provider names, schema fields, flags, or config paths — describe the class and route to the live source.

**Lines:** 234 | **Code:** 0 | **Dir:** `doca-collectx-deployment`

---

---
license: Apache-2.0
name: doca-collectx-deployment
description: >
  Use this skill to deploy and operate a CollectX (clx) based
  DOCA telemetry collector on a host or BlueField — wiring
  provide...