---
title: "Auto Docs — Generate docs from live git+skills+cron state"
sidebar_label: "Auto Docs"
description: "Generate docs from live git+skills+cron state"
---

{/* This page is auto-generated from the skill's SKILL.md by website/scripts/generate-skill-docs.py. Edit the source SKILL.md, not this page. */}

# Auto Docs

Generate docs from live git+skills+cron state.

## Skill metadata

| | |
|---|---|
| Source | Bundled (installed by default) |
| Path | `skills/software-development\auto-docs` |

## Reference: full SKILL.md

:::info
The following is the complete skill definition that OpenAmer loads when this skill is triggered. This is what the agent sees as instructions when the skill is active.
:::

# Auto-Docs Skill

## Description

Generates four auto-documentation files from live project state:
- **README.md** — Projektübersicht, Features, Architektur, Installation, Usage
- **CHANGELOG.md** — Git-Commit-Messages, gruppiert nach Typ und Release-Tags
- **SKILLS-INDEX.md** — Alle installierten Skills mit Beschreibung, Kategorie, Tags
- **CRON-STATUS.md** — Alle Cron-Jobs mit Schedule, letztem Run, Status

## Trigger

Use this skill whenever:
- README, CHANGELOG, Skills-Index oder Cron-Status muss regeneriert werden
- Nach grossen Releases (mehrere neue Features)
- Vor Deployment- oder CI-Workflows
- Wenn der Benutzer sagt "Dokumentation aktualisieren" oder "auto-docs"

## Usage

```bash
# Alles auf einmal generieren
python scripts/auto-docs.py --all

# Nur bestimmte Dokumente
python scripts/auto-docs.py --readme       # Nur README
python scripts/auto-docs.py --changelog    # Nur CHANGELOG
python scripts/auto-docs.py --skills       # Nur Skills-Index
python scripts/auto-docs.py --cron         # Nur Cron-Status

# Leise (nur Fehlerausgabe)
python scripts/auto-docs.py --all --quiet
```

## Output

Alle generierten Dateien landen in `docs/generated/`:

<!-- ascii-guard-ignore -->
```
docs/generated/
├── README.md
├── CHANGELOG.md
├── SKILLS-INDEX.md
└── CRON-STATUS.md
```
<!-- ascii-guard-ignore-end -->

## Architecture

<!-- ascii-guard-ignore -->
```
scripts/auto-docs.py
├── get_project_stats()    → Sammelt Kennzahlen (LOC, Files, Autoren, Tags)
├── generate_readme()      → README.md mit Architektur + Features
├── generate_changelog()   → CHANGELOG.md aus git log (seit letztem Tag)
├── generate_skills_index()→ SKILLS-INDEX.md aus Skills-Verzeichnis
├── generate_cron_status() → CRON-STATUS.md aus cron/jobs.json
└── main()                 → CLI-Parser + Dispatch
```
<!-- ascii-guard-ignore-end -->

## Dependencies

- Python 3.11+
- `git` CLI (für Changelog + Metriken)
- `subprocess`, `json`, `re`, `pathlib`, `datetime`, `collections` (stdlib)
- Zugriff auf OpenAmer-Skills (`OPENAMER_HOME/skills/`)
- Zugriff auf Cron-Jobs (`OPENAMER_HOME/cron/jobs.json`)

## Cron-Job

The cron job `auto_docs_24h` runs every 1440 minutes (24h) and calls `python scripts/auto-docs.py --all`.

## Pitfalls

- **Grosses CHANGELOG**: Bei vielen Commits (18158 im Repo) kann die Ausgabe mehrere MB erreichen. Das ist normal.
- **Skills ohne Beschreibung**: Skills ohne `description:` im Frontmatter erscheinen mit "Keine Beschreibung".
- **Keine Git-Tags**: Wenn kein Release-Tag existiert, wird der gesamte Commit-Verlauf ausgegeben.
- **Windows-Pfade**: Der Skript sucht Skills standardmässig in `%USERPROFILE%/AppData/Local/openamer-laptop/skills`.

## Verification

Nach dem Lauf prüfen:
```bash
ls -la docs/generated/
# Sollte 4 Dateien enthalten: README.md, CHANGELOG.md, SKILLS-INDEX.md, CRON-STATUS.md
```
