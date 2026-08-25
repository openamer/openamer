# 🧠 Competitive Intelligence — what we learned & what to steal (legally)

> Collected 24.08.2026 from public repos/docs/papers (Apache/MIT/public research).
> Not copied code — studied mechanisms, adapted ideas to our architecture.

## Sources studied

| Source | Stars | License | What we studied |
|---|---|---|---|
| aeonfun/aeon | 686 | MIT | Core loop: autoresearch, skill-health/repair, fleet-control, spawn-instance |
| SunzeY/SEAgent (ICML'26) | 262 | research | Curriculum Generator, World State Model, GRPO learning |
| LeoYeAI/openclaw-auto-dream | 544 | MIT | 5 memory layers, forgetting curves, dream cycle |
| usehelix/helix | 826 | — | Self-healing for payments (90% auto-recovery) |
| superloglabs/superlog | 1.394 | — | Self-healing via observability |

---

## Already stolen (implemented today)

1. **Lineage theses** ← AEON `autoresearch` variation-comments.
   Our version: `STRATEGY_THESIS` + `healed_via_thesis` stamp on every heal.
2. **Systemic-first triage** ← AEON `skill-repair` ("prefer a single shared fix
   over N per-skill patches when failures cluster").
   Our version: `systemic.py` — one alarm per error-signature cluster,
   auto-activates hunger reserve on 429 clusters.
3. **Fleet scorecard** ← AEON `fleet-control scorecard`.
   Our version: `scorecard.py` (runs/day, agent-vs-script, est. API load).
4. **Training curriculum** ← SEAgent Curriculum Generator.
   Our version: `curriculum.py` — 4 difficulty levels, live exam 4/4 PASS.

## To steal next (ranked by value/effort)

5. **Forgetting curve** ← auto-dream: memories decay gradually + archive instead
   of manual cleanup. Fits our Memory (99% full crisis!). Effort: ~half day.
   - importance = f(access count, recency, references)
   - nightly dream phase already exists → add decay step there
6. **Importance scoring × Recency × References** ← auto-dream index.json.
   Our MEMORY.md has no scores; consolidation would get objective ranking.
7. **Repair cooldown / idempotency** ← AEON skill-repair history:
   "don't re-repair the same target within 24h". Prevents repair loops.
   Fits our cron wrappers. Effort: ~1h.
8. **Verdict-first reports** ← AEON fleet-control "every run leads with a
   verdict, then delta vs prior, then next action". Our reports bury the
   verdict. Effort: ~2h across systemic/scorecard/senses outputs.
9. **World State Model (light)** ← SEAgent: score each STEP of a workflow run,
   not just pass/fail of selectors. Start with heuristics (DOM stability,
   load time, element visibility) before any ML. Effort: 1-2 days.
10. **spawn-instance full flow** ← AEON clones itself into a new repo with
    configured skills + idempotent recovery codes (SPAWN_FORK_EXISTS_RECOVERED…).
    We did it manually for Seda; automate as `firstborn.py spawn --repo`. Effort: ~half day.

## Anti-features we deliberately do NOT copy

- **AEON's crypto/token flywheel** (distribute-tokens in USDC) — not our game.
- **SEAgent's RL training infra** (GRPO on 7B models) — needs GPUs we don't have;
  our evolution is symbolic (strategy stats), which is honest and free.
- **auto-dream's 5-layer complexity** — our memory is small enough that one
  decay pass beats five layers of ceremony.

---
*"Amateurs copy code. Professionals copy mechanisms."*
