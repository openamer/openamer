># Measured MCP triage — 2026-10-22, this host

Raw evidence from one diagnostic session on
`C:\Users\damir\AppData\Local\openamer-laptop`. Kept because the *shape* of the
result — three servers fine, three parked, and the discriminating log lines —
repeats, and because it shows how the two failure classes masquerade as each
other.

## The banner that started it

```
MCP Servers
  blender (stdio) — disabled
  linear  (http) — 68 tool(s)
  notion  (http) — 69 tool(s)
  sentry  (http) — failed
  stripe  (http) — 15 tool(s)
  supabase (http) — failed
  vercel  (http) — failed
```

## Level 1 — token files

`$OPENAMER_HOME/mcp-tokens/`:

```
linear.json       present, fresh (≈17255 s left)
notion.json       present, fresh (≈25933 s left)
stripe.json       present, fresh (≈733 s left)
sentry.client.json  present, but NO sentry.json
supabase.client.json present, but NO supabase.json
vercel.client.json  present, but NO vercel.json
```

`*.client.json` is the dynamic-client-registration record; the **token** file is
`<name>.json`. A server with only `.client.json` was registered but never
authorized ⇒ it can never connect in a non-interactive context.

## Level 2 / 3 — measured outcomes

Real OpenAmer path (`MCPServerTask.start`, config from `_load_mcp_config()`):

```
linear:   READY in 2.05s tools=68
notion:   READY in 2.42s tools=65
stripe:   READY in 2.90s tools=11
vercel:   FAIL after 90.02s TimeoutError
supabase: FAIL after 90.02s TimeoutError
sentry:   FAIL after 90.02s TimeoutError
```

The three that connected had a live token. The three that parked had none.

## The log lines that name the class

```
WARNING tools.mcp_tool: MCP server 'linear' failed initial connection after 3
  attempts, parking until a reconnect is requested (state: connecting → parked): TimeoutError:
```

versus, in the SAME log file, minutes later:

```
WARNING tools.mcp_tool: MCP OAuth setup failed for 'sentry': MCP OAuth for
  'sentry': non-interactive environment and no cached tokens found. Run
  `openamer mcp login sentry` interactively first to complete initial authorization.
```

The first is a generic timeout line. The second names the real cause. **Search
the log for the OAuth line before believing a timeout.** A 401 from the raw
HTTP probe also means "alive, needs auth", not "down".

## The fix

```
openamer mcp login sentry
openamer mcp login supabase
openamer mcp login vercel
```

Each needs a real interactive terminal; a background/daemon context cannot
complete the browser callback. Then restart the CLI so it reconnects.

## SDK gotcha hit while probing

`mcp.client.streamable_http.streamable_http_client(url, headers=...)` raises

```
TypeError: streamable_http_client() got an unexpected keyword argument 'headers'
```

on mcp 1.26.0. The `headers=` kwarg was removed; the client must be built
explicitly and passed as `http_client=`:

```python
async with httpx.AsyncClient(follow_redirects=True,
                             timeout=httpx.Timeout(30.0, read=300.0),
                             headers={...}) as client:
    async with streamable_http_client(url, http_client=client) as (r, w, sid):
        ...
```

This is also exactly what OpenAmer's own `_run_http` does
(`tools/mcp_tool.py`, the `_MCP_NEW_HTTP` branch), so the probe mirrors
production behaviour.

## Side findings from the same session (not MCP)

- `context_length` for `minimax-m3.1-flash@https://ollama.com/v1` resolves to
  **1 000 000** tokens (cache: `context_length_cache.yaml`), threshold 500 000.
  The `ctx --` in the status bar is therefore an initialisation-timing
  artifact, not a missing window.
- `openclaw_residue_cleanup: true` was already in
  `config.yaml → onboarding.seen`, so the "This tip only shows once" hint was
  correctly suppressed. Verified with
  `is_seen(config, OPENCLAW_RESIDUE_FLAG) == True`.
- The banner's `+1 carried commit` was stale: after `git fetch origin main`,
  `origin/main` and `HEAD` were both `a01108a2` and
  `git rev-list --count origin/main..HEAD` was `0`.
