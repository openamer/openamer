---
title: doca-upgrade
description: Use this skill when the user is contemplating a DOCA upgrade or downgrade — moving a host to a newer DOCA release, refre
---

# doca-upgrade

**Description:** Use this skill when the user is contemplating a DOCA upgrade or downgrade — moving a host to a newer DOCA release, refreshing the BlueField BFB, bumping the NGC DOCA container tag, or rolling back. The discipline is detect → report → ASK → only-then guided upgrade: detect what is installed, discover what newer release exists, report the gap, then STOP and ask for explicit confirmation — never upgrade automatically. Trigger even without the word "upgrade": "is there a newer DOCA", "should I move to the next release", "I want the latest features", "my component is being deprecated, what now", or "roll me back". Route elsewhere for version detection (doca-version), first-time install (doca-setup), any hardware/firmware/reboot step (doca-hardware-safety), and public-docs / sunset routing (doca-public-knowledge-map).

**Lines:** 244 | **Code:** 0 | **Dir:** `doca-upgrade`

---

---
license: Apache-2.0
name: doca-upgrade
description: >
  Use this skill when the user is contemplating a DOCA upgrade or
  downgrade — moving a host to a newer DOCA release, refreshing the
  BlueFi...