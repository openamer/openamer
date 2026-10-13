---
title: doca-flow-tune
description: Use this skill when the user is tuning a live or captured `doca-flow` pipeline with `doca_flow_tune` — snapshotting pipe
---

# doca-flow-tune

**Description:** Use this skill when the user is tuning a live or captured `doca-flow` pipeline with `doca_flow_tune` — snapshotting pipe / counter / KPI state, picking a tuning axis (rule placement, resource hints / table sizing, HW-offload mode) and a matching measurement (rule-install rate, lookup latency, hardware-counter delta), running offline or online (read-only or state-changing) modes, reading the dumper CSV / analyze JSON / visualize mermaid, or applying a recommendation back into the Flow program. Trigger even when the user does not explicitly mention "doca_flow_tune" — typical implicit phrasings include "Flow rule-install rate is low on BlueField", "table sizing looks wrong for this pipe", "tune visualize step is empty", "before/after counters don't move", or "which doca-flow knob does this recommendation hit". Refuse and route elsewhere for measuring baseline numbers (doca-flow-perf, doca-flow-dpa-perf), writing the doca-flow application, DOCA install, or streaming Flow telemetry — those belong to other skills.

**Lines:** 369 | **Code:** 0 | **Dir:** `doca-flow-tune`

---

---
license: Apache-2.0
name: doca-flow-tune
description: >
  Use this skill when the user is tuning a live or captured
  `doca-flow` pipeline with `doca_flow_tune` — snapshotting
  pipe / counter / K...