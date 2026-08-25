---
title: physicsnemo-shard-tensor
description: Official NVIDIA-authored guidance for PhysicsNeMo ShardTensor domain parallelism — integrate domain parallelism into tra
---

# physicsnemo-shard-tensor

**Description:** Official NVIDIA-authored guidance for PhysicsNeMo ShardTensor domain parallelism — integrate domain parallelism into training/inference scripts (new or existing) with DDP or FSDP2, write and register shard patches to enable new layers/ops, and bootstrap multi-GPU correctness tests. Use when working with ShardTensor, scatter_tensor, domain parallelism, sequence/spatial sharding, ring attention, DeviceMesh + DDP/FSDP2 hybrid parallelism, or physicsnemo.domain_parallel. Do NOT use for generic PyTorch DDP/FSDP setup without domain parallelism, picking a PhysicsNeMo model or example (use physicsnemo-discover), or non-distributed training questions.
**Lines:** 252 | **Code:** 41 | **Dir:** `physicsnemo-shard-tensor`

---

---
name: physicsnemo-shard-tensor
description: Official NVIDIA-authored guidance for PhysicsNeMo ShardTensor domain parallelism — integrate domain parallelism into training/inference scripts (new or ...