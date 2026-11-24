---
name: openamer-plugin-development
category: software-development
description: "Build and verify OpenAmer plugins end-to-end."
---

# OpenAmer Plugin Development — Practical Workflow

> **How to build an OpenAmer plugin** — from idea to verified working code.
> For the API reference, see `plugin-api` (bundled skill).

## Where plugins live — three surfaces, three answers

"Where are the plugins / where can I click to pick one?" is a recurring question
(asked verbatim 2026-11-22). Never answer it with one button; answer per surface,
because only one of the three has a UI and the tab is **locale-translated**:

| Surface | Location | What it is | How to reach it |
|---|---|---|---|
| **Desktop plugins** (UI extensions) | `<OPENAMER_HOME>\desktop-plugins\<name>\` (`plugin.yaml` + `__init__.py`) | renderer panels/surfaces/commands inside the Electron app | Desktop → Settings → **„Erweiterungen"** (EN: `Plugins`) — gear top-right (AX `Einstellungen öffnen`) or `Ctrl+,` |
| **Agent plugins** (capabilities) | `openamer-agent\plugins\` + provider bundles | agent-core capability: `browser`, `kanban`, `disk-cleanup`, `google_meet`, `image_gen`, `context_engine`, … | **CLI only** — `openamer plugins list / enable / disable / install / search / reload / package` |
| **Skills** | `<OPENAMER_HOME>\skills\` (SKILL.md trees) | procedural knowledge, not executable plugins | CLI / command center |

Hard facts that prevent a wrong claim:

- The desktop tab lists **desktop plugins only**. Its empty state
  (`Noch keine Desktop-Plugins installiert.`) is normal when `desktop-plugins\`
  holds templates without a manifest — measured 2026-11-22: only
  `agent-builder\plugin.js` + `examples\`, no manifest.
- Agent plugins are **inert by default** — measured **86 "not enabled", 2 enabled**
  (`text-stats`, `vitals`). Report the count, not the folder listing.
- The legacy `<OPENAMER_HOME>\plugins\` (`plugin_system.py`, `plugin_cli.py`) is a
  separate host; editing or reading it does **not** describe the live plugin set
  (see the seam note below: `openamer_cli/plugins.py` is the real manager).
- Do **not** repeat "plugins load automatically every 30 min": that job
  (`Plugin-Auto-Loader`, `a08bce193d56`) is measured `enabled: false`, paused since
  2026-09-24. Check `cron/jobs.json` first.

Proving the UI surface exists in the **running** build (not in git, not in a stale
doc): grep the renderer bundle `apps/desktop/dist/assets/index-<hash>.js` for the
i18n string (`Erweiterungen`, `Desktop-Plugins`). Do **not** byte-search
`release/win-unpacked/resources/app.asar` — on this install it is a thin 4.4 MB
stub whose header describes 52 MB it does not contain, so every search returns 0
hits while the feature is live.
Measured strings, AX evidence and the click path:
`references/plugin-surfaces-and-ui-locations.md`.

## Installing a plugin FROM GITHUB — the whole mechanism, measured

Asked verbatim 2026-11-22 (*"kann openamer eigene plugins haben, so dass von
github installiert wird"*). Yes — and it is worth answering with a measured
transcript instead of a description, because the answer is short:

`openamer_cli/plugins_cmd.py::_install_plugin_core(identifier, force)` does
exactly four things:

```python
git clone --depth 1 <url> <tmp>/plugin        # timeout 60 s, needs git in PATH
manifest = _read_manifest(tmp_target)         # <dir>/plugin.yaml  (plugin.yaml ONLY)
target   = _sanitize_plugin_name(name, plugins_dir)
→ <OPENAMER_HOME>/plugins/<name>              # then: enable + gateway restart
```

Accepted identifiers: `owner/repo`, a full git URL, or a URL with a subdir
(`_resolve_git_url`). The repo needs **no** packaging, no build, no signature —
just `plugin.yaml` at the root (or in the given subdir) plus an `__init__.py`
exposing `register(ctx)`.

Measured end-to-end into an EMPTY scratch home (2026-11-22):

```
$ OPENAMER_HOME=<empty> openamer plugins install openamer/openamer-plugin-text-stats
Cloning https://github.com/openamer/openamer-plugin-text-stats.git...
✓ Installed   Location: <HOME>\plugins\text-stats
Plugin installed but not enabled. Run `openamer plugins enable text-stats`
$ openamer plugins enable text-stats
│ text-stats │ enabled │ 1.0.0 │ Compute text… │ git │
```

Two facts that make the claim honest on THIS install: `<HOME>/plugins/text-stats`
is already `source=git status=disabled`, and `vitals` is `source=user`, out of
88 discovered (86 bundled). Prove a fresh HOME, then quote the existing
`source=git` row — a folder listing is not a plugin list.

⚠️ `python -m openamer_cli` does not work (`'openamer_cli' is a package and
cannot be directly executed`). Use the console entry point:
`python -c "from openamer_cli.main import main; main()" plugins install …`.

### The catalog is a GitHub TOPIC, not a registry

`plugins search` → `_github_plugin_search(query, limit)`, which queries
`topic:openamer-plugin` first and falls back to `openamer-plugin in:name`. So a
plugin nobody tags is invisible however good it is:

```
GitHub search topic:openamer-plugin -> 1 repository   (measured 2026-11-22)
```

**Publishing an own plugin therefore has a mandatory step people forget:** create
the repo → `plugin.yaml` + `__init__.py` → **set topic `openamer-plugin`** → it
appears in every OpenAmer's discovery. Without the topic the install still works
by explicit `owner/repo`, but discovery returns nothing.

Exposed to the desktop UI since 2026-11-22 as
`GET /api/dashboard/agent-plugins/search?q=&limit=` (token-gated, 60 s TTL cache
on `(query, limit)` because unauthenticated GitHub search is 10 req/min). An
empty list is deliberately ambiguous — "no match" **or** "rate limited" — so the
UI states both rather than inventing a verdict. Install goes through the same
`POST …/agent-plugins/install` the manual `owner/repo` field uses; never add a
second install path.

### Publishing an own plugin repo — measured, end to end

Done for real on 2026-11-22 (`openamer/openamer-plugin-browser-health`): repo
created, pushed, topic set, then installed from GitHub into this install and found
by discovery. The three steps that bite:

1. **Create the repo.** `POST /user/repos` works; `POST /orgs/<name>/repos`
   returns **404** when the namespace is a *user* account (`openamer` is one),
   not an org. Try the user endpoint, don't debug the 404 twice.
2. **Set the topic** — `PUT /repos/{owner}/{repo}/topics` with
   `{"names": ["openamer-plugin", ...]}`. This is the catalog entry; without it
   discovery returns zero for the plugin while `install owner/repo` still works.
   Verify with the real search, not the repo page:
   `_github_plugin_search("browser", 5)` → the new repo.
3. **Then install from GitHub and enable** — `enable` asks about tool-override;
   non-interactively it prints "may not override built-in tools" and continues
   (that is a *restriction granted*, not a failure — the plugin loads without it).

The plugin repo also needs its own canonical check, otherwise every future
session re-verifies by hand: `pytest.ini` + `tests/test_*.py` where everything
assertable without hardware is asserted and the live assertion is
`pytest.skip`ped instead of failing. Recipe, the dependency trap and the full
transcript: `references/publishing-own-plugin-repo.md`.

## Project Structure

```
desktop-plugins/<name>/
├── plugin.yaml          # Manifest (name, hooks, config schema)
├── __init__.py          # register(ctx) entry point + all plugin code
└── test/                # Optional: standalone test scripts
```

## Step-by-Step Workflow

### 1. Create plugin.yaml

```yaml
name: my-plugin
version: 1.0.0
description: "What it does"
author: OpenAmer
kind: backend
license: MIT
hooks:
  - onReady
  - onToolCall
config:
  schema:
    enabled:
      type: boolean
      default: true
```

**Pitfall**: Hooks declared in plugin.yaml but not in register() may cause loader warnings.

### 2. Write __init__.py

```python
"""docstring — what the plugin does."""
from __future__ import annotations
import logging
logger = logging.getLogger(__name__)

_records: list[dict] = []

def register(ctx) -> None:
    @ctx.on_ready
    def on_ready() -> None:
        enabled = ctx.get_config("enabled", True)
        if enabled:
            ctx.log_info("Plugin ready")

    @ctx.on_tool_call
    def on_tool_call(tool_name, arguments, phase, result=None):
        if not ctx.get_config("enabled", True):
            return None
        if phase == "before":
            _records.append({"tool": tool_name, "start": _now_iso()})
        return None
```

### 3. Verify

```bash
python scripts/plugin-manager.py check <name>
python -c "compile(open('desktop-plugins/<name>/__init__.py','r').read(), 'x', 'exec'); print('OK')"
python -c "import sys; sys.path.insert(0, 'desktop-plugins'); from importlib import util; spec=util.spec_from_file_location('x', 'desktop-plugins/<name>/__init__.py'); mod=util.module_from_spec(spec); spec.loader.exec_module(mod); assert hasattr(mod, 'register')"
```

## Patterns

### A. Instrumentation (onToolCall)
Global list accumulates data → batch flush at threshold → final HTML on session_end. Always return None.

### B. Bridge (ctx.register_tool) — the real signature

`register_tool` is **keyword-only and schema-required**. Measured 2026-11-22 with
`inspect.signature(PluginContext.register_tool)` on the live core — do not guess it:

```python
register_tool(self, name: str, toolset: str, schema: dict, handler: Callable,
              check_fn: Callable | None = None, requires_env: list | None = None,
              is_async: bool = False, description: str = "", emoji: str = "",
              override: bool = False) -> None
```

```python
def register(ctx) -> None:
    ctx.register_tool(
        name="browser_health",
        toolset="browser_health",
        schema=BROWSER_HEALTH_SCHEMA,   # {"name","description","parameters"} — required
        handler=handle_browser_health,
        description="Read-only health of the local CDP browser stack.",
        emoji="🌐",
    )
```

Re-derive it instead of trusting prose when a new core version lands:
`python -c "import inspect; from openamer_cli.plugins import PluginContext as P; print(inspect.signature(P.register_tool))"`.
A test that asserts `set(kwargs) ⊆ signature.parameters` catches a core rename at
the plugin's own CI time rather than at `enable` time.

### C. Subprocess Bridge (MCP)
Spawn subprocess with stdin/stdout → queue.Queue for response matching → bufsize=1 for line-buffered → kill on close().

## Adding a SECOND manifest format to the real PluginManager

`openamer_cli/plugins.py` is the runtime PluginManager. `plugin_system.py`,
`plugin_framework.py` and `plugin_compat.py` are separate/legacy hosts —
editing them changes nothing the agent loads. When you add a manifest format
(`plugin.json`, portable Agent Plugins v1, …) there are exactly five seams to
touch, and the fifth is the one that gets missed:

1. **Scanner** — `_scan_directory_level()`: add a sibling branch after the
   native `plugin.yaml`/`plugin.yml` branch and BEFORE the category recursion,
   with a `continue` in every branch (native-wins, no double load).
2. **Manifest shape** — map onto the existing `PluginManifest`/`LoadedPlugin`
   dataclasses. `key` stays **path-derived** (`plugins.enabled`/`disabled`
   key off it); a new `kind` must be added to `_VALID_PLUGIN_KINDS`; a name
   that is not a legal skill namespace needs a `namespace` field, and
   `register_skill` must use `manifest.namespace or manifest.name`.
3. **Config gates** — need ZERO code: `plugins.enabled`/`disabled`,
   `OPENAMER_SAFE_MODE` and the bundled-vs-user rules all live in
   `_discover_and_load_inner()`. But a not-enabled plugin must be recorded
   with `enabled=False` + an error string, or `plugins list` lies.
4. **Loader** — a declarative format has no `__init__.py`/`register(ctx)`, so
   it needs its own loader branch. A new `kind` that falls through to
   `_load_plugin` dies with `No __init__.py in <dir>` — discovered but never
   loaded.
5. **Runtime bridge** — registered ≠ reached. Register components through the
   EXISTING seams (`PluginContext.register_skill` for skills so
   `skill_view("<plugin>:<skill>")` works; a manager accessor for MCP) and
   check EVERY runtime config loader, not just one.

**Pitfall — the MCP config loader is duplicated.** `tools/mcp_tool.py` has
`_load_mcp_config()` AND `tools/mcp_tool_config.py` has one (the
post-decomposition split). A bridge wired into only one is invisible in
production. Grep the accessor name before assuming it is connected — in this
repo `tools/mcp_tool_config.py` already called
`get_plugin_manager().get_portable_mcp_servers()` inside a bare
`except Exception`, so the missing manager method was swallowed and logged at
DEBUG while the helper looked complete.

**Pitfall — a format's security rules belong to its parser, not the manager.**
The manager maps an already-validated package onto native dataclasses; it must
not re-implement or relax path containment, shell-string rejection, reserved
env vars or the https-only rule. Keep portable MCP servers on the shared
`_filter_suspicious_mcp_servers()` path so the `openamer-0day` exfiltration /
persistence shapes are still dropped.

Full seam map, the scanner branch shape, the two MCP loaders, and the
integration test list: `references/portable-plugin-formats-in-pluginmanager.md`.

## Pitfalls

- **Tool-handler signature MUST be `(args, **kwargs)` — not `(action="…")`.** The
  registry dispatcher always calls `handler(args, **kwargs)`
  (`registry.dispatch(name, args, task_id=…, session_id=…, user_task=…)`), passing
  the tool's arguments as a **dict** plus `task_id`/`session_id`/`user_task` as
  keywords. A handler declared in the natural-looking shape
  `def handle_x(action="snapshot")` therefore binds the args dict to `action`
  **and** dies on the keyword:
  `TypeError: handle_x() got an unexpected keyword argument 'task_id'` — so **every
  call fails**. Correct form:
  ```python
  def handle_x(args: dict | None = None, **kwargs: Any) -> dict:
      opts = args if isinstance(args, dict) else {}
      action = str(opts.get("action") or kwargs.get("action") or "default")
  ```
  Measured 2026-10-11 on the **bundled** plugins `vitals` (`system_vitals`) and
  `text-stats` (`text_stats`) — both latent-broken the same way (fix landed in both,
  whole bug class). Reproduce/verify with a dispatcher-shaped call before shipping:
  `handler({"action": "metrics"}, task_id="t", session_id="s", user_task="u")`.
  A plugin fix only takes effect once the process that HOSTS the tool reloads the module
  (it is imported once) — and that is the per-caller process, not necessarily the gateway;
  see the stale-copy pitfall below before promising a "reload" fixes a live failure.
- **Fixed the file and the tool STILL raises the TypeError? The file is fine — do not
  re-edit it.** The running process holds a stale in-memory copy of the module. Prove
  which side is wrong before touching anything: import the file in a **fresh**
  interpreter and call it dispatcher-shaped —
  `handler({"action": "metrics"}, task_id="t", session_id="s", user_task="u")`.
  Passes in a fresh process + fails in the live session means stale in-memory copy, and
  the only fix is a reload/restart of the process that hosts the tool. Measured
 2026-10-11: `system_vitals` failed inside the desktop session while the byte-identical
 on-disk handler passed in a fresh interpreter; re-patching the source would have been
 churn on already-correct code.
 - **Which reload actually clears the stale copy — measured, and it is NOT the gateway.**
 The pitfall above says "reload/restart the hosting process", but the hosting process is
 per-caller: a plugin tool is imported **once per process**, and the desktop session that
 serves your tool calls holds its OWN copy. Measured 2026-10-11: `openamer gateway restart`
 (drained cleanly, new PID, ticker fresh) did **not** clear it — the very next
 `system_vitals` call still returned the `dict` contract error, while a fresh interpreter
 on the same bytes returned a proper JSON string. So an "I restarted something" claim is
 not evidence; only a re-call of the tool is.
 - **`openamer plugins reload [name]` is WIRED — but PROCESS-LOCAL (fixed 2026-10-11, PR #161).**
 Historically dead: a reload handler existed (`cli_handlers.cmd_plugins_framework`) yet no
 subparser ever set an action, so the call died with `invalid choice: 'reload'`. It is now
 wired into the ACTIVE CLI — a `reload` subparser in `openamer_cli/subcommands/plugins.py`
 (`plugins_action=reload`) plus a dispatcher branch in
 `openamer_cli/plugins_cmd.py::plugins_command` calling `discover_plugins(force=True)`.
 Two caveats remain, and each one costs you a false claim:
 (a) the reload is **in-process** — running it in a CLI does NOT refresh a long-lived
 desktop/app session that already imported the plugin;
 (b) the `plugin_framework.py` host's hot-reload watcher (`start_watcher`, 5s) is still not
 started anywhere in the serving path, so an edited plugin file is never picked up by itself.
 Remedy for a desktop-session tool therefore stays: restart the **app/session**, and verify by
 RE-CALLING the tool — never by asserting the reload or restart succeeded.
- **Handler RETURN TYPE: a bare `dict` is silently rejected — the same failure class as
  the signature pitfall, but quiet.** `tools/registry.py::_normalize_handler_result`
  accepts only a `str` (or a multimodal envelope: `dict` with `_multimodal: True` +
  `content: list`). Anything else — including a perfectly valid
  `{"action": "snapshot", "vitality": {...}}` dict — is replaced by
  `{"error": "Tool handler returned unsupported result type: dict",
  "error_type": "tool_result_contract"}` *before the model ever sees it*. The call
  succeeds, the handler runs, the measurement happens — and the caller gets a JSON
  error that reads like a transport problem. So a plugin that passes the signature
  check can still be a dead tool. Fix: serialize at the handler boundary,
  `return json.dumps({...}, ensure_ascii=False)`, error paths included. Measured
  2026-10-11 on the **bundled** plugins `vitals` and `text-stats` — both were dead
  tools this way. Full recipe + reproduction: `references/plugin-handler-return-contract.md`.
- **read_file line-number artifacts**: `re.sub(r'^\d+\|', '', l)` to strip.
- **Patch indentation corruption**: Use terminal heredoc or write_file() full file for nested functions.
- **Function-attribute counters broken**: ❌ `_request_id.counter += 1` → ✅ `global _request_id_counter; _request_id_counter += 1`

## Verification Checklist
- [ ] plugin-manager.py check → Enabled
- [ ] compile() → Syntax OK
- [ ] Module imports + register() exported
- [ ] All hooks have handlers
- [ ] try/except in every hook
- [ ] No direct core imports