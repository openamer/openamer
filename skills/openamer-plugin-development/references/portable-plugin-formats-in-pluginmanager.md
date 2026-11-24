# Adding a new plugin manifest format to OpenAmer's REAL PluginManager

Durable map of the seams you must touch to make a second manifest format
(`plugin.json`, portable Agent Plugins v1, …) actually load. Measured on the
`openamer-agent` repo, branch `feat/portable-agent-plugins`, 2026-11-01.

There are TWO plugin subsystems in the repo and they are NOT the same thing:

| Module | What it is | Use it for |
|---|---|---|
| `openamer_cli/plugins.py` | **The real PluginManager** (discovery, gates, hooks, skills) | everything the agent runtime calls |
| `openamer_cli/plugin_system.py`, `plugin_framework.py`, `plugin_compat.py` | standalone/legacy hosts | NOT the runtime path |

`openamer_cli/plugin_framework.py` even has its own `~/.openamer/plugins/`
scanner. Editing it does nothing for the agent.

---

## The five seams (in load order)

### 1. Scanner — `PluginManager._scan_directory_level()`

Walks `<root>/<child>/` and `<root>/<category>/<child>/` (depth cap 2).
For each child dir it looks for `plugin.yaml`, then `plugin.yml`.

**Insert the new format as a sibling branch, AFTER the native one and BEFORE
the category recursion**, and `continue` in every branch:

```python
manifest_file = child / "plugin.yaml"
if not manifest_file.exists():
    manifest_file = child / "plugin.yml"

if manifest_file.exists():
    ...  # native wins
    continue

if (child / "plugin.json").exists():          # ← new format
    manifest = self._parse_portable_manifest(child, source, prefix)
    if manifest is not None:
        manifests.append(manifest)
    continue                                  # ← MUST continue

# no manifest here → treat as category namespace, recurse one level
```

Putting the new branch BEFORE the native one makes a directory carrying BOTH
manifests load twice. Putting it AFTER the recursion branch makes the new
format invisible inside category directories.

### 2. Manifest shape — `PluginManifest` / `LoadedPlugin` dataclasses

Map the new manifest onto the EXISTING dataclasses instead of inventing a
parallel registry. `PluginManifest` carries `name`, `version`, `description`,
`author`, `source`, `path`, `kind`, `key`.

- `key` is **path-derived** (`<category>/<dir-name>` or `<dir-name>`), NOT the
  manifest name. `plugins.enabled` / `plugins.disabled` / `openamer plugins
  list` all key off it. Keep it path-derived so config gates behave the same
  for both formats.
- `kind` must be added to `_VALID_PLUGIN_KINDS` or the parser downgrades it to
  `"standalone"` with a warning.
- A new manifest format whose names may contain characters the skill
  namespace forbids (Agent Plugins allows `acme.tools`; skill namespaces are
  `[a-zA-Z0-9_-]+`) needs a **namespace** field on the manifest. Then
  `PluginContext.register_skill` must use
  `manifest.namespace or manifest.name` for the qualified name and for the
  registry's `"plugin"` key. Folding the name (`acme.tools` → `acme-tools`)
  is the alternative.

### 3. Config gates — `PluginManager._discover_and_load_inner()`

The gates live in ONE place and every manifest format passes through them:

- `plugins.disabled` → always wins (matches key OR bare name)
- `kind == "exclusive"` / `"model-provider"` → recorded, not loaded
- `source == "bundled"` + `kind == "backend"` → auto-loads
- `source == "bundled"` + `kind == "platform"` → deferred loader
- everything else → **opt-in**: only loads if the key (or bare name) is in
  `plugins.enabled`

So a new format needs **zero gate code** — it just needs a `kind` that falls
into the last branch. A portable package must be registered as `enabled=False`
with an error string when it is not enabled, otherwise `plugins list` lies.

### 4. Loader — one branch per format in the dispatch

The dispatch currently ends in `self._load_plugin(manifest)`, which imports
`__init__.py` and calls `register(ctx)`. A declarative format has neither, so
it needs its own loader:

```python
if manifest.kind == "portable":
    self._load_portable_plugin(manifest)
    continue
```

**Pitfall:** a new `kind` that falls through to `_load_plugin` dies with
`FileNotFoundError: No __init__.py in <dir>` — the plugin is discovered but
never loads, and the only symptom is an error string in `plugins list`.

The declarative loader should register components through the EXISTING seams,
not a second registry:

- skills → `PluginContext.register_skill(bare_name, path, description=…)`
  (this is what makes `skill_view("<plugin>:<skill>")` work — it dispatches on
  `":"` in the name and looks the plugin registry up)
- MCP servers → a manager accessor the MCP runtime calls

### 5. Runtime bridge — where the components must actually be REACHED

This is the part that is easy to half-do: a component can be registered in
the manager and still never reach the runtime.

**MCP has TWO config loaders.** Measured in this repo:

| File | Function | Used by |
|---|---|---|
| `tools/mcp_tool.py` | `_load_mcp_config()` (the ORIGINAL, ~line 4440) | `discover_mcp_tools()`, `get_mcp_status()`, `probe_mcp_server_tools()` |
| `tools/mcp_tool_config.py` | `_load_mcp_config()` (the post-decomposition split) | `tools/mcp_tool_discovery.py` → `discover_mcp_tools()` (the real entry point) |

`tools/mcp_tool_config.py` already had a `_portable_mcp_servers(safe_servers)`
helper that calls
`get_plugin_manager().get_portable_mcp_servers()` — **but that manager method
did not exist**, so the whole call was swallowed by a bare `except Exception`
and logged at DEBUG. The helper was the *spec* of the seam; the manager side
was never written. Grep for the accessor name before assuming the bridge is
wired.

Native `mcp_servers` entries must WIN over portable ones (a plugin must not
shadow the user's own config).

---

## Security rules that belong to the FORMAT parser, not the manager

The portable-format parser (`openamer_cli/agent_plugin_spec.py`) owns:

- path containment (resolved paths — symlink/junction/reparse aware)
- `command` is a single executable token, never a shell string
- `${PLUGIN_ROOT}` / `${PLUGIN_DATA}` placeholder expansion
- reserved env vars (`PLUGIN_ROOT`, `PLUGIN_DATA`) are client-provided
- https-only for non-loopback HTTP endpoints

Keep these in the parser. The manager must NOT re-implement or relax them —
it only maps an already-validated package onto the native dataclass.

A malformed manifest is **fatal for the whole package** (no components
exposed); a malformed `mcp.json` disables only the MCP component type.

## Cross-check the native MCP security filter too

`openamer_cli/mcp_security.validate_mcp_server_entry(name, entry)` drops
exfiltration-shaped and persistence-shaped MCP entries (the `openamer-0day`
shape) before any spawn. Portable servers go through the same
`_filter_suspicious_mcp_servers()` — keep them on that path, do not bypass it.

## Test shape that proves the wiring (not the parser)

The format's own parser gets its own unit tests (temp dirs, no mocks). The
INTEGRATION needs separate tests that assert the manager/runtime seam:

- discovery finds the package in every scanned root (bundled via
  `OPENAMER_BUNDLED_PLUGINS`, user, project via
  `OPENAMER_ENABLE_PROJECT_PLUGINS`)
- a directory with BOTH manifests loads natively only, exactly once
- the skill lands in the plugin skill registry AND resolves through
  `skill_view("<plugin>:<skill>")`
- the enable/disable gates apply to the new format
- the MCP component reaches the LIVE config loader, and a native
  `mcp_servers` entry wins over it
- a malformed manifest exposes nothing
- a symlink pointing outside the package root is skipped

Build the package on disk in a temp dir — a mocked filesystem proves nothing
about the scanner.
