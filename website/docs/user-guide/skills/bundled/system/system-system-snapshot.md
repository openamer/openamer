---
title: "System Snapshot — Use for full system-state snapshot + diff + HTTP:8898"
sidebar_label: "System Snapshot"
description: "Use for full system-state snapshot + diff + HTTP:8898"
---

{/* This page is auto-generated from the skill's SKILL.md by website/scripts/generate-skill-docs.py. Edit the source SKILL.md, not this page. */}

# System Snapshot

Use for full system-state snapshot + diff + HTTP:8898.

## Skill metadata

| | |
|---|---|
| Source | Bundled (installed by default) |
| Path | `skills/system\system-snapshot` |
| Version | `1.0.0` |
| Author | OpenAmer Agent |
| Platforms | windows |
| Tags | `system`, `snapshot`, `monitoring`, `health`, `diff` |

## Reference: full SKILL.md

:::info
The following is the complete skill definition that OpenAmer loads when this skill is triggered. This is what the agent sees as instructions when the skill is active.
:::

# System Snapshot

Vollständiger Systemzustand auf einen Blick: OS, Skripte, Skills, Cron, Health, Security, Backup, Sessions.

## Overview

Erfasst den kompletten Zustand des OpenAmer-Systems als strukturiertes JSON und stellt Diff-Funktionen und einen HTTP-Server bereit.

## When to Use

- `--now` für einmaligen Snapshot
- `--diff` um Änderungen zum letzten Snapshot zu sehen
- `--serve` für Live-API auf Port 8898
- `--list` um alle Snapshots anzuzeigen

## Usage

```bash
python scripts/system-snapshot.py --now
python scripts/system-snapshot.py --diff
python scripts/system-snapshot.py --serve
python scripts/system-snapshot.py --compare A.json B.json
python scripts/system-snapshot.py --list
```

## Verification

```bash
python scripts/system-snapshot.py --now && echo "Snapshot OK"
```

## Troubleshooting

| Problem | Lösung |
|---------|--------|
| Kein vorheriger Snapshot | `--diff` zeigt Fehler, einfach `--now` zuerst |
| Port 8898 belegt | Anderen Port verwenden oder Prozess beenden |
