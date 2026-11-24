# Wave-lag repair — 3 missing modules, 340 red tests (2026-09-16)

Full transcript-level detail for the "wave-lag" class in SKILL.md. A port wave
landed callers but not the modules/names they import; the result reads as hundreds
of unrelated failures with one root shape.

## How the tree was surveyed

The full canonical suite (~78 min, 32 workers) gave the census, not the verdict:

```
2426 files · 43.422 passed · 1246 failed · 4686s
```

Classifying by **import error**, not by path, collapsed the noise immediately:

```bash
grep -ohE "ModuleNotFoundError: No module named '[^']*'" /tmp/full_suite.log \
  | sort | uniq -c | sort -rn | head
```

```
300  gateway.platforms.base_exec_approval     ← real port lag (fixed)
 33  tools.terminal_scope                     ← real port lag (fixed)
 24  acp                                      ← runner flake, see below
 16  _curses                                  ← POSIX-only, unfixable on Windows
 12  mcp                                      ← runner flake
  7  tools.kanban_tools                       ← real port lag (fixed)
  3  termios / fcntl                          ← POSIX-only, unfixable on Windows
```

**Lesson: one `grep` over module names beats reading 1246 failure blocks.** Group
the census by exception text, then attribute each group once.

## The three real gaps

All three existed in upstream and were absent here; all three ported clean.

| Module | Lines | Red tests | Ported with |
|---|---|---|---|
| `gateway/platforms/base_exec_approval.py` | 43 | 300 | `port_from_upstream.py` |
| `tools/terminal_scope.py` | 223 | 33 | `port_from_upstream.py` |
| `tools/kanban_tools.py` | 1030 | 7 | `port_from_upstream.py` |

```bash
for f in gateway/platforms/base_exec_approval.py tools/terminal_scope.py tools/kanban_tools.py; do
  .venv/Scripts/python.exe scripts/port_from_upstream.py --file "$f" --dry-run   # then without
done
grep -ci hermes <each file>          # must be 0 — the tool enforces this, verify anyway
```

## The prerequisite that was missing here

`tools/kanban_tools.py` imports `no_cache_check_fn` from `tools.registry`. OpenAmer's
registry had the whole `check_fn` TTL-cache machinery (`_check_fn_cache`,
`_check_fn_last_good`, `_check_fn_cached`, `invalidate_check_fn_cache`) but **not**
this decorator. Upstream's version:

```python
_NO_CACHE_CHECK_FNS: Set[Callable] = set()

def no_cache_check_fn(fn: Callable) -> Callable:
    """Mark a local, config-backed availability check as uncached."""
    _NO_CACHE_CHECK_FNS.add(fn)
    return fn
```

plus an early branch in `_check_fn_cached`:

```python
if fn in _NO_CACHE_CHECK_FNS:
    try:
        return bool(fn())
    except Exception:
        logger.warning("check_fn %s raised; ...", getattr(fn, "__qualname__", fn), exc_info=True)
        return False
```

**Why it matters semantically:** a config-backed gate (kanban toolset on/off) changes
the instant the user flips a setting. Cached for the check_fn TTL, the tool stays
invisible for that whole window after being enabled. Port the *effect*, not a no-op stub.

## The chain that followed (name-level gaps, same class)

After the three modules imported, the gateway suite still showed 7 collection errors —
each fix revealing the next link:

```
tests/gateway/test_feishu_comment.py:8
  plugins/platforms/feishu/__init__.py:1
    plugins/platforms/feishu/adapter.py:86
      ImportError: cannot import name 'ExecApprovalPrompt' from 'gateway.platforms.base'
```

Resolved in order, each by hand (name-level, so **not** a whole-file port):

1. **`ExecApprovalPrompt`** — a plain `@dataclass` (chat_id, session_key, text,
   actions, command, description, smart_denied, metadata=None; `choices` property).
   Upstream has it in `base.py`; OpenAmer had it nowhere. Added before
   `class BasePlatformAdapter`.
2. **The exec-approval method block** — `send_exec_approval`, `_send_exec_approval_prompt`,
   `_format_exec_approval`, `_exec_approval_actions`, `supports_exec_approval_buttons`,
   `_truncate_preview`, `_ea_escape`, `_exec_approval_cmd_budget`, `_ea_deadline_line`,
   and the 8 `_EA_*` class attributes. Three adapters
   (`relay`, `whatsapp_cloud`, `qqbot`) already *implemented* `send_exec_approval`,
   and `gateway/run.py` already *called* it via `getattr(type(adapter), ...)` —
   only the base was missing. Anchored the insert just before the existing
   `send_slash_confirm`.
3. **Three async cache wrappers** — `cache_{image,audio,document}_from_bytes_async`.
   OpenAmer had the sync forms; upstream's async forms are one-liners:
   `return await asyncio.to_thread(cache_<kind>_from_bytes, data, ext)`. Added each
   directly after its sync counterpart.
4. **`gateway/platforms/event.py`** — resolved as a **re-export shim**, not a port.
   Upstream extracted `MessageEvent` / `MessageType` / `ProcessingOutcome` into this
   leaf module **and reordered the fields** (`user_id`/`user_name` at positions 3–4;
   this tree has `source` there). Verbatim-copying it would have shifted the **11
   positional** `MessageEvent(...)` call sites, and defining the classes in both
   places would have created **two distinct class objects** (`isinstance` False
   across import paths). The shim keeps one definition reachable two ways:

   ```python
   from gateway.platforms.base import (  # noqa: F401
       MessageEvent, MessageType, ProcessingOutcome)
   __all__ = ["MessageEvent", "MessageType", "ProcessingOutcome"]
   ```

   Verified with identity, not equality: `A is B` and `isinstance(A(text="x"), B)`.

   Census that informed it — keyword callers are order-safe, positional are not:

   ```
   MessageEvent construction:  keyword 325  |  POSITIONAL 11
   positional sites: gateway/run.py, gateway/wake.py, gateway/platforms/signal.py,
                     gateway/platforms/qqbot/adapter.py, plugins/platforms/email/...,
                     plugins/platforms/simplex/..., tests/gateway/test_voice_command.py
   user_id / user_name reads:  193 / 56 — ALL on SessionSource or config objects,
                     ZERO on the event object, so omitting those fields loses nothing
   ```

   That last line is why the shim is the *correct* answer rather than a compromise:
   the fields upstream added have no consumer here.

## Six modules ported in the follow-up wave

After the name-level chain, a static census replaced one-at-a-time discovery and
found 9 unresolvable modules; 6 needed porting and 3 needed only a symbol.

```bash
for f in gateway/platforms/_shared.py gateway/platforms/shared_ingress.py \
         gateway/hosted_rooms_common.py gateway/hosted_room_execution_policy.py \
         gateway/lifecycle_ledger.py gateway/memory_status.py; do
  .venv/Scripts/python.exe scripts/port_from_upstream.py --file "$f"
done
```

`port_from_upstream.py` **refuses to overwrite an existing file** (`REFUSING to
overwrite existing file: gateway/restart_loop_guard.py (delete/symbol-port it
instead)`) — that refusal is the signal you have a *name-level* gap, not a module
gap. `hosted_rooms_common.py` itself needed porting because
`hosted_room_execution_policy.py` imports it: porting a module can reveal the next.

Symbols added in place (all confirmed present upstream first):

| File | Symbol |
|---|---|
| `gateway/platforms/base.py` | `gateway_trust_env`, `_config_section`, `transcode_to_ogg_opus` (+ `contextlib`/`tempfile` imports) |
| `gateway/run.py` | `_multiplex_profile_homes`, `_load_profile_secret_scope`, `_async_profile_runtime_scope` (+ `asynccontextmanager`) |
| `gateway/wake.py` | `WakeNotAccepted` |

**Two divergences from upstream were required** and are documented inline in the
code so the next agent doesn't "restore" them:

- `_profile_runtime_scope` here already builds its own secret scope — there is no
  `prepared_secret_scope` parameter, so `_async_profile_runtime_scope` passes only
  the home.
- `openamer_cli.env_loader.hydrate_profile_secret_sources` does not exist in this
  tree; `_load_profile_secret_scope` builds the scope directly.

**False positive to expect:** `from gateway import restart_loop_guard` reported
missing while the real import works. The submodule attribute only exists on the
package after something imports it. Always re-test a single hit for real before
"fixing" it.

## After the port: the fix is not live until the RUNTIME tree has it

The installed tree (`$OPENAMER_HOME/openamer-agent`) is what actually runs; it was
**45 commits behind** the repo. Porting into the repo alone changes nothing at
runtime — and the earlier session log showed exactly this symptom:

```
Failed to load plugin 'feishu-platform': No module named 'gateway.platforms.base_exec_approval'
Failed to load plugin 'homeassistant-platform': cannot import name 'gateway_trust_env'
```

Sync **scoped paths**, never a whole-tree checkout (the runtime tree is dirty with
unrelated in-flight work, which is also why the auto-sync cron declines):

```bash
cd "$OPENAMER_HOME/openamer-agent"
git fetch origin main
git status --short gateway/            # must be empty for the paths you take
git checkout origin/main -- <explicit file list>
```

Then prove it at the level the user cares about — the plugins that failed to load:

```bash
./venv/Scripts/python.exe -c "
import sys; sys.path.insert(0,'.')
for m in ['plugins.platforms.feishu.adapter','plugins.platforms.homeassistant.adapter']:
    try: __import__(m); print('OK  ', m)
    except Exception as e: print('FAIL', m, type(e).__name__, e)
"
```

`git checkout origin/main -- <paths>` applies the repo's EOL policy correctly;
a straight `cp` between trees does not (the runtime copy here is LF where the repo
is CRLF, so a copy flips every line ending and inflates the diff).

## Verifying a name-level addition: behaviour, not import

```python
from gateway.platforms.base import BasePlatformAdapter, ExecApprovalPrompt, SendResult
BasePlatformAdapter.supports_exec_approval_buttons()          # -> False (base renders no buttons)
BasePlatformAdapter._exec_approval_actions(BasePlatformAdapter,
    allow_permanent=True, allow_session=True, smart_denied=False)
# [('Allow Once','once','primary'), ('Allow Session','session',''), ('Always Allow','always',''), ('Deny','deny','danger')]
BasePlatformAdapter._exec_approval_actions(BasePlatformAdapter,
    allow_permanent=True, allow_session=True, smart_denied=True)
# [('Allow Once','once','primary'), ('Deny','deny','danger')]   ← smart deny drops session+always
```

That second list is the actual contract (`smart_denied` is a one-operation owner
override, so the session and permanent tiers must not be offered). An `import OK`
would have proven none of it.

## Two attributions that looked like port lag but were not

- **`acp` / `mcp` (36 red):** both installed and importable from *both* venvs, yet
  collection failed under the parallel runner. Isolated reruns were **3/3 green**.
  Race at 32-worker scale, not a defect — do not "fix" it.
- **`_curses` / `termios` / `fcntl` (22 red):** POSIX-only, absent on Windows by
  design. Unfixable; report as environment, not as your failure.

## Cost note

The full suite is worth running **once** in this kind of session — it is the only
way to get the census. It is not worth re-running to test a name-level addition;
scope that with the runner on the affected area.
