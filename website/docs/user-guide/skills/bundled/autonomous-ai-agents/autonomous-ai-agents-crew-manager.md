---
title: "Crew Manager — Role subprocesses for Dev/Tester/Reviewer/Architect tasks"
sidebar_label: "Crew Manager"
description: "Role subprocesses for Dev/Tester/Reviewer/Architect tasks"
---

{/* This page is auto-generated from the skill's SKILL.md by website/scripts/generate-skill-docs.py. Edit the source SKILL.md, not this page. */}

# Crew Manager

Role subprocesses for Dev/Tester/Reviewer/Architect tasks.

## Skill metadata

| | |
|---|---|
| Source | Bundled (installed by default) |
| Path | `skills/autonomous-ai-agents\crew-manager` |
| Version | `1.0.0` |
| Author | OpenAmer Agent |
| License | MIT |
| Platforms | windows, linux, macos |
| Tags | `crew`, `multi-agent`, `orchestration`, `subprocess`, `roles`, `devops` |
| Related skills | `multi-agent-orchestration`, [`a2a-swarm`](/docs/user-guide/skills/bundled/autonomous-ai-agents/autonomous-ai-agents-a2a-swarm), `greenfield-agent-project` |

## Reference: full SKILL.md

:::info
The following is the complete skill definition that OpenAmer loads when this skill is triggered. This is what the agent sees as instructions when the skill is active.
:::

# Crew-Manager: Multi-Agent-Orchestrator

Orchestriert spezialisierte Rollen (Developer, Tester, Reviewer, Architect) als parallele Subprozesse via subprocess.Popen.

## Schnellstart

```bash
python scripts/crew-manager.py create "Baue einen REST-API-Server"
python scripts/crew-manager.py status
python scripts/crew-manager.py review crew-260821-123456-a1b2c3
```

## CLI

- `create <desc>` — Task erstellen, an alle Rollen delegieren
- `status` — Alle Crews anzeigen
- `review <crew_id>` — Ergebnisse einer Crew anzeigen
- `list` — Alias fuer status

## Rollen

| Rolle | Beschreibung |
|---|---|
| Developer | Code schreiben/implementieren |
| Tester | Tests/Qualitaetssicherung |
| Reviewer | Code-Review |
| Architect | Design/Architektur |

## Dateien

- `scripts/crew-manager.py` — Hauptprogramm
- `scripts/rollen.json` — Rollendefinitionen
- `~/.openamer/crews/` — Crew-Persistenz
