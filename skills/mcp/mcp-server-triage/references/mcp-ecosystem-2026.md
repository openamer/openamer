# MCP / A2A ecosystem state — measured 2026-11-06

Numbers here were read from the live endpoints and from wheels on disk, not
recalled. Re-measure before quoting them as current.

## Where servers come from (and the 21x gap)

| Source | Size | Shape |
|---|---|---|
| `punkpeye/awesome-mcp-servers` README | ~1.9k rows | markdown, needs regex parsing |
| Official registry (AAIF / Linux Foundation) | **40,965 servers** (2026-10-09) | JSON, keyless, versioned |

```bash
# keyless, no auth, no SDK
curl -s "https://registry.modelcontextprotocol.io/v0/servers?limit=5&search=github"
```

Response shape:

```json
{"servers":[{"server":{"name":"io.example/x","title":"GitHub",
  "description":"...","version":"1.2.3",
  "repository":{"url":"https://github.com/..."},
  "remotes":[{"type":"streamable-http","url":"https://..."}]},
  "_meta":{"io.modelcontextprotocol.registry/official":
           {"status":"active","isLatest":true}}}],
 "metadata":{"nextCursor":"..."}}
```

Three traps, all of which bite on the first implementation:

1. **Every published version is its own row.** Dedupe by `server.name`, letting
   `_meta...isLatest` win over row order — otherwise one server consumes
   several slots of a `--limit 5` and the output looks duplicated.
2. **`status != "active"`** (deprecated / deleted) stays in the registry for
   auditing. Filter it out; never offer such a row as an install.
3. **Remote-only servers have no `repository.url`.** Keep `remotes[0].url` or
   the entry has no usable target.

## How this repo wires it

`openamer_cli/a2a/mcp_catalog.py`:

- `_registry_entries(payload)` — normalise + filter + dedupe (pure, testable).
- `_fetch_registry(query, limit, timeout)` — cached per `(registry, query, limit)`.
- `search(..., source="auto" | "registry" | "community")` — `auto` asks the
  registry first and only falls back to the community README when the registry
  yields nothing; `community` reproduces the old behaviour and keeps the
  hermetic tests offline.
- CLI: `openamer a2a mcp-catalog "<q>" --limit N --source auto`.

Search **finds**; it never installs an arbitrary repo. `openamer mcp add` and
`openamer mcp install <approved-name>` remain the supply-chain-pinned path —
keep that split when extending this.

## Protocol versions (measured, not remembered)

- Installed SDK on this host: **mcp 1.26.0** → `LATEST_PROTOCOL_VERSION = "2025-11-25"`.
- PyPI current line: **mcp 2.3.0** = spec **2026-07-28** (stateless core).
- 1.x is still maintained (1.30.0 is a maintenance release), so a 1.26 pin is
  **behind, not broken**.

### What 2026-07-28 changed

- Stateless core: no `initialize` handshake, no `Mcp-Session-Id`. Version and
  capabilities ride in `_meta`; a server that needs state mints an explicit
  handle passed as a tool argument. Any instance can answer any request, so
  plain round-robin works.
- Routing headers `Mcp-Method` / `Mcp-Name` on Streamable HTTP POSTs.
- Caching: list results carry `ttlMs` and `cacheScope` (SEP-2549).
- `InputRequiredResult`: client retries with the answers — replaces the
  held-open streams used for elicitation / sampling / roots.
- Auth: RFC 9207 issuer validation; Client ID Metadata Documents replace
  Dynamic Client Registration (DCR still works).
- Extensions: Tasks, MCP Apps (server-shipped HTML in a sandboxed iframe),
  Enterprise Managed Authorization.
- Deprecated: Roots, Sampling, Logging, old HTTP+SSE — with a 12-month floor,
  so nothing is removed before 2027-07-28.

### The 2.x break, exactly

`from mcp.server.fastmcp import FastMCP` raises `ModuleNotFoundError` in 2.x.
The migration target is `from mcp.server.mcpserver import MCPServer`.
`mcp/server/fastmcp.py` survives in the wheel as a 769-byte stub that raises on
import, purely so v1 code gets a readable pointer instead of a bare "no module".

Call sites in this repo (only two — `openamer mcp` client code does not import
the SDK): `mcp_serve.py:52`, `agent/transports/openamer_tools_mcp_server.py:157`.

## A2A

- v1.0.0 (12 Mar 2026), v1.0.1 (28 May 2026), AAIF Growth Stage since 27 Aug 2026.
- Discovery: `GET /.well-known/agent-card.json`. A v1.0 card carries
  `supportedInterfaces[]` (`url` + `protocolBinding` + `protocolVersion`),
  `capabilities`, `securitySchemes` (OIDC), `skills[]`.
- This repo already serves that shape — `openamer_cli/a2a/standard.py`,
  `PROTOCOL_VERSION = "1.0"`, with `/.well-known/agent.json` as the implicit
  0.3 alias.
- Adoption, honestly: MCP SDKs pull 92.2M downloads/week vs A2A 4.5M (21:1).
  Use MCP for agent→tool; add A2A only when handing work to an agent you don't
  run.

## WebMCP

Draft Community Group Report (8 Oct 2026), Chrome 149 origin trial,
*not* on the W3C Standards Track. `registerTool()` / `getTools()` /
`executeTool()` on a `ModelContext` interface: the page hands the agent real
functions instead of the agent guessing which button to click. Feature-detect
(`window.modelContext`) and fall back to normal clicking.

## Commerce (DIR-02 / 22 / 23 territory — code is possible, money is gated)

- **AP2** (Google, 17 Sep 2025) — agent-led payments, an extension of A2A and MCP.
- **ACP** (Stripe + OpenAI, 29 Sep 2025) — checkout via Instant Checkout.
- **UCP** (Google, 11 Jan 2026) — the whole shopping journey.

None is an AAIF project; all three need real merchant/payment accounts, so a
client proves nothing without an end-to-end transaction.