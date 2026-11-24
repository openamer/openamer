# Official MCP Registry Integration — Dual-Source Catalog

## Overview
Enhanced `openamer a2a mcp-catalog` to search **both** the official MCP registry (~40,965 servers) and the community awesome-mcp-servers README (~1,900 servers).

## Changes Made

### 1. `openamer_cli/a2a/mcp_catalog.py`
- Added `_fetch_registry()` — queries `https://registry.modelcontextprotocol.io/v0/servers` with search/limit params
- Added `_fetch_community()` — existing GitHub README parsing (punkpeye/awesome-mcp-servers)
- Added `_registry_entries()` — normalizes registry payload (handles version duplication: registry lists every published version of each server)
- Updated `search(query, source="auto", limit=20)` — merges both sources, dedupes by server ID, prefers registry entries
- Added `source` parameter: `"auto"` (merged), `"registry"` (official only), `"community"` (README only)
- 60-second timeout on registry fetch, graceful fallback to community-only

### 2. `openamer_cli/subcommands/a2a.py`
- Added `--source auto|registry|community` argument to `mcp-catalog` subcommand
- Removed unsafe/unimplemented `--install` flag
- Updated help text

### 3. `tests/openamer_cli/test_mcp_catalog.py`
- Added 4 new tests for registry path:
  - `test_registry_entries_normalises_payload`
  - `test_search_auto_prefers_registry`
  - `test_search_community_only`
  - `test_search_registry_only`
  - `test_registry_entries_dedupes_versions_keeping_latest`

## Registry Payload Structure
```json
{
  "servers": [
    {
      "server": {
        "id": "io.github.user/server-name",
        "name": "Server Name",
        "description": "...",
        "repository": {"url": "https://github.com/..."},
        "version": "1.2.3",
        "tags": ["tag1", "tag2"]
      },
      "_meta": {
        "isLatest": true,
        "publishedAt": "2026-11-06T..."
      }
    }
  ]
}
```

## Key Technical Findings

### Version Duplication
The registry returns **every published version** as a separate entry (same server ID, different version). The `_meta.isLatest` flag marks the latest. Our normalization keeps only the latest version per server ID.

### Remote-Only Servers
Many registry entries are **remote-only** (streamable-http URLs like `https://browserhere.1ts.app/mcp`) — no local Docker/NPX install needed. The community README mostly has local-installable servers.

### Search Behavior
- `source="auto"` (default): Merged results, registry preferred for deduping, community fills gaps
- `source="registry"`: Official only, includes remote servers
- `source="community"`: Legacy README-only, local-installable focus

## Verification
- All 66 tests pass (60 original + 6 new)
- Ruff clean on all modified files
- Live test: `openamer a2a mcp-catalog "browser" --limit 5` returns 5 results including remote streamable-http server

## Related
- Official registry: https://registry.modelcontextprotocol.io/
- Community source: https://github.com/punkpeye/awesome-mcp-servers
- MCP spec: https://modelcontextprotocol.io/