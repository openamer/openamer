---
title: hf-cloud-sagemaker-deployment-planner
description: Plan and coordinate the deployment of a model to Amazon SageMaker AI. Use this skill whenever the user wants to deploy, 
---

# hf-cloud-sagemaker-deployment-planner

**Description:** Plan and coordinate the deployment of a model to Amazon SageMaker AI. Use this skill whenever the user wants to deploy, host, serve, or expose a model on SageMaker or AWS — including phrases like "deploy a model", "host this LLM on AWS", "serve this embedding model", "deploy a reranker", "deploy a text-to-image / diffusion model", "host this for async inference", "create an endpoint", "serve my fine-tuned model", or any request that involves making a model available for inference on AWS. Use this even when the user is vague (e.g. "I just want to get this running on AWS, you figure it out"). Works for text-generation LLMs, embedding models, rerankers, classifiers, text-to-image / diffusion models — picks the right serving stack and chooses between real-time and async inference. This is the entry-point skill for SageMaker deployment work — it asks clarifying questions, picks a deployment pathway, and coordinates the other deployment skills.
**Lines:** 91 | **Code:** 3 | **Dir:** `hf-cloud-sagemaker-deployment-planner`

---

---
name: hf-cloud-sagemaker-deployment-planner
description: 'Plan and coordinate the deployment of a model to Amazon SageMaker AI. Use this skill whenever the user wants to deploy, host, serve, or ex...