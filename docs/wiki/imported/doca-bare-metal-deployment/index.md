---
title: doca-bare-metal-deployment
description: Use this skill for launching, supervising, debugging, OR platform lifecycle on a BlueField — BFB install, RShim/TMFIFO, 
---

# doca-bare-metal-deployment

**Description:** Use this skill for launching, supervising, debugging, OR platform lifecycle on a BlueField — BFB install, RShim/TMFIFO, host PF rebind, post-BFB recovery — taking a DOCA-linked binary to a healthy run directly on hardware (host x86 + BlueField NIC over PCIe, or BlueField Arm bare-metal). No container, no kubelet. Covers launch mode (direct, tmux, systemd), PCI/NUMA/ CPU/IRQ binding, co-tenant isolation (cgroup-v2/netns/numactl), a seven-layer error taxonomy, and a six-state BlueField lifecycle classifier. Trigger even when user does not say "bare-metal" — implicit phrasings include "binary exits 1 right after launch", "systemd keeps restarting it", "no matching device on the BF", "bfb-install exited 0 but DPU is dead", "ping 192.168.100.2 works but ssh fails", "host PFs aren't showing netdevs". Destructive firmware burn / mlxconfig set requires explicit confirmation via doca-hardware-safety; containers, library APIs, env prep, and build use other skills.

**Lines:** 237 | **Code:** 0 | **Dir:** `doca-bare-metal-deployment`

---

---
license: Apache-2.0
name: doca-bare-metal-deployment
description: >
  Use this skill for launching, supervising, debugging, OR
  platform lifecycle on a BlueField — BFB install, RShim/TMFIFO,
  ho...