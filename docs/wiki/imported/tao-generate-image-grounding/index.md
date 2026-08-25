---
title: tao-generate-image-grounding
description: Two-step image grounding pipeline: extracts referring expressions from (image, caption) pairs and grounds them to pixel-
---

# tao-generate-image-grounding

**Description:** Two-step image grounding pipeline: extracts referring expressions from (image, caption) pairs and grounds them to pixel-space bounding boxes via a VLM. Use when the user wants to ground captions to bboxes, generate phrase-grounded annotations, auto-label images for grounding, or run the image_grounding pipeline. Triggers include 'image grounding', 'phrase grounding', 'ground captions', 'auto-label image grounding', 'image_grounding'.
**Lines:** 126 | **Code:** 7 | **Dir:** `tao-generate-image-grounding`

---

---
name: tao-generate-image-grounding
description: "Two-step image grounding pipeline: extracts referring expressions from (image, caption) pairs and grounds them
  to pixel-space bounding boxes via ...