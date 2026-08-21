---
name: code-intelligence
description: Use for AST/dep graph/complexity analysis of Python code.
trigger: code intelligence, ast parsing, dependency graph, complexity analysis, refactoring
domain: software-development
version: 2.0.0
---

# Code Intelligence Graph

AST-Parsing + Dependency-Graph + Complexity-Analyse + Refactoring-Vorschläge + HTML-Report für Python-Codebasen.

## Überblick

`scripts/code-intelligence.py` scannt alle `.py`-Dateien in `openamer_cli/`, `scripts/` und `tests/`, baut einen vollständigen AST-basierten Code-Intelligence-Graph und exportiert:

- **Funktionen**: Name, Argumente, Rückgabetyp, Zeilen, Docstring, McCabe-Complexity
- **Klassen**: Name, Basisklassen, Methoden, Attribute, Docstring
- **Imports**: Modul, Namen, Aliase, interne/extern
- **Abhängigkeiten**: Welche Datei importiert welche andere (intern + extern)
- **Zirkuläre Imports**: Erkennt gegenseitige Import-Ketten

## CLI-Modi

| Flag | Beschreibung |
|------|-------------|
| `--build` | Scanner alle .py-Dateien und baut den Graph neu |
| `--query TERM` | Findet alle Referenzen zu Funktion/Klasse/Datei |
| `--deps FILE` | Zeigt Abhängigkeiten einer Datei |
| `--complexity` | Top-N komplexeste Funktionen (McCabe) |
| `--suggest-refactor` | Analysiert Graph & findet Refactoring-Kandidaten |
| `--report` | Generiert HTML-Report mit D3.js-Graph-Visualisierung |
| `--json` | Machine-readable JSON-Output |
| `--no-cache` | Ignoriert Cache, baut immer neu |
| `--top N` | Top N für `--complexity` (default: 10) |

## Verwendung

```bash
# Graph bauen
python scripts/code-intelligence.py --build

# Nach Funktionen/Dateien suchen
python scripts/code-intelligence.py --query 'cmd_cron'
python scripts/code-intelligence.py --query 'KanbanBoard'

# Abhängigkeiten anzeigen
python scripts/code-intelligence.py --deps 'openamer_cli/cron.py'

# Komplexität
python scripts/code-intelligence.py --complexity --top 20

# Refactoring-Vorschläge
python scripts/code-intelligence.py --suggest-refactor

# HTML-Report (mit D3.js Graph)
python scripts/code-intelligence.py --report

# Bauen + Report in einem Schritt
python scripts/code-intelligence.py --build --report
```

## Exit-Codes

| Code | Bedeutung |
|------|-----------|
| 0 | Erfolg |
| 1 | Fehler (ungültige Argumente) |
| 2 | Graph nicht gefunden |
| 3 | Abhängigkeitsfehler |

## Graph-Daten

Der Graph wird gespeichert als JSON unter:
`C:\Users\damir\AppData\Local\openamer-laptop\.code-intelligence\graph.json`

Struktur:
```json
{
  "meta": { "built_at": "...", "total_files": 2852, ... },
  "nodes": [
    {
      "file": "openamer_cli/cron.py",
      "lines": 500,
      "functions": [{ "name": "cron_list", "complexity": 18, ... }],
      "classes": [],
      "imports": [{ "module": "json", ... }],
      "internal_deps": ["openamer_cli/colors.py"]
    }
  ],
  "edges": [
    { "from": "openamer_cli/cron.py", "to": "openamer_cli/colors.py", "type": "import" }
  ]
}
```

## Analyse-Kategorien (--suggest-refactor)

1. **Zu große Dateien** (>400 / >800 Zeilen)
2. **Hochkomplexe Funktionen** (CX ≥ 10)
3. **Zirkuläre Imports**
4. **Skript-artige Dateien** (keine Funktionen/Klassen, >50 Zeilen)
5. **Meistgenutzte Imports**
6. **Lange Funktionen/Methoden** (≥80 Zeilen)

## Cron-Job

Der Graph wird automatisch alle 24h via Cron-Job neu gebaut:
`0 */24 * * * python scripts/code-intelligence.py --build`

## Fehlerbehebung

- **"Verzeichnis nicht gefunden"**: Die Scan-Dirs sind relativ zum REPO_DIR. Setze `REPO_DIR` in der Datei oder führe aus dem Repo-Root aus.
- **Große Graphen**: Bei 2800+ Dateien kann der Build 10-60 Sekunden dauern. Der Cache wird automatisch beim nächsten `--build` aktualisiert.
- **Kein D3.js im Report**: Der HTML-Report lädt D3.js via CDN (`d3js.org`). Bei fehlender Internetverbindung wird kein Graph gerendert, die Tabelle bleibt lesbar.