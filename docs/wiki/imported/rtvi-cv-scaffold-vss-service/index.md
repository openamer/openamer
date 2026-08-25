---
title: rtvi-cv-scaffold-vss-service
description: Scaffold a standalone RTVI CV microservice that plugs into VSS Search and Alerts profiles via Kafka mdx-raw. The shipped
---

# rtvi-cv-scaffold-vss-service

**Description:** Scaffold a standalone RTVI CV microservice that plugs into VSS Search and Alerts profiles via Kafka mdx-raw. The shipped scaffold script is a YOLO26 reference implementation (ONNX, labels, custom parser required). Use when building a new perception microservice repo, validating the VSS integration contract, extending that scaffold for segmentation frame-mask payloads, or scaffolding with placeholders before customer YOLO26 assets exist. For swapping the detector in the stock vss-rt-cv container, use rtvi-cv-customize-model instead. Live DeepStream integration cannot run until the customer-supplied ONNX, labels file, and parser library exist.

**Lines:** 346 | **Code:** 58 | **Dir:** `rtvi-cv-scaffold-vss-service`

---

---
name: rtvi-cv-scaffold-vss-service
description: >
  Scaffold a standalone RTVI CV microservice that plugs into VSS Search and
  Alerts profiles via Kafka mdx-raw. The shipped scaffold script is a ...