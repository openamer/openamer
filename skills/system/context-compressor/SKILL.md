---
name: context-compressor
title: Context Compressor
description: Use for session compression and full-text search.
---

# Context Compressor

Intelligente Session-Komprimierung aus der OpenAmer `state.db`:
- **Komprimiert** Session-Transkripte um 60-80% durch Redundanz-Entfernung
- **Extrahiert** Entscheidungen, Action-Items, Learnings und offene Punkte
- **Volltextsuche** über alle komprimierten Sessions
- **Batch-Archivierung** aller Sessions in JSON-Archiven

## Standort

- **Script:** `C:\Users\damir\AppData\Local\openamer-laptop\scripts\context-compressor.py`
- **Archiv:** `C:\Users\damir\AppData\Local\openamer-laptop\context-compressor\archives\`
- **Index:** `C:\Users\damir\AppData\Local\openamer-laptop\context-compressor\index.json`

## CLI-Übersicht

| Flag | Beschreibung |
|------|-------------|
| `--session <id>` | Einzelne Session komprimieren → JSON on stdout |
| `--batch [Tage]` | Alle Sessions älter als N Tage archivieren (default: 7) |
| `--stats` | Kompressionsrate + Extraktions-Statistiken anzeigen |
| `--search <query>` | Volltextsuche in allen komprimierten Sessions |

## Beispiel

```bash
# Einzelne Session komprimieren
python scripts/context-compressor.py --session 20260821_233243_387822

# Batch-Verarbeitung (alle Sessions >7 Tage)
python scripts/context-compressor.py --batch

# Alle Sessions verarbeiten (auch aktuelle)
python scripts/context-compressor.py --batch 0

# Statistiken anzeigen
python scripts/context-compressor.py --stats

# Volltextsuche
python scripts/context-compressor.py --search "API-Key"
python scripts/context-compressor.py --search "entscheidung"
```

## Ausgabe-Struktur (pro Session)

```json
{
  "session_id": "20260821_233243_387822",
  "title": "...",
  "raw_chars": 59414,
  "compressed_chars": 4756,
  "compression_percent": "92.0%",
  "decisions": ["..."],
  "action_items": ["..."],
  "learnings": ["..."],
  "open_points": ["..."],
  "messages": [
    {"id": 24014, "role": "user", "compressed": "...", "original_len": 89, "compressed_len": 89},
    {"id": 24016, "role": "tool", "compressed": "[JSON] keys=[...]", "original_len": 8125, "compressed_len": 221}
  ]
}
```

## Kompressions-Strategie

1. **Boilerplate entfernen:** `<antthinking>`, `<tool_call>`, lange Code-Blöcke
2. **Duplikat-Sätze entfernen:** Wiederholungen innerhalb derselben Nachricht
3. **Tool-Outputs massiv kürzen:**
   - JSON-Outputs → `[JSON] keys=[...]` (auf Schlüssel reduziert)
   - Lange Tool-Outputs → auf max 200 Zeichen gekürzt
4. **Entscheidungen extrahieren:** Pattern-basiert (DE + EN)
5. **Deduplizieren:** Gleiche Entscheidungen/Actions nur einmal

## Datenquelle

- **state.db** aus `OPENAMER_HOME` (default: `C:\Users\damir\AppData\Local\openamer-laptop\state.db`)
- **Tabellen:** `sessions`, `messages`
- **Komprimierte Sessions:** `context-compressor/archives/batch_<timestamp>.json`