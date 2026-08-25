---
title: doca-rdmi
description: Use this skill when the user is doing hands-on DOCA RDMI (RDMA Initiator) programming — picking doca-rdmi vs doca-rdma f
---

# doca-rdmi

**Description:** Use this skill when the user is doing hands-on DOCA RDMI (RDMA Initiator) programming — picking doca-rdmi vs doca-rdma for an accelerator-initiated one-sided RDMA flow, standing up a doca_rdmi_connection or doca_rdmi_poster, attaching a doca_dpa_completion or doca_verbs_cq before doca_ctx_start(), retrieving the DPA-side handle for a DPA kernel, auditing whether a doca_rdmi_* symbol is EXPERIMENTAL on this DOCA, or debugging DOCA_ERROR_* returns from RDMI calls. Trigger even when the user does not say "DOCA RDMI" or "initiator" — implicit phrasings include "my DPA kernel needs to post RDMA writes to a remote responder", "DPA kernel sees no completions", "function not found on doca_rdmi_* at link time", "DOCA_ERROR_BAD_STATE from completion attach", or "the DPA posted but the work request never arrived". Refuse and route elsewhere for two-sided or host-CPU RDMA, the DPA programming model, GPU-side RDMA initiation, or general RDMA/IB/RoCE concepts — those belong to other skills.

**Lines:** 301 | **Code:** 0 | **Dir:** `doca-rdmi`

---

---
license: Apache-2.0
name: doca-rdmi
description: >
  Use this skill when the user is doing hands-on DOCA RDMI (RDMA
  Initiator) programming — picking doca-rdmi vs doca-rdma for an
  accelerator-i...