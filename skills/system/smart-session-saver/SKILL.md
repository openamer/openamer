---
name: smart-session-saver
title: Smart Session Saver
description: Use for session archiving, search, restore, and stats.
---

# Smart Session Saver

Automatische Session-Archivierung + Volltextsuche + Wiederherstellung + Metrik-Stats. Arbeitet nur auf Metadaten — **keine Datenlöschung**.

## Standort

- **Script:** `C:\Users\damir\scripts\smart-session-saver.py`
- **Repo:** `C:\Users\damir\openamer-repo\scripts\smart-session-saver.py`
- **Archiv:** `C:\Users\damir\AppData\Local\openamer-laptop\.session-archive\`

## CLI-Übersicht

| Flag | Beschreibung |
|------|-------------|
| `--archive` | Archiviere Sessions >7 Tage als JSON in `.session-archive/YYYY-MM/` |
| `--list` | Liste alle archivierten Sessions |
| `--search QUERY` | Volltextsuche in allen Archiven |
| `--restore SESSION_ID` | Stelle Session-Metadaten als JSON wieder her |
| `--stats` | Metrik-Statistiken anzeigen |
| `--dry-run` | Nur zeigen, nichts archivieren |
| `--age N` | Alter in Tagen überschreiben (default: 7) |
| `--db PATH` | Alternativer Pfad zur Session-DB |

## Beispiele

```bash
# Archivieren (Sessions >7 Tage)
python scripts/smart-session-saver.py --archive

# Trockenlauf
python scripts/smart-session-saver.py --archive --dry-run

# Alle Archive auflisten
python scripts/smart-session-saver.py --list

# Volltextsuche
python scripts/smart-session-saver.py --search "Feature X"

# Session wiederherstellen
python scripts/smart-session-saver.py --restore 20260818_104355

# Dashboard mit Metriken
python scripts/smart-session-saver.py --stats

# Mit anderem Alter
python scripts/smart-session-saver.py --archive --age 3
```

## Cron-Job

Der Cron-Job läuft alle 1440m (24h, `--archive`) über den OpenAmer-Cron-Scheduler unter dem Namen `Smart Session Saver Archive`.

## Archiv-Struktur

```
.session-archive/
├── 2026-08/
│   ├── 2026-08-18_20260818_104355_6c4c49.json
│   └── ...
└── 2026-09/
    └── ...
```

Jede JSON-Datei enthält Session-Metadaten (Modell, Token, Kosten, Titel), die letzten 5 Nachrichten, und lesbare Zeitstempel.

## Datenquellen

- **Session-DB:** `state.db` aus `OPENAMER_HOME`
- **Tabellen:** `sessions`, `messages`
- **Schema:** `id`, `title`, `started_at`, `ended_at`, `message_count`, `input_tokens`, `output_tokens`, `model`, `archived`, `pinned`