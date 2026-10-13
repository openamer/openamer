---
title: tao-generate-referring-expressions
description: Four-step image referring-expression pipeline: turns images plus KITTI bounding-box labels into region descriptions, sce
---

# tao-generate-referring-expressions

**Description:** Four-step image referring-expression pipeline: turns images plus KITTI bounding-box labels into region descriptions, scene captions, grounded referring expressions, and (optionally) verified expressions via VLM distillation. Use when the user wants to generate referring-expression annotations from images with KITTI labels, build region descriptions, produce grouped grounding phrases tied to bboxes, run a double-check verification pass on grounding expressions, auto-label traffic / scene images for referring datasets, or run the image_referring_expression pipeline. Triggers include 'referring expression', 'region description', 'KITTI labels', 'spatial relationship annotation', 'auto-label image referring expression', 'image_referring_expression'.
**Lines:** 146 | **Code:** 8 | **Dir:** `tao-generate-referring-expressions`

---

---
name: tao-generate-referring-expressions
description: "Four-step image referring-expression pipeline: turns images plus KITTI bounding-box labels into region
  descriptions, scene captions, ground...