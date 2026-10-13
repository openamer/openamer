---
title: doca-eth
description: Use this skill for hands-on DOCA Ethernet packet-queue work on a BlueField DPU or ConnectX NIC — bringing up a `doca_eth
---

# doca-eth

**Description:** Use this skill for hands-on DOCA Ethernet packet-queue work on a BlueField DPU or ConnectX NIC — bringing up a `doca_eth_rxq` or `doca_eth_txq` on a port / representor / SF, picking among the four `enum doca_eth_rxq_type` values (`_REGULAR` / `_CYCLIC` / `_MANAGED_MEMPOOL` / `_SHARED_MEMPOOL`), sizing burst or scatter-gather length against the `_cap_*` queries, submitting `doca_eth_txq_task_send` / `_lso_send` (carrying packet `doca_buf`s — no `doca_eth_frame` struct exists), or debugging DOCA_ERROR_* from an Ethernet call. Trigger on implicit phrasings: "my RX queue is up but no packets arrive", "send-task returns AGAIN at line rate", "which queue type for fixed-MTU ingress", "device open fails without sudo", or "is L3 checksum offload available here". Refuse and route elsewhere for installing DOCA, flow-rule / steering programming, host↔DPU control messaging, or RDMA data movement.

**Lines:** 279 | **Code:** 0 | **Dir:** `doca-eth`

---

---
license: Apache-2.0
name: doca-eth
description: >
  Use this skill for hands-on DOCA Ethernet packet-queue work
  on a BlueField DPU or ConnectX NIC — bringing up a
  `doca_eth_rxq` or `doca_eth_t...