---
title: mcore-run-on-slurm
description: How to launch distributed Megatron-LM training jobs on a SLURM cluster. Covers a minimal sbatch skeleton, environment-va
---

# mcore-run-on-slurm

**Description:** How to launch distributed Megatron-LM training jobs on a SLURM cluster. Covers a minimal sbatch skeleton, environment-variable setup for torch.distributed.run, CUDA_DEVICE_MAX_CONNECTIONS rules across hardware and parallelism modes, container conventions, monitoring, and per-rank failure diagnosis.
**Lines:** 137 | **Code:** 42 | **Dir:** `mcore-run-on-slurm`

---

---
name: mcore-run-on-slurm
description: How to launch distributed Megatron-LM training jobs on a SLURM cluster. Covers a minimal sbatch skeleton, environment-variable setup for torch.distributed.run...