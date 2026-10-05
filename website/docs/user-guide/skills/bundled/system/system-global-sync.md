---
title: "Global Sync — Use for multi-machine HTTP delta sync with peer management"
sidebar_label: "Global Sync"
description: "Use for multi-machine HTTP delta sync with peer management"
---

{/* This page is auto-generated from the skill's SKILL.md by website/scripts/generate-skill-docs.py. Edit the source SKILL.md, not this page. */}

# Global Sync

Use for multi-machine HTTP delta sync with peer management.

## Skill metadata

| | |
|---|---|
| Source | Bundled (installed by default) |
| Path | `skills/system\global-sync` |

## Reference: full SKILL.md

:::info
The following is the complete skill definition that OpenAmer loads when this skill is triggered. This is what the agent sees as instructions when the skill is active.
:::

# Global State Sync

Multi-Machine State Synchronization für OpenAmer.

## Überblick

Global State Sync synchronisiert OpenAmer-Zustände (Skills, Cron, Scripts, Config, Sessions)
zwischen mehreren Maschinen über HTTP. Nur geänderte Dateien seit dem letzten Sync werden
übertragen (Delta-Only). Bei Timestamp-Konflikten gewinnt die neuere Version; die verlierende
Version wird in `.global-sync/conflicts/` gespeichert.

## Architektur

<!-- ascii-guard-ignore -->
```
+-------------------+          HTTP POST /sync           +-------------------+
|  Maschine A       |  ──────────────────────────────►   |  Maschine B       |
|  Port 8902        |  JSON-Delta + SHA256-Signatur      |  Port 8902        |
|  Sync-Thread 60m  |  ◄──────────────────────────────   |  Sync-Thread 60m  |
+-------------------+          JSON-Delta + Signatur     +-------------------+
```
<!-- ascii-guard-ignore-end -->

## Installation

Das Script liegt unter `scripts/global-sync.py` (OpenAmer Home) und wird via
Config in `.global-sync/config.json` gesteuert.

## Verwendung

```bash
# Status anzeigen
python scripts/global-sync.py --status

# Peer hinzufügen
python scripts/global-sync.py --add-peer mein-server 192.168.1.100:8902

# Sofort syncen
python scripts/global-sync.py --sync-now

# Server starten (Daemon-Modus)
python scripts/global-sync.py --start

# Peer-Liste anzeigen
python scripts/global-sync.py --peers

# Neues Token setzen
python scripts/global-sync.py --token MEIN_NEUES_SICHERES_TOKEN
```

## Konfiguration

`.global-sync/config.json`:

```json
{
  "peers": [
    {"name": "server1", "host": "192.168.1.100", "port": 8902}
  ],
  "sync_interval_minutes": 60,
  "sync_items": ["skills", "cron", "scripts", "config", "sessions"],
  "token": "DEIN_SICHERES_TOKEN",
  "server_port": 8902
}
```

### sync_items
- `skills` — OpenAmer Skills
- `cron` — Cron-Job-Definitionen
- `scripts` — Python-Scripte
- `config` — config.yaml
- `sessions` — Session-Dumps

## Sicherheit

- Jeder Request enthält einen SHA256-HMAC über den Body.
- Der Shared-Token wird in der Config gespeichert.
- Nur der SHA256-Hash des Tokens wird im Header übertragen.
- Port 8902 sollte hinter einer Firewall liegen.

## Konfliktlösung

| Bedingung | Ergebnis |
|-----------|----------|
| Remote neuer als lokal | Remote-Version überschreibt lokale |
| Lokal neuer als remote | Lokale Version bleibt; Remote in `.global-sync/conflicts/` |
| Gleicher Timestamp | Remote gewinnt (idempotent) |

## Dateien

| Pfad | Beschreibung |
|------|-------------|
| `~/.global-sync/config.json` | Sync-Konfiguration |
| `~/.global-sync/conflicts/` | Konflikt-Dateien |
| `~/.global-sync/last_sync.txt` | Timestamp des letzten Syncs |
| `scripts/global-sync.py` | Hauptscript |

## Cron-Job

Ein Cron-Job führt `--sync-now` alle 60 Minuten aus.
