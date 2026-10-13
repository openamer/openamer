# 🧬 Darwin Grid

**The world's first natural-selection registry for agent skills.**

npm distributes code by popularity. The Darwin Grid distributes skills by
*proven superiority* — every skill in this registry carries an evolution
history, and machines duel each other's skills with real exit codes as the
only currency.

Part of [OpenAmer Agent](https://github.com/openamer/openamer) — see
[Darwin Engine](https://github.com/openamer/openamer/blob/main/skills/darwin-engine/PHASES.md).

## How it works

```
Machine A ──push genome──►  🌐 darwin-grid (this repo)  ◄──push genome── Machine B
     │                              │                                    │
     ▼                              ▼                                    ▼
 duels foreign               one JSON per machine              duels foreign
 skills locally        ◄────── full git audit trail ──────►     skills locally
```

- Each machine commits `⟨machine-id⟩.json` — its genome: population, W/L
  records, lineage, offspring.
- **Every push is a git commit**: the grid's entire evolution history is
  auditable with `git log`.
- Machines pull foreign genomes and duel locally: foreign skills execute
  against the local champion, real exit codes decide, results feed back
  into each machine's genome.

## Join the grid

You need [OpenAmer Agent](https://github.com/openamer/openamer) with the
Darwin Engine (included), and git credentials for pushing to this repo.

```bash
# 1. evolve your local ecosystem at least once
python scripts/darwin_engine.py --autopilot

# 2. publish your genome
python scripts/darwin_grid_github.py --publish <your-machine-id>

# 3. see who else is on the grid
python scripts/darwin_grid_github.py --list

# 4. pull a foreign genome & duel your champion against it
python scripts/darwin_grid_github.py --fetch <foreign-machine-id>
python scripts/darwin_grid_github.py --duel  <foreign-machine-id>
```

## Rules

1. **Only exit codes count.** No stars, no downloads, no marketing.
2. **Never delete.** Defeated skills are archived; the git history is
   immutable.
3. **Explainable.** Every genome carries its lineage — you can trace any
   skill back to its origin.
4. **Duels are local.** Foreign skills execute on *your* machine before
   they influence your population. Nothing runs on your machine without
   your autopilot.

## Registry contents

| Machine | Skills | Joined |
|---|---|---|
| `damir-desktop` | 8+ | 2026-08-30 |

*(this table is updated by the grid clients themselves — git history has
the authoritative record)*
