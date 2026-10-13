---
sidebar_position: 13
title: "Windows sandbox"
description: "Native Windows containment for local terminal commands: a job object that kills the process tree, caps processes and memory, and isolates the clipboard."
---

# Windows sandbox (native, no admin)

Local terminal commands run through a Windows **job object** when this is
enabled. That needs no administrator rights, so it works on a stock Windows
laptop.

## Why it exists

Every other agent's isolation story stops at native Windows:

| Product | Windows isolation |
|---|---|
| Claude Code | **None** — the OS sandbox is unsupported there ("run Claude Code inside a WSL2 distribution") |
| Codex CLI | a single `sandbox = "unelevated"` fallback |
| OpenAmer (before) | container backends only (Docker/Modal/Daytona/SSH), opt-in and requiring an external runtime — the default local terminal had no boundary |

## Enable it

```yaml
# ~/.openamer/config.yaml
terminal:
  sandbox:
    windows:
      enabled: true
      writable_root: "C:/Users/me/projects/thing"   # empty = no write boundary claimed
      max_processes: 64
      max_memory_mb: 4096
      fail_closed: true      # kill rather than run uncontained
      strip_secrets: true
```

Read once per session and cached. With `enabled: false` (the default) command
spawning is unchanged.

## What is actually enforced

**By the OS (job object):**

| Guarantee | Mechanism |
|---|---|
| The whole process tree dies when the sandbox closes — no orphaned daemons | `KILL_ON_JOB_CLOSE` |
| Hard cap on concurrent processes (blocks fork bombs) | `ACTIVE_PROCESS` |
| Per-process and per-job memory ceiling | `PROCESS_MEMORY`, `JOB_MEMORY` |
| No clipboard read/write, no handles into other processes, no global parameter or desktop changes | `UILIMIT_*` |
| Children cannot leave the job | `BREAKAWAY_OK` is never granted |

**By OpenAmer:**

| Guarantee | Mechanism |
|---|---|
| Credentials absent from the child environment | credential-suffix filter layered on the existing sanitizer |
| Writes stay inside `writable_root`; junctions and symlinks resolved first | path boundary check |
| `.git` / `.hg` / `.svn` never writable, even inside the root | protected paths |
| `~/.ssh`, `~/.aws`, `~/.gnupg`, `.env`, `OPENAMER_HOME` never writable | protected paths |
| No writable root configured → everything denied | fail-closed default |
| A command that cannot be contained is **killed**, not run uncontained | `fail_closed: true` |

## What is *not* enforced

* **Network is not OS-isolated on native Windows.** Blocking egress per process
  needs Windows Filtering Platform rules, which require administrator rights.
  Proxy-honouring clients can be routed; everything else is not intercepted.
* **The filesystem boundary is policy, not an ACL.** It constrains the paths
  OpenAmer writes and resolves junctions before comparing, but a command using
  raw Win32 file APIs is not intercepted.

`agent/win_sandbox.py:describe_enforcement()` returns exactly this, with the
network row marked `partial` — so no status surface can advertise more than the
platform delivers.

## Verifying it on your machine

```bash
python scripts/verify_win_sandbox.py
python -m pytest tests/test_win_sandbox.py -q
```

The tests are not mock-only: they create a real job object, put a real child
process inside it, and prove the OS kills the tree when the job closes and
refuses a second child under a one-process cap.

## A pre-existing leak this closed

Live verification showed the existing local-backend sanitizer strips **by name**
against a known provider blocklist — and four real variables rode straight
through it: `OPENAMER_MESH_SECRET`, `OPENAMER_SESSION_KEY`, `OPENVID_LLM_KEY`,
`TOKENHARBOR_API_KEY`. The sandbox path now also drops anything matching a
credential suffix, unless it is explicitly allowlisted through
`terminal.env_passthrough` or a skill declaration.

The other spawn paths were not audited in that change — recorded as open rather
than assumed fixed.
