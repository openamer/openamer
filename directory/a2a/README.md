# OpenAmer A2A Mesh Directory (shared storage)

This is the **shared** part of the OpenAmer brain storage. Transparency rule:

- **LOCAL (never here):** raw activity / chat / thinking / tool data stays on
  each user's machine (`~/.openamer/a2a/activity.jsonl` + trajectories). It is
  private and is **never** pushed to this public repo automatically.
- **SHARED (this directory):** only *curated, signed* knowledge — mesh insights,
  skill manifests, node announcements — explicitly published by a user /
  node. Use `openamer a2a ...` to produce and verify these.

| Subdir | Content | Producer |
|---|---|---|
| `insights/`  | signed mesh learning insights (FAQ: `meshlearn learn`) | `a2a meshlearn learn` |
| `skills/`    | signed skill manifests (provenance)                  | `a2a skill sign`   |
| `nodes/`     | signed node announcements (opt-in registry)          | `a2a announce`     |

All content is Ed25519-signed; verify before adopting (`a2a skill verify`,
`a2a meshlearn adopt`). This is open-source "collective knowledge", not user
private data.
