---
title: nemotron-asr-finetune
description: Orchestration skill for NVIDIA Nemotron Speech (Riva) / NeMo ASR domain and language adaptation. Given a goal like "impr
---

# nemotron-asr-finetune

**Description:** Orchestration skill for NVIDIA Nemotron Speech (Riva) / NeMo ASR domain and language adaptation. Given a goal like "improve/fine-tune ASR for my domain or language", it scopes the task, picks the cheapest sufficient path (word boosting → n-gram LM → fine-tuning), delegates each stage to the right sub-skill (data generation, training, evaluation, deployment), and answers cost/time/data questions along the way.
**Lines:** 132 | **Code:** 0 | **Dir:** `nemotron-asr-finetune`

---

---
name: "nemotron-asr-finetune"
description: Orchestration skill for NVIDIA Nemotron Speech (Riva) / NeMo ASR domain and language adaptation. Given a goal like "improve/fine-tune ASR for my domain o...