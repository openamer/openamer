---
title: "Rsi Phase2 Learned Proposals — RSI Phase 2: Learned proposals from model"
sidebar_label: "Rsi Phase2 Learned Proposals"
description: "RSI Phase 2: Learned proposals from model"
---

{/* This page is auto-generated from the skill's SKILL.md by website/scripts/generate-skill-docs.py. Edit the source SKILL.md, not this page. */}

# Rsi Phase2 Learned Proposals

RSI Phase 2: Learned proposals from model

## Skill metadata

| | |
|---|---|
| Source | Bundled (installed by default) |
| Path | `skills/rsi-phase2-learned-proposals` |

## Reference: full SKILL.md

:::info
The following is the complete skill definition that OpenAmer loads when this skill is triggered. This is what the agent sees as instructions when the skill is active.
:::

## RSI Phase 2: Learned Proposals

Goal: Replace rule-based proposals with model-learned patterns validated by safety rails.

Current: Rule-only (CYCLE_SECONDS, max_tokens, imports, except, stale comments)
Phase 2: Add learned proposals from 2B model with validation gates

Architecture: propose_improvement(target, content, model=None) runs rules ALWAYS, then learned proposals IF model provided and validated.

Safety: Pattern must exist in content, bindings must be preserved, kind must be in allowed set, reason must be non-empty.

Output: Logged to improvements.jsonl, acceptance rate tracked over 50 cycles.
---
RSI Phase 2 design: learned proposals from 2B model, validated by safety rails, optional integration with existing improve_once()
