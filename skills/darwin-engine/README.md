# 🧬 Darwin Engine

**The self-evolving skill ecosystem for OpenAmer.** No other agent framework
lets its skill population evolve itself — Darwin does.

Skills are treated as a living population: they are scored on *real* usage
signals, the fittest breed mutated children, children compete against their
parents **live in production cron jobs**, winners are promoted automatically,
and dead weight is quarantined — reversibly.

## How it works

```
        ┌──────────┐   real session   ┌──────────┐
        │ FITNESS  │◄── usage data ───│ SESSIONS │
        └────┬─────┘                  └──────────┘
             │ top-5 become parents
             ▼
        ┌──────────┐   section-aware  ┌──────────┐
        │ MUTATION │────variants ────►│ OFFSPRING│
        └──────────┘                  └────┬─────┘
             │                             │ live trial:
             ▼                             │ child replaces parent
        ┌──────────┐   exit codes from ────┘ in a real cron job
        │ SELECTION│◄── executions.db
        └────┬─────┘
             │ winner promoted / loser archived (never deleted)
             ▼
        ┌─────────────────────────────────┐
        │ EVOLVED POPULATION + LINEAGE TREE│
        └─────────────────────────────────┘
```

## The 4 phases

| Phase | Capability | Evidence |
|---|---|---|
| 1 | Fitness scoring from real session + cron signals | 60k+ messages scanned |
| 2 | **Live A/B trials**: child replaces parent in a real cron job; winner decided by real exit codes | executions.db |
| 3 | Semantic section-aware mutations + autopilot + quarantine with rollback | 19 tests |
| 4 | Lineage family tree (Mermaid) + portable genome export/import for fleet evolution | 7 tests |

## Quick start

```bash
python scripts/darwin_engine.py --autopilot        # full unattended cycle
python scripts/darwin_engine.py --lineage          # evolution family tree (mermaid)
python scripts/darwin_engine.py --trial skillA skillA__mutX   # start live A/B
python scripts/darwin_engine.py --quarantine       # dry-run: what would be pruned
python scripts/darwin_engine.py --rollback 1       # undo last quarantine
python scripts/darwin_engine.py --export-genome    # portable evolution state
python scripts/darwin_engine.py --import-genome genome.json  # fleet merge
```

## Guarantees

- **Never deletes** — parents are archived, quarantined skills are restorable
- **Never guesses** — every promotion decision is backed by real execution evidence
- **Never breaks cron** — skills referenced by any job are protected from quarantine
- **Reproducible** — mutations use a fixed seed for full auditability
- **Fleet-ready** — genomes merge across machines, highest W/L wins conflicts

## Why this matters

Every other agent framework curates its skills by hand — humans deciding what
stays, what goes, what gets improved. Darwin removes the human from the loop:
improvement pressure comes from *actual usage*, selection comes from *actual
failures*, and the family tree of every improvement is preserved forever.

This is natural selection, applied to agent capability.
