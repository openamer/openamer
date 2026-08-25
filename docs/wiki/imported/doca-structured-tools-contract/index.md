---
title: doca-structured-tools-contract
description: Use this skill whenever another DOCA skill says "prefer the structured tool per doca-structured-tools-contract", or when
---

# doca-structured-tools-contract

**Description:** Use this skill whenever another DOCA skill says "prefer the structured tool per doca-structured-tools-contract", or when the user wants a one-shot answer that consolidates info multiple manual commands would produce — DOCA env / version / devices / capabilities / validate / host vs DPU state. Trigger even when the user does not explicitly mention "structured tool" or "doca-env --json" — typical implicit phrasings include "is there one command that tells me everything about my DOCA install", "what version is X capability available since", "every PF/VF/SF visible on this BlueField with PCIe address", "will this pipe pass validate before commit", "diff host vs DPU state", or "why does the agent give a one-line answer on host A and five commands on host B". Refuse and route elsewhere for general DOCA orientation, specific library API how-to, or install-from-scratch guidance — those belong to the per-library skill, doca-public-knowledge-map, or doca-setup.

**Lines:** 381 | **Code:** 0 | **Dir:** `doca-structured-tools-contract`

---

---
license: Apache-2.0 AND CC-BY-4.0
name: doca-structured-tools-contract
description: >
  Use this skill whenever another DOCA skill says "prefer the
  structured tool per doca-structured-tools-cont...