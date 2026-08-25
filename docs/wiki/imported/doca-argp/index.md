---
title: doca-argp
description: Use this skill for hands-on DOCA Arg Parser CLI work on a shipped sample or new DOCA-using app — adding / removing / ren
---

# doca-argp

**Description:** Use this skill for hands-on DOCA Arg Parser CLI work on a shipped sample or new DOCA-using app — adding / removing / renaming flags; wiring `doca_argp_init` → register params → `doca_argp_start` → `doca_argp_destroy` in order; picking a parameter type from the full public enum (`DOCA_ARGP_TYPE_STRING`, `_INT`, `_BOOLEAN`, `_DEVICE`, `_DEVICE_REP`, `_DOUBLE` — six values, not three); preserving the standard `--device` / `--representor` / `--json` (`-j`; real flag is `--json`, NOT `--json-config`) / `--sdk-log-level` surface; or debugging `DOCA_ERROR_BAD_STATE` / `INVALID_VALUE` / `NOT_SUPPORTED` / `IO_FAILED` from `doca_argp_*`. Trigger on implicit phrasings: "add a custom flag to a DOCA sample", "should I use getopt here", "BAD_STATE registering a new param", "my JSON config key is rejected", or "my sample's --json is ignored". Refuse and route elsewhere for variadic-flag / subcommand / shell-completion features, DOCA Core context, or DOCA Log internals.

**Lines:** 266 | **Code:** 0 | **Dir:** `doca-argp`

---

---
license: Apache-2.0
name: doca-argp
description: >
  Use this skill for hands-on DOCA Arg Parser CLI work on a
  shipped sample or new DOCA-using app — adding / removing /
  renaming flags; wiring...