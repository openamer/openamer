# Native Windows containment (`agent/win_sandbox.py`)

> **Which file is which.** This is the *engineering record* — design, the exact
> OS mechanisms, the leak that live verification found, and what is deliberately
> not enforced. The user-facing version that ships on the docs site is
> `website/docs/user-guide/windows-sandbox.md`; keep the two in sync when the
> behaviour changes (they will drift otherwise — this note is here because that
> already happened once with the "not yet wired" status line).

Status: **wired into the local terminal backend** (opt-in, default off) —
`tools/environments/local.py` builds a job object for each command whenever
`terminal.sandbox.windows.enabled` is true, and closes it in `_kill_process()`.

## Enabling it

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

The policy is read once and cached, like the backend's other settings — a change
needs a restart. With `enabled: false` (the default) the spawn path is
byte-identical to before.

## Why this exists

Every competitor's isolation story ends at native Windows:

| Product | Windows isolation |
|---|---|
| Claude Code | **None** — the OS sandbox is unsupported; docs say "run Claude Code inside a WSL2 distribution" |
| Codex CLI | A single `sandbox = "unelevated"` fallback |
| OpenAmer (before) | Container backends (Docker/Modal/Daytona/SSH), opt-in, external runtime required; the default local terminal had no boundary |

This module adds a boundary using only primitives that need **no administrator
rights**, so it works on a stock Windows laptop.

## What is enforced — and by what

**OS-enforced (Windows Job Object):**

| Guarantee | Mechanism |
|---|---|
| Whole process tree dies when the sandbox closes — no orphaned daemons | `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE` |
| Hard cap on concurrent processes — blocks fork bombs | `JOB_OBJECT_LIMIT_ACTIVE_PROCESS` |
| Per-process and per-job memory ceiling | `JOB_OBJECT_LIMIT_PROCESS_MEMORY`, `JOB_OBJECT_LIMIT_JOB_MEMORY` |
| No clipboard read/write, no handles in other processes, no global system-parameter or desktop changes | `JOB_OBJECT_UILIMIT_*` |
| Children **cannot** escape the job | `JOB_OBJECT_LIMIT_BREAKAWAY_OK` is deliberately never set |

**Enforced in-process:**

| Guarantee | Mechanism |
|---|---|
| Credentials are absent from the child environment | `enforce_environment()` — see the leak note below |
| Writes stay inside the writable root; junctions and symlinks resolved first | `check_write_path()` |
| `.git` / `.hg` / `.svn` are never writable, even inside the root | same |
| SSH keys, `~/.aws`, `~/.gnupg`, `OPENAMER_HOME`, `.env` are never writable | `protected_paths()` |
| No writable root configured → **everything denied** | fail-closed default |

## What is *not* enforced

Stated plainly, because a security boundary is only useful if its edge is honest:

* **Network is not OS-isolated on native Windows.** Per-process egress blocking
  needs Windows Filtering Platform rules, i.e. administrator rights. Codex's
  "network off by default" comes from an OS sandbox on macOS/Linux, not from the
  user token. What we can do without admin: refuse to run at all when
  `network=deny` is requested, and inject proxy variables for clients that honour
  them. `describe_enforcement()` reports this as `partial` — never as enforced.
* **The filesystem boundary is policy, not an ACL.** It constrains the paths our
  own tools write, and it resolves junctions before comparing — but a command
  calling raw Win32 file APIs is not intercepted. ACL-level confinement requires
  a different token or an isolated backend.

`describe_enforcement()` is the single source for this, so a `/sandbox` status
surface can never advertise more than the platform delivers.

## Leak found during live verification (fixed here, noted for the other path)

`scripts/verify_win_sandbox.py` showed that the pre-existing local-backend
sanitizer (`tools/environments/local._sanitize_subprocess_env`) strips
**by name** against `_OPENAMER_PROVIDER_ENV_BLOCKLIST` plus two narrow prefixes
(`AUXILIARY_*`, `GATEWAY_RELAY_*`). Four real variables on this machine survived
it unchanged:

```
OPENAMER_MESH_SECRET  OPENAMER_SESSION_KEY  OPENVID_LLM_KEY  TOKENHARBOR_API_KEY
```

`enforce_environment()` closes that for its callers: after the existing
sanitizer runs, anything matching a credential suffix
(`_API_KEY|_KEY|_TOKEN|_SECRET|_PASSWORD|_PASSWD|_CREDENTIAL|_ACCESS_KEY|
_PRIVATE_KEY|_SESSION_KEY|APIKEY`) is dropped unless it is explicitly
allowlisted through `tools.env_passthrough` (the skill-declaration path — the one
legitimate reason a secret-shaped name needs to reach a child).

This is deliberately an **extension, not a second scrubber**: there is still
exactly one blocklist, and the other spawn paths are untouched. Those other paths
were not audited in this change — that is an open task, tracked here rather than
quietly assumed fixed.

## Verifying it yourself

```bash
python scripts/verify_win_sandbox.py     # real job object, real child process
python -m pytest tests/test_win_sandbox.py -q
```

The tests are not mock-only: they create a real job, put a real child in it, prove
the OS kills the tree when the job closes, and prove the process cap refuses a
second child. A mock would have passed the first, wrong version of this module.
