---
name: skill-validator
description: 'Use for 100-point QA validation of all skills + auto-fix + report.'
version: 1.0.0
author: OpenAmer Agent
license: MIT
tags:
  - validation
  - quality
  - skills
  - qa
  - report
  - auto-fix
platforms: [linux, macos, windows]
metadata:
  openamer:
    tags: [validation, quality, skills, QA, report, auto-fix, cron]
    related_skills: [auto-env-checker, smart-cron-scheduler]
---

# Skill Validator

Automatisierte 100-Punkte-Qualitätsprüfung für alle OpenAmer Skills.
Validiert Frontmatter, Description-Qualität, Body-Struktur, Cross-Refs und CLI-Commands.

## Overview

Der Skill Validator prüft alle 659 SKILL.md Dateien gegen 5 Kategorien:

| Kategorie | Punkte | Beschreibung |
|-----------|--------|--------------|
| Frontmatter | 30 | name, description, version, tags, platforms, metadata.openamer |
| Description | 15 | ≤57 Zeichen, Trigger-Wort, sinnvolle Länge |
| Body-Struktur | 25 | Sections (Overview, Usage, etc.), Code-Blöcke, Tabellen |
| Cross-Refs | 15 | related_skills existieren, Selbstverweise, keine broken Links |
| Commands/CLI | 15 | openamer-Befehle, bash-Blöcke, Exit-Codes, Setup-Befehle |

## When to Use

- **Täglich**: `--all --json` für kontinuierliche Qualitätsüberwachung
- **Nach Skill-Importen**: `--all --fix` um neue Skills automatisch zu korrigieren
- **Vor Releases**: `--all --html` für visuellen Qualitätsbericht
- **Bei Problemen**: `--skill <name>` für gezielte Einzelprüfung
- **Fokus**: `--best` (Top 10) oder `--worst` (Bottom 10) für schnelle Übersicht

## Installation

Das Skript liegt unter `scripts/skill-validator.py` und wird direkt ausgeführt:

```bash
# Prüfen ob vorhanden
python scripts/skill-validator.py --version 2>/dev/null || echo "Script bereit"
```

Keine zusätzlichen Dependencies erforderlich (nur Python 3.10+ Standardbibliothek).

## Usage

### Alle Skills prüfen

```bash
python scripts/skill-validator.py --all
```

### Einzelnen Skill prüfen

```bash
python scripts/skill-validator.py --skill github-pr-workflow --verbose
```

### Auto-Fix

```bash
python scripts/skill-validator.py --all --fix
```
Korrigiert automatisch:
- Fehlendes Frontmatter → minimales Frontmatter hinzufügen
- Fehlende `metadata.openamer` → leeren Block hinzufügen
- Fehlende `platforms` → `[linux, macos, windows]`
- Fehlende `version` → `1.0.0`

### JSON-Report

```bash
python scripts/skill-validator.py --all --json --output logs/skill-validator-report.json
```

### HTML-Report

```bash
python scripts/skill-validator.py --all --html --output logs/skill-validator-report.html
```

Generiert ein interaktives Dashboard mit:
- Notenverteilung (A+ bis F)
- Kategorien-Balkendiagramme
- Beste/Schlechteste Skills
- Top-Probleme
- Vollständige Liste aller Skills mit Einzelscores

### Best/Worst

```bash
# Top 10 beste Skills
python scripts/skill-validator.py --best

# Top 10 schlechteste (mit Problemen)
python scripts/skill-validator.py --worst --verbose
```

## Verification

Nach der Installation prüfen:

```bash
# Kurztest mit Einzel-Skill
python scripts/skill-validator.py --skill auto-env-checker
# Erwartet: Score zwischen 30-70, gültiges Frontmatter

# JSON-Ausgabe testen
python scripts/skill-validator.py --skill plan --json | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'OK: Score={d[\"skill_results\"][0][\"score\"]}')"

# HTML-Report testen
python scripts/skill-validator.py --skill plan --html --output /tmp/test-report.html
# Erwartet: report.html existiert und ist > 10KB
```

## Troubleshooting

| Problem | Ursache | Lösung |
|---------|---------|--------|
| "Kein gültiges YAML-Frontmatter" | SKILL.md hat kein --- Block | `--fix` verwenden oder manuell hinzufügen |
| Alle Skills zeigen 0 Punkte | Frontmatter-Parser Problem | Pfad zu skills/ prüfen |
| HTML-Report leer | Fehler in der HTML-Generierung | `--json` stattdessen nutzen |
| Exit-Code 127 | 127+ Skills mit Note F | Normal bei vielen importierten Skills; keine Sorge |
| Langsame Ausführung (659 Skills) | Erwartet, ~60-90 Sekunden | Mit `--json --output` für schnelle Speicherung |

## Pitfalls

- **Frontmatter wichtig**: Ohne gültiges Frontmatter gibt es 0 Punkte — immer `--fix` nach Import neuer Skills
- **metadata.openamer**: Wird nur erkannt wenn korrekt eingerückt (2 Spaces pro Level)
- **Große Reports**: Der JSON-Report aller Skills ist ~12 MB — HTML-Dashboard ist besser lesbar
- **False Positives**: Importierte NVIDIA Skills haben oft fehlende Sections (erwartet)
- **Exit-Code**: Wird auf 127 gecappt da OS-Limit für Exit-Codes