---
name: rsi-phase2-learned-proposals
description: "RSI Phase 2: Learned proposals from model"
---
## RSI Phase 2: Learned Proposals

Goal: Replace rule-based proposals with model-learned patterns validated by safety rails.

Current: Rule-only (CYCLE_SECONDS, max_tokens, imports, except, stale comments)
Phase 2: Add learned proposals from 2B model with validation gates

Architecture: propose_improvement(target, content, model=None) runs rules ALWAYS, then learned proposals IF model provided and validated.

Safety: Pattern must exist in content, bindings must be preserved, kind must be in allowed set, reason must be non-empty.

Output: Logged to improvements.jsonl, acceptance rate tracked over 50 cycles.
---
RSI Phase 2 design: learned proposals from 2B model, validated by safety rails, optional integration with existing improve_once()