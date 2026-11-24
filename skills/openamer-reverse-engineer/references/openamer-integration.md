# OpenAmer integration

This fork is wired into OpenAmer on three levels: an MCP server, a CLI, and an
Evidence-to-memory bridge. Nothing here is required to use the analysis engines
— it is how OpenAmer specifically consumes them.

## Identity

| Thing              | Value                       |
| ------------------ | --------------------------- |
| Display name       | OpenAmer RE                 |
| CLI binary         | `oare`                      |
| npm package        | `openamer-re`               |
| MCP server key     | `openamer-re`               |
| Client config file | `openamer-re.json`          |
| Bundled skill      | `openamer-reverse-engineer` |
| Upstream           | REA v6.8.0 by morluto (MIT) |

## Installing the CLI

`openamer-re` is not on the npm registry yet, so `npx openamer-re` will fail.
Install from this repository instead:

```bash
npm install --prefix "$HOME/.oare" "$(pwd)"   # or: npm i -g "$(pwd)"
node scripts/rea.mjs --version                # run without installing
```

The package pins `^22.23.4 || ^24.22.1 || >=26.12.1` and `.npmrc` sets
`engine-strict=true`, so an older Node refuses to install.

## Tool-family scopes (measured on one Windows host)

The server registers 229 tools when unscoped. Every tool schema costs context,
so register a scope. Measured counts with `oare mcp doctor` (protocol
2025-11-25, 6 prompts in all cases):

| `REA_MCP_TOOL_FAMILIES`                                                                           | Tools |
| ------------------------------------------------------------------------------------------------- | ----- |
| _(unset)_                                                                                         | 229   |
| `direct,enhanced,native,artifact,managed,browser,electron,javascript-runtime,application,session` | 179   |
| `direct,session,artifact,managed,browser,electron,javascript-runtime,application`                 | 132   |
| `session,application,electron,javascript-runtime,artifact,managed`                                | 79    |
| `session,application,electron,javascript-runtime`                                                 | 49    |

All valid ids: `direct, enhanced, native, artifact, managed, firmware, android,
pcap, flutter, frida, apktool, jeb, adb, browser, electron, javascript-runtime,
application, session`. An invalid id fails startup with the complete list.

Scopes are additive — start narrow and widen on a `Tool ... disabled` error.
Tool schemas are omitted from `tools/list` for families outside the scope, so
the cost is real context, not a formality.

## Registering in OpenAmer

```bash
openamer mcp add openamer-re \
  --env REA_MCP_TOOL_FAMILIES=session,application,electron,javascript-runtime,artifact,managed \
  --command "C:/Users/damir/tools/node-v24.22.1-win-x64/node.exe" \
  --args "<repo>/scripts/rea.mjs" mcp
```

`openamer mcp add` connects, discovers the tools and writes the entry to
`config.yaml`. It prompts to enable the discovered tools; feed `y` on stdin when
running headless. Verify with `openamer mcp test openamer-re`.

Point `--command` at an absolute Node path when several Node versions are
installed. The package pins `^22.23.4 || ^24.22.1 || >=26.12.1` (`.nvmrc`
24.22.1) and `.npmrc` sets `engine-strict=true`, so a 24.18 runtime refuses to
install.

## Evidence-to-memory bridge

`scripts/openamer_re_bridge.py` (in the OpenAmer home) turns an Evidence record
into a durable OpenAmer episode, so a finding outlives the session:

```bash
python scripts/openamer_re_bridge.py describe finding.json          # text only
python scripts/openamer_re_bridge.py ingest finding.json --dry-run   # no write
python scripts/openamer_re_bridge.py ingest finding.json             # writes episode
```

It accepts one Evidence record, a bundle (`records` / `evidence` /
`evidence_records` / `items`), or a JSONL stream with progress lines mixed in.
The written episode carries `kind="re_finding"` and a `meta` block with
`evidence_id`, `operation`, `subject`, `subject_sha256`, `confidence`,
`authority` and the limitation count — so a later recall can tell a bounded
derivation from a complete one.

Embeddings come from `longterm_memory.add_episode`, which calls the local Ollama
`nomic-embed-text` endpoint. If that is down the bridge fails loudly instead of
writing an episode that cannot be retrieved.

## Windows build prerequisite

`native/windows/build/{manifest.json,rea-windows-x64.node}` are build outputs, not
sources. Without them every `scripts/run-exclusive.mjs` command (including
`npm run build`) exits 1 with "Windows native controls are unavailable", because
the owned-process supervisor cannot load. Either build them per
`native/windows/README.md` or copy both files from the published
`rea-agents@6.8.0` tarball — this fork's own remediation message says the same.

## What is upstream and what is ours

Engines, providers, Evidence contracts and tool semantics are upstream code.
This fork changes the identity layer (`src/identity.ts`, `package.json`,
`server.json`), the bundled skill name, and adds the bridge plus this document.
Do not describe a fork-only integration as an analysis capability.
