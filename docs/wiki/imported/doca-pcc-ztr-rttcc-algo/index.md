---
title: doca-pcc-ztr-rttcc-algo
description: Use this skill when the user is doing hands-on deployment, tuning, or evaluation of the DOCA-shipped Zero-Touch RoCE RTT
---

# doca-pcc-ztr-rttcc-algo

**Description:** Use this skill when the user is doing hands-on deployment, tuning, or evaluation of the DOCA-shipped Zero-Touch RoCE RTT-based Congestion Control (ZTR RTTCC) reference algorithm on a BlueField-3 DPA — wiring `doca_pcc_dev_ztr_rttcc_algo` into the shipped DOCA PCC sample, picking a variant (vanilla / PM / RX-rate / multipath / window-probeless) at DPACC build time, tuning host-set parameters, or diagnosing `DOCA_PCC_DEV_STATUS_FAIL` from the algorithm. Trigger even when the user does not say 'DOCA PCC' or 'ZTR RTTCC' — typical implicit phrasings: 'my RoCE-v2 flows aren't being throttled', 'PCC sample isn't dispatching to my algo', 'how do I pick the multipath PCC variant', 'set-params returns fail', 'algorithm loaded but counters are flat', or 'do I need a custom CC algorithm on BF3'. Refuse and route elsewhere for writing a custom PCC algorithm from scratch, read-only PCC counter inspection, the host-side `doca-pcc` lifecycle, or firmware-only pre-Programmable PCC — those belong to other skills.

**Lines:** 403 | **Code:** 0 | **Dir:** `doca-pcc-ztr-rttcc-algo`

---

---
license: Apache-2.0
name: doca-pcc-ztr-rttcc-algo
description: >
  Use this skill when the user is doing hands-on deployment, tuning,
  or evaluation of the DOCA-shipped Zero-Touch RoCE RTT-based
...