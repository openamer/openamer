---
title: "Task Queue — Use for persistent task-queue with priorities + daemon"
sidebar_label: "Task Queue"
description: "Use for persistent task-queue with priorities + daemon"
---

{/* This page is auto-generated from the skill's SKILL.md by website/scripts/generate-skill-docs.py. Edit the source SKILL.md, not this page. */}

# Task Queue

Use for persistent task-queue with priorities + daemon.

## Skill metadata

| | |
|---|---|
| Source | Bundled (installed by default) |
| Path | `skills/system\task-queue` |
| Version | `1.0.0` |
| Author | OpenAmer Agent |
| Platforms | linux, macos, windows |
| Tags | `queue`, `tasks`, `scheduler`, `daemon`, `automation` |

## Reference: full SKILL.md

:::info
The following is the complete skill definition that OpenAmer loads when this skill is triggered. This is what the agent sees as instructions when the skill is active.
:::

# Task Queue

Persistente JSON-basierte Task-Queue mit Prioritäten, Daemon-Modus und Retry.

## Overview

Verwaltet asynchrone Tasks mit Priorität 1-5, automatischer Verarbeitung im Daemon-Modus und Retry-Logik.

## When to Use

- `--add` um Tasks in die Queue zu stellen
- `--process` für manuelle Verarbeitung
- `--daemon` für automatische Verarbeitung alle 10s
- `--list` für Queue-Übersicht
- `--stats` für Metriken

## Usage

```bash
python scripts/task-queue.py --add '{"type":"backup","payload":{},"priority":1}'
python scripts/task-queue.py --list --status pending
python scripts/task-queue.py --process
python scripts/task-queue.py --stats
python scripts/task-queue.py --retry <id>
python scripts/task-queue.py --cancel <id>
```

## Verification

```bash
python scripts/task-queue.py --add '{"type":"test","payload":{"cmd":"echo ok"},"priority":3}' && python scripts/task-queue.py --process && python scripts/task-queue.py --stats
```

## Troubleshooting

| Problem | Lösung |
|---------|--------|
| Race-Condition im Daemon | Wurde via RLock + atomare Updates gefixt |
| Queue-Korruption | `queue.json` manuell reparieren oder löschen |
