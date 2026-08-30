---
name: darwin-engine
description: Use when evolving the skill population automatically - fitness scoring, mutation, crossover, and parent/child competition. Run `python scripts/darwin_engine.py --full` from the repo root.
---

# Darwin Engine — Evolutionary Skill Ecosystem

Treats skills as an evolving population: fitness from real usage signals,
mutations from top parents, crossover of two parents, and competition where
a winning child replaces (archived, never deleted) its parent.

## When to use

- Periodic (cron) skill-population evolution
- Deciding which skills are weak and should be pruned or mutated
- Generating improved skill variants without human curation

## Commands (repo root)

```bash
python scripts/darwin_engine.py --scan      # fitness for all skills
python scripts/darwin_engine.py --mutate    # generate mutations (dry-run)
python scripts/darwin_engine.py --mutate --apply   # write offspring
python scripts/darwin_engine.py --crossover skillA skillB --apply
python scripts/darwin_engine.py --compete   # evaluate candidates vs parents
python scripts/darwin_engine.py --trial skillA skillA__mutX  # live A/B: cron job runs child
python scripts/darwin_engine.py --trials  # evaluate trials from real execution evidence
python scripts/darwin_engine.py --report    # reports/darwin-report.md
python scripts/darwin_engine.py --full      # scan+mutate+compete+report
```

## Outputs

- `reports/darwin-fitness.json` — per-skill fitness (usage, health, age, W/L)
- `reports/darwin-report.md` — human-readable leaderboard
- `~/.openamer.../darwin/offspring/` — candidate child skills
- `~/.openamer.../darwin/archive/` — archived (defeated) parents

## Fitness model

`usage*3 + health*5 + mutation_bonus - age_penalty + structure_bonus`

Exit codes: 0 = ok, 1 = no data, 2 = evolution made changes.

## Pitfalls

- Exit code 2 from `--full`/`--mutate` is SUCCESS with changes — cron must treat it as ok.
- Fitness needs the sessions DB to count usage; without it, usage = 0 and ranking is age-driven only.
- Mutations are deterministic (seed 42) for auditability.
