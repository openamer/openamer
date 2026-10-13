---
title: dynamo-interconnect-check
description: Validate that a Dynamo deployment's NIXL/UCX/NCCL interconnect is ready for disaggregated serving over RDMA/NVLink. Use 
---

# dynamo-interconnect-check

**Description:** Validate that a Dynamo deployment's NIXL/UCX/NCCL interconnect is ready for disaggregated serving over RDMA/NVLink. Use after recipe-runner brings a deployment up (especially disagg/multi-node) to confirm the KV transport is correct; use troubleshoot for diagnosing already-failed pods.
**Lines:** 161 | **Code:** 13 | **Dir:** `dynamo-interconnect-check`

---

---
name: dynamo-interconnect-check
description: Validate that a Dynamo deployment's NIXL/UCX/NCCL interconnect is ready for disaggregated serving over RDMA/NVLink. Use after recipe-runner brings a de...