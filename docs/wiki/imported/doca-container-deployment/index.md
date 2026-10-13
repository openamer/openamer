---
title: doca-container-deployment
description: Use this skill when the user is hands-on deploying an in-bundle DOCA service container (Argus, DMS, Firefly, or UROM ser
---

# doca-container-deployment

**Description:** Use this skill when the user is hands-on deploying an in-bundle DOCA service container (Argus, DMS, Firefly, or UROM service) on a BlueField — kubelet standalone watching a static-pod manifests directory, YAML pod-spec drop, kubelet status / ENTRYPOINT logs / per-service liveness, smoke-before-bulk, and the layered error taxonomy (pod-spec, scheduling, image pull, runtime, mount, network, version, host). Trigger even when the user does not say "container deployment" — typical implicit phrasings include "how do I run my built service on the BlueField?", "where do I drop the pod-spec YAML?", "pod stuck in Pending / ImagePullBackOff / CrashLoopBackOff", "container Running but service isn't ready", "pod restart-loops after edit", or "DMS and Firefly together". Refuse and route elsewhere for per-service config schemas, DOCA install, library-API questions, external NVIDIA services (BlueMan, HBN, SNAP, Virtio-net), or full Kubernetes-cluster ops — those belong to other skills.

**Lines:** 195 | **Code:** 0 | **Dir:** `doca-container-deployment`

---

---
license: Apache-2.0
name: doca-container-deployment
description: >
  Use this skill when the user is hands-on deploying an in-bundle DOCA
  service container (Argus, DMS, Firefly, or UROM service)...