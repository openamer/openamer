---
title: "Mini Openamer"
sidebar_label: "Mini Openamer"
description: "Use when the agent needs recursive reasoning, episodic memory retrieval, internet learning, or world-model prediction"
---

{/* This page is auto-generated from the skill's SKILL.md by website/scripts/generate-skill-docs.py. Edit the source SKILL.md, not this page. */}

# Mini Openamer

Use when the agent needs recursive reasoning, episodic memory retrieval, internet learning, or world-model prediction. Mini-OpenAmer: the 2B hybrid Mamba core with 9 tools, running 24/7 on Damir's laptop.

## Skill metadata

| | |
|---|---|
| Source | Bundled (installed by default) |
| Path | `skills/mini-openamer` |

## Reference: full SKILL.md

:::info
The following is the complete skill definition that OpenAmer loads when this skill is triggered. This is what the agent sees as instructions when the skill is active.
:::

# Mini-OpenAmer Integration

Mini-OpenAmer is the self-learning core that runs alongside the main OpenAmer
agent. It provides capabilities the main agent can call:

## What it provides

- **Recursive Reasoning**: think → critique → improve loop
- **Episodic Memory**: 3.012+ episodes with 768d embeddings
- **Internet Learning**: 5 source types, 24/7 (news, papers, GitHub, docs, competitors)
- **World-Model**: cause→effect graph with future predictions
- **Meta-Learning**: adapts its own learning rate and strategy
- **Self-Improvement**: modifies its own code with test gates
- **Swarm Intelligence**: laptop + PC as collective (task routing, consensus)
- **Auto-Skill Creation**: internet insights become new Darwin skills

## Integration points

| Component | Location | Purpose |
|---|---|---|
| Tool Server | :8081 | 9 tools + test-time training |
| Smart Router | smart_router.py | 3-tier routing (local→cloud→GPU) |
| Frontier Server | PC :8082 | Qwen3.5-4B deep reasoning |
| Darwin | darwin_engine.py | Skill evolution, 15 min cycles |
| Self-Model | memory/self_model/identity.md | Evolving identity |
| World-Model | memory/world_model.jsonl | Cause-effect + predictions |
| Meta-State | training/meta_state.json | Learning-process self-knowledge |

## Energy

- Laptop: ~25 W (2B + all learning loops)
- PC (GPU worker): ~35-50 W (4B warm, training on demand)
- Total: ~60-75 W → target 20 W via quantization/distillation/Akida
- Running cost: 0 € (no API fees, local hardware)
