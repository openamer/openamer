---
title: tao-setup-nvidia-gpu-host
description: Host setup for TAO GPU backends. Checks and, after user approval, installs minimum-compatible NVIDIA driver, CUDA Toolki
---

# tao-setup-nvidia-gpu-host

**Description:** Host setup for TAO GPU backends. Checks and, after user approval, installs minimum-compatible NVIDIA driver, CUDA Toolkit, and NVIDIA Container Toolkit versions for Docker/local-Docker and Kubernetes GPU worker hosts. TAO-wide defaults can be overridden by the selected model's runtime profile. The `--check-only` path works on any Linux distribution; `--install` automates debian-family (Ubuntu/Debian/Pop!_OS/Mint/Zorin/Raspbian), rhel-family (Fedora/RHEL/Rocky/AlmaLinux), and suse-family (openSUSE/SLES) hosts, and prints actionable manual-install steps for everything else. Use when the user asks to "set up an NVIDIA GPU host", "check TAO Docker GPU runtime", or prepare a Kubernetes GPU worker for TAO.
**Lines:** 250 | **Code:** 29 | **Dir:** `tao-setup-nvidia-gpu-host`

---

---
name: tao-setup-nvidia-gpu-host
description: >-
  Host setup for TAO GPU backends. Checks and, after user approval, installs
  minimum-compatible NVIDIA driver, CUDA Toolkit, and NVIDIA Container ...