# Composite / list-constant drift in the toolset layer (2026-10-10)

Session-specific detail for the SKILL.md section *"A port can also drift a shared
LIST CONSTANT"*. Three CI-failing suites, one root-cause class, two independent
port artifacts.

## The failing suites and what they actually said

```
FAILED tests/openamer_cli/test_tools_config.py::test_get_platform_tools_expands_composite_when_mixed_with_configurable
    AssertionError: browser should be enabled when openamer-cli is listed
FAILED tests/tools/test_delegate_composite_toolsets.py::TestExpandParentToolsets::test_composite_openamer_cli_expands_web
    AssertionError: 'browser' not found in {'openamer-wecom-callback', 'openamer-webhook',
      'debugging', 'image_gen', 'openamer-slack', ..., 'web', 'homeassistant', ...}
FAILED tests/gateway/test_api_server_toolset.py::TestApiServerAdapterToolset::test_create_agent_respects_config_override
    AssertionError: assert ['asi', 'terminal', 'web'] == ['terminal', 'web']
```

Baseline: `3 failed, 148 passed`. Note the shape — every message names a
*toolset* (`browser`, `asi`), never a list member, which is exactly why this reads
as expansion-logic breakage instead of a one-string drift.

Reproduce:

```bash
cd <repo>            # a worktree of origin/main
env -u OPENAMER_DELEGATED_CHILD_CONTEXT \
  "C:/Users/damir/AppData/Local/openamer-laptop/venv/Scripts/python.exe" -m pytest \
  tests/openamer_cli/test_tools_config.py \
  tests/tools/test_delegate_composite_toolsets.py \
  tests/gateway/test_api_server_toolset.py -q -p no:xdist --tb=short
```

`-p no:xdist` matters: these suites assert on a module-level `set` populated at
import; xdist workers each re-import and the failure text becomes a huge set dump.

## Root cause A — a leaf grew a member the shared composite never got

`toolsets.py`:

```python
_OPENAMER_CORE_TOOLS = [ ...          # line 31 — the SHARED list
    "browser_vision", "browser_console", "browser_cdp", "browser_dialog",
]                                     # ... browser_vault MISSING

TOOLSETS = {
  "browser": {                        # line 175 — the LEAF
      "tools": ["browser_navigate", ..., "browser_dialog", "browser_vault",
                "web_search"],
  },
  "openamer-cli":  {"tools": _OPENAMER_CORE_TOOLS, ...},   # line 446
  "openamer-cron": {"tools": _OPENAMER_CORE_TOOLS, ...},   # line 452
  ...
}
```

`browser_vault` was added to the leaf by port commit `24c66ebb6`
("feat(vault): model-blind browser autofill") whose `git show -- toolsets.py`
diff is exactly:

```
-            "browser_dialog", "web_search"
+            "browser_dialog", "browser_vault", "web_search"
```

The shared list was not touched in that commit → the subset test
`set(browser_tools).issubset(core_tools)` flips to `False` and `browser` stops
being expanded for **every** platform composite built on `_OPENAMER_CORE_TOOLS`.

Upstream carries `browser_vault_list / _unlock / _fill / _save_login /
_enter_code  # ride with the browser` inside *its* core list — i.e. the identifier
belongs in the shared list, and the port dropped it there. **Fix = add
`"browser_vault"` to `_OPENAMER_CORE_TOOLS`.** Do not remove it from the leaf:
the tool exists (`tools/browser_vault_tool.py`), the leaf is its correct home, and
the leaf is what tests/tools/test_api_server_toolset.py already pins.

## Root cause B — a composite GAINED a member no other composite has

Port commit `5f889477c` ("feat: ASI Core + Heartbeat — native In-Prozess-Integration")
appended to the **`openamer-api-server`** composite only:

```python
# toolsets.py, inside "openamer-api-server" (NOT inside _OPENAMER_CORE_TOOLS)
    # ASI Core — integrated subsystems (gated on scripts/training/ existing)
    "asi_status", "asi_think", "asi_learn",
    "asi_remember", "asi_trigger",
```

and introduced a standalone leaf:

```python
  "asi": {"tools": ["asi_status", "asi_think", "asi_learn",
                    "asi_remember", "asi_trigger"], "includes": []},
```

`asi` is in **neither** `CONFIGURABLE_TOOLSETS` (openamer_cli/tools_config.py:95)
**nor** `_DEFAULT_OFF_TOOLSETS` (:153). Therefore the recovery block in
`_get_platform_tools` (tools_config.py ~1881-1940, "Recover non-configurable
platform toolsets … part of the platform's default composite but absent from
CONFIGURABLE_TOOLSETS") adds it whenever its tools are a subset of the platform's
default-composite universe:

```python
_plat_info = PLATFORMS.get(platform)
_default_ts = _plat_info["default_toolset"]        # "openamer-api-server"
platform_tool_universe = set(resolve_toolset(_default_ts))   # now contains asi_*
...
if not ts_tools.issubset(claimed):
    enabled_toolsets.add(ts_key)                   # <- 'asi' leaks in
```

Measured, per platform, the non-configurable toolsets the recovery block adds:

| platform | recovered non-configurable toolsets |
|---|---|
| `cli` | `['kanban']` (intended — rides along with core) |
| `cron` | `['kanban']` (intended) |
| `api_server` | `['asi']` ← the leak |

So `test_create_agent_respects_config_override` (an explicit
`platform_toolsets: {api_server: [web, terminal]}` override) came back
`['asi','terminal','web']`. This is *not* a bug in the recovery block: that block
recovers rides-along toolsets under an explicit override **by design** (see
`test_get_platform_tools_preserves_explicit_empty_selection`, whose comment says
`kanban` is still auto-recovered). The bug is the composite carrying a capability
no other platform composite carries.

### Candidate fixes, and why the composite edit is the one

| fix | effect | verdict |
|---|---|---|
| remove the `asi_*` block from the `openamer-api-server` composite | `asi` leaves the universe → not recovered; api-server default drops it too | **chosen** — restores the documented invariant "All platforms share the same core tools" (toolsets.py:375-379); minimal diff; matches the "extra member" framing |
| add `"asi"` to `CONFIGURABLE_TOOLSETS` | recovery skips it, api-server *default* still includes it, new TUI toggle appears | plausible but adds user-facing surface and a second, different classification mechanism for the same fix |
| add `"asi"` to `_DEFAULT_OFF_TOOLSETS` | silently disables a documented headline feature on every platform | too broad; changes default behaviour beyond the failing assertion |

`openamer asi status` (the CLI subcommand, `openamer_cli/subcommands/asi.py`) is
unaffected by any of these — the **model tool** set is a separate surface from the
CLI command.

Also worth knowing: an explicit `"asi"` entry in `platform_toolsets` still works
after the composite edit, via `explicit_passthrough` (tools_config.py:1958-1966) —
removing it from the composite makes it *opt-in*, not unreachable.

## The probe that finds the whole class (run this first)

`scripts/composite_toolset_drift.py` in this skill. It prints, in one pass:

1. every leaf toolset whose static tools are **not** a subset of the composite
   that is supposed to bundle it (`_OPENAMER_CORE_TOOLS`-based composites);
2. every non-configurable toolset the recovery block auto-enables per platform;
3. whether the shared list is missing/extra members vs each leaf.

```
.venv/Scripts/python.exe skills/upstream-porting-workflow/scripts/composite_toolset_drift.py
```

## Diagnostics that were dead ends (so the next agent doesn't repeat them)

- `git log --oneline -- toolsets.py` shows **one** commit (`9cb4dc471`, the ~10k-file
  dump commit) — path history is useless in this repo. The rebrand commits
  (`fd647ed4a`, `15ce2b813`) and the feature commits are found with
  `git log --oneline --all -- toolsets.py`, then `git show <c> -- toolsets.py | grep -n "^[-+]"`.
- Comparing against upstream `toolsets.py` answers *"was this identifier in the
  shared list?"* (yes for `browser_vault`) but **cannot** answer anything about
  `asi` — ASI Core is OpenAmer-only and upstream has no `asi` toolset. Use upstream
  for port-drift questions, never for local-feature design questions.
- `grep -rn "\"asi\"\|'asi'" tests/` returns nothing: no test pins the `asi`
  toolset either way, which is why the leak survived. Absence of a test is not
  evidence of intent — the failing fixture (an explicit override returning exactly
  the requested set) was the only signal.

## Tooling notes for running probes in this repo

- **Write the probe to a `.py` file in the worktree and run it with the venv
  python via `terminal`** rather than inlining it into a subprocess helper. An
  inlined `subprocess.run(..., text=True)` on this host decodes output as cp1252
  and dies with `UnicodeDecodeError: 'charmap' codec can't decode byte 0x90` on
  the emoji/box-drawing characters the repo's import banners print. A scratch file
  run through `terminal` inherits a UTF-8-capable environment.
- Run pytest against the **worktree's** `origin/main` copy, not the live install —
  and always `env -u OPENAMER_DELEGATED_CHILD_CONTEXT` so the subagent guard does
  not change tool availability mid-run.
- Delete scratch probes (`_dbg_*.py`) before committing; the live checkout is a
  shared tree that background crons commit into.
