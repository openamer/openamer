---
title: "Cross Profile Sync — Sync skills/cron/config between OpenAmer profiles"
sidebar_label: "Cross Profile Sync"
description: "Sync skills/cron/config between OpenAmer profiles"
---

{/* This page is auto-generated from the skill's SKILL.md by website/scripts/generate-skill-docs.py. Edit the source SKILL.md, not this page. */}

# Cross Profile Sync

Sync skills/cron/config between OpenAmer profiles.

## Skill metadata

| | |
|---|---|
| Source | Bundled (installed by default) |
| Path | `skills/system\cross-profile-sync` |

## Reference: full SKILL.md

:::info
The following is the complete skill definition that OpenAmer loads when this skill is triggered. This is what the agent sees as instructions when the skill is active.
:::

# Cross-Profile Sync

## Beschreibung

Autonomes Tool zum Synchronisieren, Diffen und Mergen von OpenAmer-Profilen.
Skills, Cron-Jobs und Konfiguration zwischen Profilen (z. B. `dev`, `work`, `default`) abgleichen.

## Komponenten

<!-- ascii-guard-ignore -->
```
openamer-laptop/
├── scripts/cross-profile-sync.py   # Das Hauptskript
├── skills/cross-profile-sync/       # Dieser Skill (Dokumentation)
├── cron/jobs.json                   # Cron-Job für 24h-Diff
└── profiles/
    ├── dev/
    ├── work/
    └── .snapshots/
```
<!-- ascii-guard-ignore-end -->

## Funktionen

1. **`--sync source target`** — Skills, Cron und Config von source nach target kopieren
2. **`--diff a b`** — Strukturierte Unterschiede anzeigen
3. **`--merge a b output`** — Zwei Profile vereinigen (newest wins)
4. **`--dry-run`** — Nur Vorschau (Default)
5. **`--force`** — Wirklich ausführen
6. **`--list`** — Alle Profile anzeigen

## Sicherheit

- Dry-Run ist DEFAULT — ohne --force passiert nichts
- Before-Snapshot vor jeder Aktion
- Logging in logs/cross-profile-sync.log
- Merge-Konflikte in logs/merge-report.json

## Verwendung

```bash
# Diff
python3 "$OPENAMER_HOME/scripts/cross-profile-sync.py" --diff dev work

# Sync (Dry-Run)
python3 "$OPENAMER_HOME/scripts/cross-profile-sync.py" --sync dev work --dry-run

# Sync (wirklich)
python3 "$OPENAMER_HOME/scripts/cross-profile-sync.py" --sync dev work --force

# Merge
python3 "$OPENAMER_HOME/scripts/cross-profile-sync.py" --merge dev work merged --force
```

## Cron-Job (alle 24h)

```yaml
name: cross-profile-diff-report
schedule: "0 4 * * *"
script: scripts/cross-profile-sync.py
prompt: >
  Führe Cross-Profile Diff für alle Profile aus und melde
  dem Parent, wenn Unterschiede gefunden wurden.
```
