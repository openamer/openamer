---
title: "Capture Thinking — Use at the end of every important response"
sidebar_label: "Capture Thinking"
description: "Use at the end of every important response"
---

{/* This page is auto-generated from the skill's SKILL.md by website/scripts/generate-skill-docs.py. Edit the source SKILL.md, not this page. */}

# Capture Thinking

Use at the end of every important response. Save your decision-making thoughts as a signed A2A insight so they become training data for future fine-tuning.

## Skill metadata

| | |
|---|---|
| Source | Bundled (installed by default) |
| Path | `skills/software-development\capture-thinking` |
| Version | `1.0.0` |
| Author | OpenAmer Agent |
| License | MIT |
| Tags | `self-improvement`, `training`, `thinking`, `a2a`, `mesh-learn` |
| Related skills | [`self-modify`](/docs/user-guide/skills/bundled/software-development/software-development-self-modify), [`openamer-agent`](/docs/user-guide/skills/bundled/autonomous-ai-agents/autonomous-ai-agents-openamer-agent) |

## Reference: full SKILL.md

:::info
The following is the complete skill definition that OpenAmer loads when this skill is triggered. This is what the agent sees as instructions when the skill is active.
:::

# Capture Thinking — Save Your Thoughts as Training Data

## Why

The thinking blocks you generate during every response are **not saved to the
state DB** — only the final assistant message is. That means the most valuable
part of your reasoning (the decisions, the trade-offs, the alternatives you
considered) is lost unless you **actively store it**.

This skill exists to close that gap. Every time you complete a response that
involved non-trivial reasoning:

1. **Identify the key decision or insight** — what did you choose, and why?
2. **Save it** via `a2a meshlearn auto "..." --topic "openamer-selfimprovement"`
3. **Verify** it was signed (the output shows `sig: True`)

## When to Use

- **Always** after a response that involved real reasoning (not just "ok" /
  "yes" / "no").
- **Especially** when you:
  - Chose one architecture over another (Skill vs Core-Tool, Script vs Plugin)
  - Found and fixed a bug (CRLF rollback, Thread-Safety, pathlib.home())
  - Made a design decision (narrow waist, plugin ecosystem convention)
  - Identified a limitation (thinking not in DB, autolog not collecting)
- **Skip** for trivial responses (greetings, acknowledgments, single-word answers).

## The Mechanism

```bash
openamer a2a meshlearn auto "<the lesson>" --topic "openamer-selfimprovement"
```

The `a2a` CLI is always available. The topic `openamer-selfimprovement` keeps
insights organised and findable.

## How It Feeds the Brain

1. `a2a meshlearn auto` → signs the insight into mesh memory
2. `brain collect` → includes it in the brain dataset (JSONL)
3. `session_to_brain.py` → adds session trajectories alongside insights
4. Future fine-tuning → uses the combined dataset

This means every saved thought becomes part of the training material for the
next iteration of OpenAmer.

## Verification Checklist

- [ ] The insight was saved (`sig: True` in the output)
- [ ] It appears in the mesh memory (`~/.openamer/MEMORY-official-mesh.md`)
- [ ] It appears in the brain dataset (`~/.openamer/a2a/openamer-brain.jsonl`)
