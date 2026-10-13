---
title: deepstream-sop
description: Use this skill when building, deploying, evaluating, debugging, or measuring latency for the DeepStream SOP Inference Mi
---

# deepstream-sop

**Description:** Use this skill when building, deploying, evaluating, debugging, or measuring latency for the DeepStream SOP Inference Microservice — a GPU-accelerated FastAPI service that detects whether operators perform assembly-line steps in order via event boundary detection (GEBD) plus VLM classification. Trigger even if the user does not name it: verify operator step sequence, detect missing or out-of-order SOP steps, score factory/work-cell video for procedure compliance, run VLM-based SOP checking on industrial cameras, or call /v1/chat/completions with a file, RTSP, or Basler camera. Also trigger for its internals: SOPVideoProcessor, DeepStream GEBD model (e.g. DDM) via Triton CAPI, nvds_custom_postprocess, Cosmos Reason 1/2 vLLM, SSE streaming, Kafka NvProto/JSON output, Basler/Pylon camera + emulation, Docker compose, chunk-level latency. Do NOT trigger for generic DeepStream pipelines, object detection/tracking, NIM imports, or video summarization.

**Lines:** 230 | **Code:** 46 | **Dir:** `deepstream-sop`

---

---
name: "deepstream-sop"
description: >
  Use this skill when building, deploying, evaluating, debugging, or measuring
  latency for the DeepStream SOP Inference Microservice — a GPU-accelerated
  F...