---
name: goal-engine
description: 'Use for mission: define, prioritize, --tick, progress, scan.'
tags:
  - missions
  - goals
  - tasks
  - prioritization
  - auto-execution
  - autonomous
usage: |
  Nutze `goal-engine.py` für selbstständige Missionsplanung und Task-Ausführung.
  Daten liegen in `.goal-engine/missions.json` im Home-Verzeichnis.
  Der Cron-Job läuft alle 30 Minuten und führt den nächsten Task aus.
---

# Goal Engine — Autonomous Mission Planning

Vollständiges System für selbstständige Missions-Definition, Auto-Task-Generierung, Priorisierung und Self-Execution.

## CLI-Übersicht

```bash
# Mission definieren (auto-generiert Goals + Tasks)
python scripts/goal-engine.py --define 'Mission Name' 'Beschreibung'

# Alle Missionen nach Priorität sortiert anzeigen
python scripts/goal-engine.py --list

# Automatische Priorisierung (nach Impact + Dringlichkeit)
python scripts/goal-engine.py --prioritize

# Wichtigsten nächsten Task anzeigen
python scripts/goal-engine.py --next

# Nächsten Task automatisch ausführen (self-execution tick)
python scripts/goal-engine.py --tick

# Fortschrittsreport anzeigen
python scripts/goal-engine.py --progress

# Mission/Goal/Task als erledigt markieren
python scripts/goal-engine.py --complete <id>

# Analyse: Scripts, Skills, offene Tasks, Gaps
python scripts/goal-engine.py --scan

# Manuelles Goal hinzufügen
python scripts/goal-engine.py --add-goal <mission_id> 'Beschreibung'

# Manuellen Task hinzufügen
python scripts/goal-engine.py --add-task <goal_id> 'Beschreibung' --priority 4 --script log-analyzer.py
```

## Datenstruktur

```
~/.goal-engine/
├── missions.json    # Alle Missionen mit Goals, Tasks, Prioritäten
└── goal-engine.log  # Aktivitätslog
```

### missions.json Schema

```json
{
  "missions": [
    {
      "id": "m_abc12345",
      "name": "OpenAmer #1",
      "description": "OpenAmer zum besten AI Agent auf Windows machen",
      "priority": 5,
      "status": "active",
      "created": "2026-08-22T00:00:00",
      "deadline": null,
      "goals": [
        {
          "id": "g_abc12345",
          "description": "Analyse & Grundlagen",
          "progress": 0,
          "status": "pending",
          "tasks": [
            {
              "id": "t_abc12345",
              "description": "Analysiere Logs auf Fehler-Patterns",
              "status": "pending",
              "priority": 5,
              "script_hint": null
            }
          ]
        }
      ]
    }
  ]
}
```

## Auto-Task-Generierung

Der `--define` Befehl analysiert die Missionsbeschreibung auf Schlüsselwörter:

| Schlüsselwörter          | Generierte Goals                  |
|--------------------------|-----------------------------------|
| Stabilität, Crash, Robust | Analyse, Implementierung          |
| Performance, Speed        | Optimierung, Überwachung          |
| Integration, API          | Integration, Implementierung      |
| Überwachung, Monitor      | Überwachung, Analyse              |
| Automatisierung, Workflow | Implementierung, Integration      |

Pro Goal werden 2-3 Tasks generiert (zufällig aus Template-Pools).

## Priorisierungslogik (`--prioritize`)

Jede Mission bekommt eine Priorität (1-5) basierend auf:

1. **Impact**: Anzahl offener Tasks (mehr = höherer Impact)
2. **Dringlichkeit**: Alter der Mission (je älter, desto dringender)
3. **Deadline**: Falls gesetzt → näher am Termin = höhere Priorität
4. **Progress-Boost**: Falls ≥80% erledigt → +1 Priorität (Abschluss fördern)

Die Priorität wird als `★`-Sterne in der Liste dargestellt.

## Self-Execution Tick (`--tick`)

Der Tick führt den wichtigsten nächsten Task aus:

1. Findet den Task mit der höchsten Priorität (Mission-Prio × Task-Prio)
2. Markiert ihn als `running`
3. Sucht nach einem passenden Script (anhand `script_hint` oder Keyword-Matching)
4. Falls kein Script gefunden → Fallback-Analyse
5. Subprocess mit 300s Timeout
6. Markiert als `done` oder `failed`
7. Aktualisiert Goal-Progress
8. Cron-Job führt `--tick` alle 30 Minuten aus

## Exit-Codes

| Code | Bedeutung              |
|------|------------------------|
| 0    | Erfolg / nichts zu tun |
| 1    | Keine offenen Tasks    |
| 2    | Fehler / ID nicht gef. |

## Cron-Job

Ein Cron-Job (addiert via `jobs.json` im OpenAmer-Cron-Verzeichnis) führt `--tick` alle 30 Minuten aus:

```json
{
  "id": "goal_engine_tick",
  "name": "Goal Engine Tick",
  "script": "goal-engine.py --tick",
  "schedule": { "kind": "cron", "expr": "*/30 * * * *" }
}
```

## Workflow

1. **Mission definieren**: `--define 'Name' 'Beschreibung'`
2. **Priorisieren**: `--prioritize` (automatisch nach Impact + Dringlichkeit)
3. **Tick starten**: `--tick` oder Cron macht das automatisch alle 30min
4. **Fortschritt checken**: `--progress` (mit ETA und Blockers)
5. **Abschließen**: `--complete <id>` (Mission, Goal oder Task)
6. **Scannen**: `--scan` (Scripts, Skills, Gaps analysieren)

## Fehlerbehebung

- **Script findet kein passendes Script**: Manuell via `--add-task <goal_id> 'Task' --script <name.py>` verknüpfen
- **missions.json beschädigt**: Wird automatisch zurückgesetzt (leere Liste)
- **Cron läuft nicht**: `--scan` zeigt ob Goal-Engine Cron-Job fehlt
- **Task timeout**: Standard 300s, kann in der `subprocess.run()`-Zeile angepasst werden