---
title: paidf-orchestration-write-dag
description: Use when a user describes a custom PAIDF Orchestration pipeline — a specific ordered combination of stages such as augme
---

# paidf-orchestration-write-dag

**Description:** Use when a user describes a custom PAIDF Orchestration pipeline — a specific ordered combination of stages such as augmentation only, auto-labeling only, detection+captioning only, or image attribute augmentation without full auto-labeling — that no existing DAG in airflow/dags/workflows/ covers, and asks for a new Kubernetes DAG. Also use to check that a generated or existing DAG's model/container/prompt choices match an external spec document (e.g. a PAIDF `launchable.md`).
**Lines:** 496 | **Code:** 28 | **Dir:** `paidf-orchestration-write-dag`

---

---
name: paidf-orchestration-write-dag
description: Use when a user describes a custom PAIDF Orchestration pipeline — a specific ordered combination of stages such as augmentation only, auto-labeling...