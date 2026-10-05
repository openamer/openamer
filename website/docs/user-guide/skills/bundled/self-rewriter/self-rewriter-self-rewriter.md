---
title: "Self Rewriter — Use for Self-Rewriting Core: AST analyze, patch, commit"
sidebar_label: "Self Rewriter"
description: "Use for Self-Rewriting Core: AST analyze, patch, commit"
---

{/* This page is auto-generated from the skill's SKILL.md by website/scripts/generate-skill-docs.py. Edit the source SKILL.md, not this page. */}

# Self Rewriter

Use for Self-Rewriting Core: AST analyze, patch, commit.

## Skill metadata

| | |
|---|---|
| Source | Bundled (installed by default) |
| Path | `skills/self-rewriter` |
| Author | OpenAmer |

## Reference: full SKILL.md

:::info
The following is the complete skill definition that OpenAmer loads when this skill is triggered. This is what the agent sees as instructions when the skill is active.
:::

# Self-Rewriting Core Skill

Der Self-Rewriter ist ein autonomes Core-Evolution-Tool, das das `openamer_cli/` Verzeichnis
auf Ineffizienzen scannt, Patches generiert, validiert und automatisch committed.

## Standort

- **Script**: `C:\Users\damir\openamer-repo\scripts\self-rewriter.py`
- **Cron-Kopie**: `$OPENAMER_HOME\scripts\self-rewriter.py`
- **Arbeitsverzeichnis**: `.rewriter/` im Repository-Root
  - `pending/` — generierte Patches (unified diff)
  - `applied/` — angewandte Patches (Archiv)
  - `reports/latest.json` — letzter Scan-Report

## CLI-Usage

```bash
python scripts/self-rewriter.py --scan              # Core analysieren
python scripts/self-rewriter.py --suggest           # Verbesserungen anzeigen
python scripts/self-rewriter.py --patch             # Patches generieren (max 3)
python scripts/self-rewriter.py --apply             # Patches validieren + commiten + mergen
python scripts/self-rewriter.py --all               # Full Cycle (scan -> patch -> apply)
python scripts/self-rewriter.py --all --dry-run     # Full Cycle nur anzeigen
python scripts/self-rewriter.py --scan --max-patches 5
python scripts/self-rewriter.py --apply --yes       # Non-interactive apply
python scripts/self-rewriter.py --repo /pfad/zum/repo --scan
```

## Exit-Codes

| Code | Bedeutung |
|------|-----------|
| 0 | Nichts zu tun — alles sauber |
| 1 | Patches verfuegbar (issues gefunden) |
| 2 | Patches angewandt und committed |

## Was wird analysiert (AST-basiert)

1. **Doppelte Imports** — selbes Modul mehrfach importiert
2. **Zu lange Funktionen** — > 100 Zeilen
3. **Fehlende Type Hints** — Parameter/Rueckgabewert ohne Type Annotation
4. **Leere except-Bloecke** — `except: pass` (sicherheitsrelevant)
5. **TODO/FIXME-Kommentare** — markierte Stellen im Code

## Patches & Git-Workflow

1. Branch `rewriter-tmp` wird von `main` erstellt
2. Patches werden via `patch -p0` / `patch -p1` angewandt
3. `py_compile` validiert die Syntax
4. Bei Erfolg: Commit + Merge zurueck zu `main` (--no-ff)
5. Branch wird geloescht
6. Angewandte Patches wandern von `pending/` -> `applied/`

## Cron-Job (alle 6h)

Der Cron-Job `self-rewriter-scan` laeuft alle 360 Minuten (6h) und fuehrt
`self-rewriter.py --scan` aus. Er prueft ob neue Issues aufgetaucht sind
und postet nur bei Aenderungen einen Report.

## Troubleshooting

- **"Core-Verzeichnis nicht gefunden"**: Script sucht in `~/openamer-repo/` und Umgebung.
  Mit `--repo /absoluter/pfad` explizit angeben.
- **Patch-Apply schlaegt fehl**: Patches arbeiten gegen den aktuellen `main`-Branch.
  Bei Konflikten sind manuelle Eingriffe noetig — der rewriter-tmp Branch bleibt dann bestehen.
- **Report nicht gefunden**: `--suggest` und `--patch` brauchen einen vorherigen `--scan`-Report.
