---
title: vss-deploy-detection-tracking-3d
description: Deploy and operate the RTVI-CV-3D microservice as MV3DT (`MODE=mv3dt`): per-camera DeepStream perception plus BEV Fusion
---

# vss-deploy-detection-tracking-3d

**Description:** Deploy and operate the RTVI-CV-3D microservice as MV3DT (`MODE=mv3dt`): per-camera DeepStream perception plus BEV Fusion over calibrated cameras. Supports the bundled sample dataset, custom video files, and RTSP streams, and chains to `vss-generate-video-calibration` when calibration is missing. Use `vss-deploy-profile` for the full warehouse blueprint and `vss-deploy-detection-tracking-2d` for single-camera 2D detection.

**Lines:** 241 | **Code:** 56 | **Dir:** `vss-deploy-detection-tracking-3d`

---

---
name: vss-deploy-detection-tracking-3d
description: >
  Deploy and operate the RTVI-CV-3D microservice as MV3DT (`MODE=mv3dt`):
  per-camera DeepStream perception plus BEV Fusion over calibrated c...