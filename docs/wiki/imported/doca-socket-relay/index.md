---
title: doca-socket-relay
description: Use this skill when the operator is driving the DOCA Socket Relay to bridge a socket-oriented host application onto a Bl
---

# doca-socket-relay

**Description:** Use this skill when the operator is driving the DOCA Socket Relay to bridge a socket-oriented host application onto a BlueField DPU peer without rewriting it — picking the deployment shape (in-process, sidecar, or BlueField service container), configuring the host-side socket and the DPU-side forwarding endpoint, walking the bind → connect → round-trip → admit-fleet smoke, or diagnosing a stuck/silent relay. Trigger even when the user does not explicitly mention "DOCA Socket Relay" — typical implicit phrasings include "move my socket app onto the BlueField without rewriting it", "host app gets ECONNREFUSED on the relay", "relay accepts the connection but bytes never arrive on the DPU side", "first round-trip works, the rest hang", "bridge an AF_UNIX (UDS) socket to a DPU peer over Comch", or "I want a sidecar that forwards my socket to the BlueField". Refuse and route elsewhere for the comch programming API, line-rate raw packet I/O via doca-eth, and DOCA install/bring-up — those belong to other skills.

**Lines:** 305 | **Code:** 0 | **Dir:** `doca-socket-relay`

---

---
license: Apache-2.0
name: doca-socket-relay
description: >
  Use this skill when the operator is driving the DOCA Socket Relay
  to bridge a socket-oriented host application onto a BlueField DPU
 ...