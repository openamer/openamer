---
name: crew-manager
description: "Role subprocesses for Dev/Tester/Reviewer/Architect tasks."
version: 1.0.0
author: OpenAmer Agent
license: MIT
platforms: [windows, linux, macos]
metadata:
  openamer:
    tags: [crew, multi-agent, orchestration, subprocess, roles, devops]
    related_skills: [multi-agent-orchestration, a2a-swarm, greenfield-agent-project]
---

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