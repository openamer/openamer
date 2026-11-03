# A2A protocol (standard interoperability)

OpenAmer nodes can expose the public [Agent2Agent (A2A) protocol](https://github.com/a2aproject/A2A)
alongside their existing signed node-to-node channel. The standard surface is a
**bounded adapter** — it does not replace the OpenAmer mesh, and it advertises
only what it actually implements.

Pinned reference: A2A **v1.0.1** (`docs/specification.md` + `specification/a2a.proto`).

## What is supported

| Surface | Detail |
|---|---|
| `GET /.well-known/agent-card.json` | A2A v1.0 Agent Card (public discovery URI) |
| `GET /.well-known/agent.json` | Pre-1.0 alias of the same card |
| `POST /a2a` | JSON-RPC 2.0 `SendMessage` and `GetTask` |
| `GET /card`, `POST /message` | Unchanged OpenAmer routes (Ed25519 envelope + trust store) |

Accepted method aliases for pre-1.0 clients: `message/send` → `SendMessage`,
`tasks/get` → `GetTask`. They are never advertised on the card.

## Start a node

```bash
# Bearer token is a secret: keep it in the profile .env, not in config.yaml.
echo 'A2A_BEARER_TOKEN=...' >> ~/.openamer/.env
openamer a2a node serve --port 9000 --public-url http://127.0.0.1:9000
```

Without a token the command refuses to start. There is no unauthenticated
mode: an empty token disables the standard surface entirely (both routes
return 404) instead of falling open.

## Call it

```bash
curl -s http://127.0.0.1:9000/.well-known/agent-card.json

curl -s -X POST http://127.0.0.1:9000/a2a \
  -H 'Authorization: Bearer ...' \
  -H 'A2A-Version: 1.0' \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"SendMessage",
       "params":{"message":{"messageId":"m1","role":"ROLE_USER",
                "parts":[{"text":"what is 2+2?"}]}}}'
```

## Security model

- **Authentication**: every JSON-RPC request needs `Authorization: Bearer <token>`.
  Missing or wrong credentials → HTTP 401 with a `WWW-Authenticate: Bearer` challenge.
- **Authorization**: the token's configured capability set must include
  `task.ask` (`--capabilities`, default `task.ask`). Without it the call is
  rejected with HTTP 403 and the task handler never runs.
- **Same handler as the signed channel**: standard requests are dispatched
  through the same `on_task` callback as the Ed25519-verified `/message` route,
  so tool permissions, approvals and profile scoping are unchanged. The adapter
  never executes tools itself.
- **Version negotiation**: the `A2A-Version` header is required for 1.0 clients.
  A missing header is treated as a pre-1.0 client (A2A §3.2.6) and any version
  other than `1.0` is rejected with `VersionNotSupportedError` (-32009).
- **No compliance claim**: the card sets `streaming: false`,
  `pushNotifications: false` and `extendedAgentCard: false`. Methods outside the
  supported subset return `-32601`.

## Not implemented

Streaming (`SendStreamingMessage`), push notification configs, `ListTasks`,
`CancelTask`, `SubscribeToTask`, task resubscription, extended Agent Cards and
multi-tenancy. These are reported as explicit protocol errors rather than
silently emulated.
