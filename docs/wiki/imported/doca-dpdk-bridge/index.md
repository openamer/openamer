---
title: doca-dpdk-bridge
description: Use this skill when the user has an existing DPDK application and is adding DOCA capabilities in-place — most commonly D
---

# doca-dpdk-bridge

**Description:** Use this skill when the user has an existing DPDK application and is adding DOCA capabilities in-place — most commonly DOCA Flow hardware steering — without rewriting the data-plane in DOCA-native form: binding a DPDK port id to a `doca_dev` (`doca_dpdk_port_probe` / `doca_dpdk_port_as_dev`), converting `rte_mbuf` ↔ `doca_buf`, querying `doca_dpdk_cap_is_rep_port_supported`, or debugging `DOCA_ERROR_*` from a bridge call. Trigger even without "DOCA DPDK Bridge": "how do I add DOCA Flow to my DPDK app", "make a DPDK port visible to DOCA", "the bridge loads but every operation returns errors", "pkg-config --exists doca-dpdk-bridge fails", or "DOCA_ERROR_NOT_FOUND on port registration". Route elsewhere for fresh DOCA-native packet I/O (doca-eth), flow-rule programming (doca-flow), DOCA or DPDK install (doca-setup), or RDMA data movement (doca-rdma).

**Lines:** 303 | **Code:** 0 | **Dir:** `doca-dpdk-bridge`

---

---
license: Apache-2.0
name: doca-dpdk-bridge
description: >
  Use this skill when the user has an existing DPDK application and is
  adding DOCA capabilities in-place — most commonly DOCA Flow hardw...