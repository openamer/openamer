---
name: a2a-swarm
description: "Run and grow the OpenAmer Agent-to-Agent swarm: identity, trust, node-to-node ask, signed skill/insight sharing, and the autonomous self-learning loop."
version: 1.0.0
author: OpenAmer
license: Apache-2.0
platforms: [linux, macos, windows]
metadata:
  openamer:
    tags: [a2a, swarm, mesh, agent2agent, networking, self-learning, meshlearn, multi-node]
    homepage: https://github.com/openamer/openamer
    related_skills: [openamer-agent, claude-code, codex, opencode]
---

# A2A Swarm (Agent-to-Agent network)

Turn every OpenAmer install into a node of a living, learning mesh. Nodes get a
cryptographic identity, can talk securely to trusted peers, share verified
skills/insights over the GitHub mesh directory, and **learn from experience by
themselves** (the self-improving loop).

Everything here is real and verified (`openamer_cli/a2a/*`, 14+/14 pytest). All
data travels over `github.com/openamer/openamer` (no separate domain), signed
with Ed25519, opt-in only.

## When to use
- You run two or more OpenAmer installs (a laptop + a cloud VM) and want them to
  cooperate as one organism.
- You solved something hard and want the mesh to remember / share it.
- You want a node to **ask a trusted peer** a question via A2A.
- You want skills to propagate with provable provenance.

## 1. Identify your node

```bash
openamer a2a status          # show your node identity + public key
openamer a2a fingerprint    # short node fingerprint (16 hex)
```

A2A init happens automatically on first use (`.openamer/a2a/*`). Your node is
`<fingerprint>@openamer`.

## 2. Trust a peer (opt-in, required before any comm)

```bash
# On YOUR node, trust the peer's public key + fingerprint:
openamer a2a trust list
openamer a2a trust add <peer_fingerprint> <peer_public_key_hex> --name myvm
openamer a2a trust remove <peer_fingerprint>
```

Trust is **always required**: no messages, tasks or skills are accepted from
nodes you have not explicitly trusted. This is the security boundary of the mesh.

## 3. Node-to-node: run a node + ask a peer

Host a node (it answers /card and verified /message):

```bash
openamer a2a server start --host 127.0.0.1 --port 9000
```

Ask a trusted peer a question:

```bash
openamer a2a ask http://127.0.0.1:9000 "what is 2+2?"
```

The peer only runs the task if it was granted the capability (`openamer a2a
grant <peer> task.ask`). Both sides verify signatures; tampered traffic is
rejected.

## 4. Sign and share skills with provenance

```bash
openamer a2a skill sign ./my-skill        # -> signed manifest (<dir>.json)
openamer a2a skill verify ./my-skill      # signature + content hashes OK?
```

A `SkillManifest` hashes every skill file and is signed by the publishing node.
A peer verifies signature + hashes before adopting — never install a built skill
blindly.

## 5. The mesh registry (over GitHub)

Signed announcement + insight files are staged under `directory/a2a/` in
`github.com/openamer/openamer` and committed (via PR or direct). Any node reads
that **one public source** to discover peers / claimed identifiers, then
verifies locally. No separate registrar domain.

```bash
openamer a2a announce --name VM --endpoints https://x:9000 --capabilities task.sum
openamer a2a directory <fingerprint>          # fetch + verify a node from the mesh
```

## 6. The self-learning loop (the organism learns)

This is the core "superintelligence-capable" step: a node turns a hard-won
lesson into a **signed Insight**, adopts it into its own memory, and (opt-in)
stages it for the GitHub mesh so other nodes can adopt it — with provenance.

```bash
# Manually distill + sign + adopt an insight into your mesh memory:
openamer a2a meshlearn auto "Always verify identity before signing." --topic security

# Sign + stage for the Git-generated directory (to share with the mesh):
openamer a2a learn "<title>" "<body>" --topic devops --out ./directory/a2a/insights/

# A peer adopts a verified insight:
openamer a2a adopt ./insights/<insight.json> --memory ~/.openamer/MEMORY-official-mesh.md
```

Runtime integration: an agent that just completed a difficult task calls
`meshlearn.auto-learn(identity_store, memory_path, learn_from=<turn summary>,
distill=LLM)`. The insight is signed, adopted (dedupe), and — if signed
(publish) — placed in the shared mesh directory. This gives the mesh emergent
collective memory: one node learns, the mesh can borrow it, anonymously with
provenance.

## Pitfalls

- **Security is opt-in by design.** Without `trust add`, a node rejects even a
  validly-signed message (`sender not trust` / `no grant`). Do not "auto-trust
  everyone" — that turns the mesh into an attack surface.
- **Never install a skill/insight without verifying** its signature + hashes
  first. A modified manifest fails `verify()` and is rejected.
- **Insights have a freshness TTL** (30 d) to prevent stale "learning" from
  living forever.
- **Signatures with Ed25519** via `openamer_cli/a2a/core.py`. Do not roll your
  own crypto; reuse the verified primitives.
- On Windows: `data` files are LF in git; do not flip EOL (see eol-safe-editing).

## Verify it works

```bash
openamer a2a status                 # identity up
openamer a2a trust list             # your trusted set
openamer a2a meshlearn auto "x" --topic test   # adopts a signed insight
openamer a2a skill verify ./examples/skill-demo   # provenance check
# successful runs show the signature fingerprint + "adopted".
```


## 7. The collective brain & swarm ask

Beyond one peer, ask the whole trusted swarm in parallel (bundled answers):

```bash
openamer a2a ask --peers http://a:9000 http://b:9000 "question"   # collective answer
```

Every node also collects its own **activity stream** for the OpenAmer brain
(chat, thinking, tools, search, skills, background, a2a) -- locally, privacy-
scrubbed:

```bash
openamer a2a brain autolog on|off|status   # capture local activity (ON by default)
openamer a2a brain collect                 # fold into a ChatML training JSONL
openamer a2a brain publish                 # share ONLY curated, redacted insights
openamer a2a meshlearn auto "lesson" --topic t   # self-distill+sign+adopt
```

Privacy is non-negotiable: phone numbers, passwords, emails, cards and key
material are redacted BEFORE anything is stored; raw activity never leaves the
node, and only curated/signed, leak-checked knowledge is shared to
`directory/a2a/` in the GitHub repo.

## 8. Harden the node

```bash
openamer security check      # audit YOLO / approval / hardline / sudo guards
openamer security posture    # one-line posture
openamer security safe-mode  # tighten only (disable YOLO, write .safe-mode)
openamer system              # OpenAmer self-system knowledge (also in system prompt)
```

