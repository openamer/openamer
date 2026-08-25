---
title: doca-dms
description: Operate NVIDIA DOCA Management Service (`dmsd` + `dmspe`) on a BlueField, Arm/x86 host, or Kubernetes pod: choose deploy
---

# doca-dms

**Description:** Operate NVIDIA DOCA Management Service (`dmsd` + `dmspe`) on a BlueField, Arm/x86 host, or Kubernetes pod: choose deployment and authentication, configure `-allowed_users` and `dmsgroup`, use gNMI Get/Set/Subscribe, run supported gNOI workflows, and debug frontend/backend failures. Trigger even without "DMS" for "manage a remote BlueField over gRPC", "gNOI reboot from orchestrator", or fleet-management requests. SAFETY: reboot, OS install, factory-reset, and managed-file deletion are destructive and require target-bound explicit confirmation; never invoke them speculatively. Route installation and library/API build questions elsewhere, and route turnkey aggregation to the externally-productized DOCA Telemetry Service.

**Lines:** 221 | **Code:** 0 | **Dir:** `doca-dms`

---

---
license: Apache-2.0
name: doca-dms
description: >
  Operate NVIDIA DOCA Management Service (`dmsd` + `dmspe`) on a
  BlueField, Arm/x86 host, or Kubernetes pod: choose deployment and
  authenticat...