# OpenAmer Vision

## What OpenAmer is

OpenAmer is a **self-improving, self-learning personal AI agent** that runs on
your own machine, meets you in the channels you already use, and gets better
the longer you use it.

It is a **hardened, independently-developed fork** of the
[Agent architecture](https://github.com/NousResearch/hermes-agent), MIT by Nous Research
(MIT-licensed, by Nous Research). We are grateful for that foundation and say
so openly — OpenAmer does not hide its lineage. What we build on top of it is
our own.

## The one thing we refuse to compromise on

**OpenAmer does not break.**

Most agent projects optimize for breadth — more platforms, more models, more
features. We optimize for a different axis first: **robustness and
verifiability.** An agent that silently fails, corrupts its own install, or
invents results is worse than useless, no matter how many features it has.

This is not a slogan. It is a concrete engineering stance:

- **Self-update must never brick the install.** We fix the failure modes that
  leave an agent half-updated (file-locks, interrupted installs, stale
  recovery markers) instead of papering over them.
- **The agent verifies before it claims.** Real tool output, not plausible
  fabrication. When something fails, it says so and shows the real error.
- **Quality is enforced, not hoped for.** We ship skills that audit prose for
  leaked reasoning, enforce documentation standards, and land dependent PRs
  correctly — because a self-improving agent must improve *correctly*.

## Why "self-improving" is our moat

Many agents *claim* to learn. OpenAmer makes learning **real and observable**:

- **Memory** persists across sessions — preferences, corrections, environment
  facts — so the agent stops repeating your corrections.
- **Skills** are procedural memory: after a hard task, the agent distills the
  approach into a reusable skill and improves it the next time it's used.
- **A2A swarm** turns every install into an agent node that can share curated,
  signed, leak-free knowledge with peers — a network that compounds.

This is the one advantage that **grows with time** instead of shrinking. Every
skill, every memory, every solved problem makes OpenAmer better — and no
competitor can copy a year of accumulated learning overnight.

## What we are NOT trying to be

- **Not a coding-agent-in-a-terminal** (that's Claude Code, Codex, Aider).
- **Not a multi-agent framework library** (that's autogen, crewAI, LangGraph).
- **Not a "clone with a new name."** We fork honestly, then we differentiate
  on robustness, verifiability, and real self-improvement.

## The roadmap, in order

1. **Earn trust** — honest lineage, clean installs, no silent breakage.
2. **Prove the learning loop** — observable memory + skills that demonstrably
   improve the agent over time.
3. **Compound through the swarm** — signed, leak-free knowledge sharing between
   nodes, so the network learns faster than any single install.

## The honest bottom line

OpenAmer is young. It does not yet have the stars, the community, or the
polish of its upstream. What it has is a clear, defensible position: **an
agent that does not break, verifies what it claims, and genuinely improves
with use.** That is a foundation worth building on.
