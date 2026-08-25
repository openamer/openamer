---
title: doca-pcc-counters
description: Use this skill when the user is invoking the DOCA PCC Counters tool — the `pcc_counters.sh` bash script under the DOCA t
---

# doca-pcc-counters

**Description:** Use this skill when the user is invoking the DOCA PCC Counters tool — the `pcc_counters.sh` bash script under the DOCA tools directory — to arm and read the fixed firmware/hardware PCC (Programmable Congestion Control) diagnostic counters (CNP, RTT, WRED-drop, etc.) on a ConnectX / BlueField device via mst + the mlx5 debugfs `diag_cnt` interface. The script takes two positional args — `set | query` and an mst device path — with no `--help` or subcommands. Trigger even without "pcc_counters.sh" or "PCC counters": "how do I read the CNP / RTT / WRED-drop counters", "PCC counter stuck at zero", "the script says Bad Device", or "is congestion control dropping packets on this port?". Route elsewhere for writing a custom PCC algorithm (doca-pcc), factory firmware PCC config, DOCA install, or fleet-wide CC tuning.

**Lines:** 258 | **Code:** 0 | **Dir:** `doca-pcc-counters`

---

---
license: Apache-2.0
name: doca-pcc-counters
description: >
  Use this skill when the user is invoking the DOCA PCC Counters tool
  — the `pcc_counters.sh` bash script under the DOCA tools director...