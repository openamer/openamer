# OpenAmer Agent-to-Agent (A2A) Swarm — Design

> **Status:** Proposal / Architecture draft
> **Author:** OpenAmer
> **Goal:** Every OpenAmer install becomes an autonomous agent node that can
> communicate with every other OpenAmer node over the internet, share skills and
> memory, and delegate work — forming an opt-in, living "swarm" that grows and
> improves itself, safely.
>
> This document is the **foundation for building** — it nails down architecture,
> the security boundary, and a phased roadmap. Code comes after this is agreed.

---

## 1. Why & what (the honest framing)

The vision: a living organism of cooperating agents. Each node should be able to
*do anything, know anything, talk to anything*. That vision is achievable as a
**federated network protocol**, but only if we're clear about what actually
creates value:

- **Value is NOT created by "many agents connected".** Joining more nodes does
  not by itself make any agent smarter.
- **Value IS created by three concrete things:**
  1. **Shared grounded memory / skills** (a node that solved X shares that
     solution so another node doesn't re-derive it) — the "growing body".
  2. **Task routing / delegation** (a node that can't do Y finds, securely, a
     node that can) — the "organs".
  3. **Self-improvement loops** (skills improve during use, and good skills get
     published back to the mesh) — the "immune system / evolution".

So this document is deliberately **restrained**: A2A connectivity is the
transport; the *organism* is shared memory + skills + routing, and the *safety*
is the part that must be solved first.

### Core design principles

1. **Opt-in by default.** No node silently joins a swarm or accepts remote work
   without the operator's explicit consent. "Automatic in one click" — never
   "automatic without asking".
2. **Signed, verified identity.** Every message is cryptographically signed by
   its origin node. No anonymous command execution from the network.
3. **Capability budgets.** Remote delegation can only use capabilities the local
   operator has granted (tools, disk, network, spend).
4. **No prompt-injection backdoor.** Remote content is treated as untrusted data,
   isolated from the trusted system prompt, matching how we already treat
   subagent/received content.
5. **Fail-closed.** If identity/verification fails, the message is rejected —
   never partially trusted.

---

## 2. Terminology

| Term | Meaning |
|---|---|
| **Node** | One installed OpenAmer (a host with its own identity key + `OPENAMER_HOME`). |
| **A2A** | Agent-to-Agent protocol — the open standard (Linux Foundation / Google, 2025) for agent interop over HTTP/JSON, complementary to MCP. |
| **Mesh** | The opt-in network of mutually-trusted OpenAmer nodes. |
| **Hub / Discovery** | Optional rendezvous that helps nodes find each other — hosted as a signed registry **inside the GitHub repo** (`github.com/openamer/openamer`, e.g. `directory/a2a/`), not a control plane. Nodes pin the repo; nothing depends on a separate domain. |
| **Skill publish** | A node exporting an improved/bundled skill to the mesh for others to adopt. |
| **Capability** | A named, approved permission (e.g. `terminal.write`, `network.fetch`, `model.budget`) a node may hand to a trusted peer for a specific task. |

---

## 3. Architecture overview

```
         github.com/openamer/openamer/directory/a2a  (optional, signed registry of public keys)
                             │
        ┌────────────────────┼───────────────────────┐
        ▼                    ▼                        ▼
  ┌───────────┐        ┌───────────┐           ┌───────────┐
  │ OpenAmer  │  A2A   │ OpenAmer  │   A2A     │ OpenAmer  │
  │  Node A   │◄──────►│  Node B   │◄─────────►│  Node C   │
  │ (home)    │ HTTPS  │ (cloud)   │  HTTPS    │ (VPS)     │
  └─────┬─────┘        └─────┬─────┘           └─────┬─────┘
        │   MCP / tools      │        MCP/tools      │
   ┌────┴─────┐         ┌────┴─────┐           ┌────┴─────┐
   │ subagents│         │ subagents│           │ subagents│
   │ terminal │         │ terminal │           │ terminal │
   │ file/…   │         │ file/…   │           │ file/…   │
   └──────────┘         └──────────┘           └──────────┘
```

- **Transport:** HTTP(S) JSON following the [A2A protocol](https://a2a-protocol.org)
  (AgentCard + `message/send`), backed by our own capability/trust envelope.
- **Node local** logic lives in `openamer a2a` subcommand + a `a2a/` package.
- **Shared memory/skills** use a publish/subscribe endpoint hosted as signed
  files inside the GitHub repo (`github.com/openamer/openamer`), peer-verified —
  or direct node-to-node for fully self-hosted setups.

---

## 4. Node identity & trust

- Each node generates an Ed25519 keypair at first `openamer a2a on`.
- Public key is the node's address/identity (`<fingerprint>@openamer`).
- Trust model: **explicit.** The operator authorizes peers by adding their
  public key (`openamer a2a trust add <fingerprint>`), or via a signed "invite"
  link `openamer a2a invite`. No global implicit trust.
- Messages carry a signature over (sender, recipient, nonce, timestamp, payload);
  replay-protected by a rolling counter/TTL.

---

## 5. Capability grants (the safety core — required before any code)

Remote work is expressed as **granted capabilities**, never unrestricted:

```
# example: authorize trusted peer for a bounded task
openamer a2a grant <peer> terminal.read   --max-bytes 2MB
openamer a2a grant <peer> network.fetch   --allow "github.com/openamer/openamer"
openamer a2a grant <peer> model.reason    --budget-cents 0.50
openamer a2a grant <peer> file.write      --path "~/a2a-out/"
```

Every capability has: a **scope** (path/domain/type), a **budget** (bytes/cents/
duration), and an **expiry**. Delegated work runs inside the existing subagent +
[approvals] machinery (which OpenAmer already has), so nothing bypasses the
local approval/security net.

---

## 6. What a node shares (the "living organism" parts)

### 6.1 Shared / grounded memory (opt-in)
- A node may **publish** an anonymized, schema-typed "knowledge slice" (a solved
  problem → key insight, with a capability tag) to peers or to the hub.
- Peers **pin** the pubkey; only nodes you trust can write into your mesh feed.
- No raw transcripts are shared; only distilled, permission-cleaned knowledge.

### 6.2 Skill publish / adoption
- When a skill noticeably improves during use (the existing self-improvement
  loop), the operator can `openamer a2a publish skill <name>`.
- Subscribing nodes get a **proposal**, not an auto-install. They review
  (`openamer a2a review <skill>`) then adopt or reject — no silent code running.

### 6.3 Task routing
- `openamer a2a ask "<question>"` → sends to a trusted peer (or a group) with a
  capability budget.
- The remote node may answer directly or delegate to its own subagents; the
  answer comes back through the same signed, budgeted envelope.
- A small **routing hint** (best-effort: which peers advertise which capability)
  helps, but never forces — the operator picks/approves the target.

---

## 7. Security & threat model

| Threat | Mitigation |
|---|---|
| **Prompt injection from remote node** | Remote content isolated; never merged into trusted system prompt; sign + treat as data (reuses existing subagent/receive discipline). |
| **Impersonation / MITM** | Ed25519 signatures; pin public keys; TLS on transport. |
| **Replay / tampering** | Nonce + TTL + rolling counters. |
| **Runaway spend / work on your machine** | Capability budgets (cents/bytes/time); all delegated work goes through local approval. |
| **Malicious skill in mesh** | Skills arrive as **proposals** only; require review + explicit adoption. |
| **Hub compromise** | Hub is discovery-only, pubkey-pinned, never a control plane; node identities are local-first. |

---

## 8. Phased roadmap

> Each phase ships working, verifiable software. Nothing speculative.

### Phase 0 — Groundwork (no network yet)
- [ ] `a2a/` package scaffolding + keypair generation (Ed25519)
- [ ] Identity store + `openamer a2a` CLI skeleton (`status/on/off`)
- [ ] Unit tests for signing/envelope + replay protection
- **Exit:** `openamer a2a status` shows a valid generated identity; tests green.

### Phase 1 — Node-to-node (trusted pair)
- [ ] AgentCard endpoint (A2A) + `message/send`
- [ ] `openamer a2a trust add/remove <pubkey>` + invite link
- [ ] Capability grants + enforcement; delegated task runs in subagent w/ approval
- [ ] End-to-end signed test between two local nodes
- **Exit:** two local nodes exchange a budgeted, signed task & answer.

### Phase 2 — Mesh essentials (self-improving organism)
- [ ] Skill publish/adopt (proposal + review)
- [ ] Shared grounded-memory slices (publish/subscribe, pubkey-pinned)
- [ ] `openamer a2a ask` routing to a trusted group
- [ ] Hub/discovery registry inside `github.com/openamer/openamer` (signed files, pubkey-pinned) — no separate domain
- **Exit:** A solved task's skill/insight published to a trusted peer and
  reviewed/adopted there.

### Phase 3 — Hardening & scale
- [ ] budgets/rate-limits, dashboard UI (`openamer a2a` in desktop/web)
- [ ] E2E encryption (optional at-rest), audit log of capabilities used
- [ ] Public safety docs + threat-model review before wide adoption

---

## 9. Open questions (decide before coding)

1. Should skill/insight sharing default **publish** (transparent) or require a
   manual publish each time? (Recommend: manual publish per item, with a
   "publish pattern" toggle.)
2. Hub vs fully self-hosted mesh as the default path for new users? (Recommend:
   self-hosted pair for power users; hub optional for discovery, never required.)
3. What identity UX? (Recommend: short invite code `openamer a2a invite` →
   trust-fingerprint, preferred over raw long hex.)
4. Version model: keep `a2a` as a purely add-on package so an update never
   breaks non-A2A installs. (Recommend: yes — additive only.)

---

## 10. Why this is "the best in the world" (and keeps its promise)

- Uses the **open A2A + MCP standards**, not a closed format.
- **Safety-first**: signed identity, capability budgets, review-before-adopt —
  the things that make a world swarm trustworthy rather than dangerous.
- **Grounded improvement**, not buzz: shared memory + skills + routing are the
  mechanisms that actually compound across nodes.
- **Additive**: no disruption to existing single-instance OpenAmer; upgrading
  never breaks a working setup.

---

*This is the design contract. Building follows it phase by phase; each phase
ends with working, tested, verifiable code.*