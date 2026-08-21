---
name: code-generator
category: software-development
description: Scaffolding für Scripts, Skills und Plugins aus Templates.
---

# Code Generator

Scaffolding für neue OpenAmer-Scripts, Skills und Plugins aus eingebauten Templates.
CLI-Tool mit 4 Modi, OPENAMER_TOOL-Konvention, Exit-Codes und JSON-Output.

## Usage

```bash
# Hilfe
python scripts/code-generator.py --help

# 1) Script generieren
python scripts/code-generator.py --script mein-tool --desc "Mein neues Tool" [--cron 30min]

# 2) Skill generieren
python scripts/code-generator.py --skill mein-skill --desc "Mein neuer Skill" --category system

# 3) Plugin generieren
python scripts/code-generator.py --plugin mein-plugin --desc "Mein Desktop Plugin"

# 4) Templates auflisten
python scripts/code-generator.py --list
python scripts/code-generator.py --list --json
```

## Modi

### --script NAME
Generiert `scripts/<name>.py` mit:
- Shebang (`#!/usr/bin/env python3`)
- Docstring mit OPENAMER_TOOL-Konvention (Tool-Beschreibung, Exit-Codes, JSON-Output-Struktur)
- Standard-Imports (argparse, json, os, sys, datetime, pathlib, typing)
- `OPENAMER_HOME`-Pfadlogik
- `create_parser()` mit `--json`, `--verbose`
- `run()` Funktion
- `main()` mit Error-Handling (ValueError → Exit 1, PermissionError → Exit 2, ImportError → Exit 3)
- `if __name__ == "__main__"`-Guard
- Optionaler Cron-Block (`--cron 30min` → 1800s Intervall)
- Option `--no-exit-codes` zum Weglassen der Exit-Code-Doku

### --skill NAME --desc BESCHREIBUNG --category KATEGORIE
Generiert `skills/<kategorie>/<name>/SKILL.md` mit:
- YAML-Frontmatter (name, category, description)
- Usage-Sektion (CLI-Befehl, Skill-Config)
- Implementation-Sektion
- Verification-Sektion
- Exit-Codes-Tabelle
- JSON-Output-Beispiel

Kategorien: system, devops, security, software-development, autonomous-ai-agents, creative, desktop, email, github, imported, marketing, media, mlops, note-taking, productivity, research, smart-home, social-media

### --plugin NAME
Generiert `desktop-plugins/examples/<name>/` mit:
- `__init__.py` (Plugin-Hooks: on_load, on_unload, execute + optionales CLI-Main)
- `plugin.yaml` (Metadaten, Hooks, Tags)

### --list
Listet alle verfügbaren Templates mit ihren Args, Typen und Dateien.

## Exit Codes

| Code | Bedeutung             |
|------|-----------------------|
| 0    | Erfolg                |
| 1    | Fehler (Args, Exist)  |
| 2    | Schreibfehler         |
| 3    | Abhängigkeitsfehler   |

## Templates

Die Templates sind als Dict im Code von `scripts/code-generator.py` eingebettet (Dict `TEMPLATES`).
Roh-Kopien liegen in `.code-generator/templates/` zur Referenz.

Verfügbare Templates:
- **script**: Python-Script mit Shebang, Argparse, Exit-Codes, JSON-Output
- **skill**: SKILL.md mit Frontmatter, Usage, Implementation, Verification
- **plugin**: Desktop-Plugin mit `__init__.py` + `plugin.yaml`

## JSON Output

Alle Modi unterstützen `--json` für maschinenlesbare Ausgabe:

```json
{
  "tool": "code-generator",
  "version": "1.0.0",
  "status": "ok",
  "output": {
    "mode": "script",
    "name": "mein-tool",
    "path": "C:/.../scripts/mein-tool.py",
    "cron": "30min",
    "exit_codes": true
  }
}
```

## Verification

```bash
# Test: Hilfe anzeigen
python scripts/code-generator.py --help

# Test: Script generieren
python scripts/code-generator.py --script test-tool --desc "Test Tool" --json

# Test: Skill generieren
python scripts/code-generator.py --skill test-skill --desc "Test Skill" --category system --json

# Test: Plugin generieren
python scripts/code-generator.py --plugin test-plugin --desc "Test Plugin" --json

# Test: Templates auflisten
python scripts/code-generator.py --list --json

# Aufräumen
rm -f scripts/test-tool.py
rm -rf skills/system/test-skill
rm -rf desktop-plugins/examples/test-plugin
```

## Implementation

Script: `scripts/code-generator.py`
Templates: `.code-generator/templates/`
Skill: `skills/software-development/code-generator/SKILL.md`

Das Tool verwendet:
- `argparse` für CLI-Parsing (Mutually Exclusive Group für Modi)
- `textwrap.dedent` für saubere Einrückung der Templates
- `pathlib.Path` für Plattform-unabhängige Pfade
- `slugify()` für konsistente Dateinamen
- `render_template()` für `{{placeholder}}`-Ersetzung