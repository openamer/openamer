---
title: doca-urom-svc
description: Operate the DOCA UROM Service container on BlueField Arm for remote memory operations (puts, gets, atomics, collectives)
---

# doca-urom-svc

**Description:** Operate the DOCA UROM Service container on BlueField Arm for remote memory operations (puts, gets, atomics, collectives) enqueued by a paired host using `doca-urom`: pull the NGC image, choose the UCX component, size queues, configure Comch pairing, and align host and service versions. SECURITY: the service has no standalone access control; Comch pairing and RDMA permissions are the boundary. Pair only intended hosts, expose least-privilege memory regions, and verify both views before start. Trigger for slow UCX collectives, unexpected NOT_PERMITTED, or missing completions. Do not use for host application code, MPI/UCX integration design, or DOCA install.

**Lines:** 369 | **Code:** 0 | **Dir:** `doca-urom-svc`

---

---
license: Apache-2.0
name: doca-urom-svc
description: >
  Operate the DOCA UROM Service container on BlueField Arm for remote
  memory operations (puts, gets, atomics, collectives) enqueued by a
  ...