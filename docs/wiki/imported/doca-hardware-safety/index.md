---
title: doca-hardware-safety
description: Use this skill whenever the agent is about to recommend or apply a change that touches DPU / NIC hardware state on a liv
---

# doca-hardware-safety

**Description:** Use this skill whenever the agent is about to recommend or apply a change that touches DPU / NIC hardware state on a live system — mlxconfig firmware-parameter write, NIC firmware burn, BFB reflash, NIC ↔ DPU mode flip, SR-IOV or device-emulation slot enable, kernel boot-parameter change (IOMMU, hugepages, VFIO), PCIe rebind / rescan / link-state flip, or BlueField cold reboot. Wraps the change in pre-flight inventory, OOB reachability, a maintenance window, the mlxconfig cold-power-cycle rule, replica rehearsal, and rollback. Trigger even when the user does not say "hardware safety" — implicit phrasings: "flip BlueField mode over SSH", "enable SR-IOV and reboot", "burned firmware but mlxconfig shows old value", "reflashed BFB and lost representors", "reflash during business hours", "vendor says this is one-way". Refuse for general DOCA orientation (doca-public-knowledge-map), install or env debug (doca-setup), and program-side debug (doca-debug, doca-programming-guide) — those belong to other skills.

**Lines:** 277 | **Code:** 0 | **Dir:** `doca-hardware-safety`

---

---
license: Apache-2.0
name: doca-hardware-safety
description: >
  Use this skill whenever the agent is about to recommend or apply a
  change that touches DPU / NIC hardware state on a live system —...