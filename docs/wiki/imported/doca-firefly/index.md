---
title: doca-firefly
description: Use this skill when the user is operating the DOCA Firefly Service container on BlueField — picking the four PTP configu
---

# doca-firefly

**Description:** Use this skill when the user is operating the DOCA Firefly Service container on BlueField — picking the four PTP configuration axes (role / profile / domain / interface), wiring the BlueField PHC + host follower + consumer workload pairing, deciding whether PTP-grade time is even needed (vs. chrony / NTP), or debugging a Firefly deployment where PTP isn't syncing or the host clock isn't following. Trigger even when the user does not explicitly mention "DOCA Firefly" or "PTP" — typical implicit phrasings include "container green but PTP never advances past LISTENING", "Firefly says synced but the host clock still drifts", "sync acquired but offset is tens of microseconds", "my Rivermax SMPTE workload needs PTP", or "is chrony good enough". Refuse and route elsewhere for installing DOCA, host-side chrony / ptp4l config bodies, PTP topology / boundary-clock design, building DOCA apps that read the disciplined PHC, or other DOCA services (DMS, Flow-Inspector, HBN) — those belong to other skills.

**Lines:** 346 | **Code:** 0 | **Dir:** `doca-firefly`

---

---
license: Apache-2.0
name: doca-firefly
description: >
  Use this skill when the user is operating the DOCA Firefly Service
  container on BlueField — picking the four PTP configuration axes
  (rol...