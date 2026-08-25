---
title: tao-setup-nvidia-gpu-host
description: Host setup for TAO GPU backends. Checks and, after user approval, installs NVIDIA driver branch 580, CUDA Toolkit 13.0, 
---

# tao-setup-nvidia-gpu-host

**Description:** Host setup for TAO GPU backends. Checks and, after user approval, installs NVIDIA driver branch 580, CUDA Toolkit 13.0, and NVIDIA Container Toolkit 1.19.0 for Docker/local-Docker and Kubernetes GPU worker hosts. The `--check-only` path works on any Linux distribution; `--install` automates debian-family (Ubuntu/Debian/Pop!_OS/Mint/Zorin/Raspbian), rhel-family (Fedora/RHEL/Rocky/AlmaLinux), and suse-family (openSUSE/SLES) hosts, and prints actionable manual-install steps for everything else. Use when the user asks to "set up an NVIDIA GPU host", "check TAO Docker GPU runtime", or prepare a Kubernetes GPU worker for TAO.
**Lines:** 227 | **Code:** 23 | **Dir:** `tao-setup-nvidia-gpu-host`

---

---
name: tao-setup-nvidia-gpu-host
description: >-
  Host setup for TAO GPU backends. Checks and, after user approval, installs
  NVIDIA driver branch 580, CUDA Toolkit 13.0, and NVIDIA Container Too...