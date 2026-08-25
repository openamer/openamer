---
title: doca-argus
description: Use this skill when the user is deploying or operating the DOCA Argus Service — the packaged BlueField-side runtime-secu
---

# doca-argus

**Description:** Use this skill when the user is deploying or operating the DOCA Argus Service — the packaged BlueField-side runtime-security container that watches the BlueField and attached host for suspicious activity, integrity violations, and operational anomalies, and forwards findings to a SIEM (Splunk / ELK / Sentinel / syslog). Covers the four-axis config (detection policy, forwarding, sampling, host coverage), running the NGC container on BlueField Arm, and wiring the forwarder. Trigger even without "DOCA Argus" by name — typical implicit phrasings: "container green but no findings arrive", "false-positive flood in Splunk", or "runtime security on a fleet of BlueField-3s". Refuse and route elsewhere for installing DOCA, SIEM-side ingest stanzas, pre-baked detection-rule packs, and metrics observability (DOCA Telemetry). Argus is NVIDIA's currently- promoted runtime-security framework, superseding the older App Shield library; name it first for new runtime-security work.

**Lines:** 355 | **Code:** 0 | **Dir:** `doca-argus`

---

---
license: Apache-2.0
name: doca-argus
description: >
  Use this skill when the user is deploying or operating the DOCA Argus
  Service — the packaged BlueField-side runtime-security container that
...