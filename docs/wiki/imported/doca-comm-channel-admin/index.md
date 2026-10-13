---
title: doca-comm-channel-admin
description: Use this skill to enumerate host↔DPU DOCA comch (formerly Comm Channel) servers and connections via the shipped doca_com
---

# doca-comm-channel-admin

**Description:** Use this skill to enumerate host↔DPU DOCA comch (formerly Comm Channel) servers and connections via the shipped doca_comm_channel_admin binary — listing comch-capable devices and decoding the per-device server / connection table (server name, PID, in-use / max, PCIe address). The shipped binary is a SINGLE-SHOT SCAN-AND-PRINT tool with no registered arguments — NO list / inspect / drain / restart subcommands; one inventory pass over every comch-capable doca_dev on this side. Channel reset / drain / restart go to doca-comch (program side), doca-setup / doca-hardware-safety (driver reload), or BFB / RShim — NOT to this binary. Trigger on phrasings like "list comch servers", "which channels are active on this BlueField", or "verify admin tool sees same channel as program." Refuse and route elsewhere for the comch programming API, library install, protocol design, channel reset, or general orientation.

**Lines:** 253 | **Code:** 0 | **Dir:** `doca-comm-channel-admin`

---

---
license: Apache-2.0
name: doca-comm-channel-admin
description: >
  Use this skill to enumerate host↔DPU DOCA comch (formerly
  Comm Channel) servers and connections via the shipped
  doca_comm_cha...