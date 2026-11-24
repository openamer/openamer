# OpenAmer Session-Daten-Architektur

## Datenquellen für Analyse & Training

### 1. state.db (PRIMARY — die echte Session-Datenbank)

**Pfad:** `<OPENAMER_HOME>/state.db`

**Haupttabelle: `messages`** — alle Chat-Nachrichten + Tool-Aufrufe.

Schema:

| Spalte | Typ | Bedeutung |
|--------|-----|-----------|
| `id` | INTEGER | Auto-Increment-PK |
| `session_id` | TEXT | Session-Ident (z.B. `20260921_013030_4536c3`, `cron_91a6a02a6148_20260921_013441`) |
| `role` | TEXT | `user`, `assistant`, `tool` |
| `content` | TEXT | Nachrichten-Content (Markdown, JSON für Tool-Results) |
| `tool_call_id` | TEXT | ID des Tool-Calls (bei role=tool) |
| `tool_calls` | TEXT | JSON-Array der Tool-Calls (bei role=assistant) |
| `tool_name` | TEXT | Tool-Name (bei role=tool) |
| `effect_disposition` | TEXT | Wirkung des Tool-Ergebnisses |
| `timestamp` | REAL | Unix-Timestamp (kann NULL sein) |
| `token_count` | INTEGER | Token-Anzahl (oft NULL — nicht als Primary-Statistik nutzen) |
| `finish_reason` | TEXT | `stop`, `tool_calls`, `max_tokens`, `verification_required` etc. |
| `reasoning` | TEXT | Reasoning-Content des Modells |
| `active` | INTEGER | `1` = aktiv, `0` = komprimiert/archiviert |
| `compacted` | INTEGER | `1` = Session wurde komprimiert |

**Größe (Stand Sep 2026):** ~12.055 Sessions, ~241.845 Messages:
- 112k assistant, 115k tool, 14k user

**Wichtige Query-Patterns:**

```sql
-- Letzte 50 Sessions mit Stats
SELECT session_id,
       MIN(timestamp) as start_ts,
       MAX(timestamp) as end_ts,
       COUNT(*) as msg_count,
       SUM(CASE WHEN role='user' THEN 1 ELSE 0 END) as user_msg_count,
       SUM(CASE WHEN role='tool' THEN 1 ELSE 0 END) as tool_msg_count,
       SUM(token_count) as total_tokens
FROM messages
WHERE active = 1
GROUP BY session_id
ORDER BY MAX(timestamp) DESC
LIMIT 50;

-- Finish-Reason-Verteilung einer Session
SELECT finish_reason, COUNT(*)
FROM messages
WHERE session_id = ? AND active = 1
GROUP BY finish_reason;

-- Tool-Nutzung über alle Sessions
SELECT tool_name, COUNT(*) as cnt
FROM messages
WHERE role = 'tool' AND tool_name IS NOT NULL AND tool_name != ''
GROUP BY tool_name
ORDER BY cnt DESC
LIMIT 20;
```

### 2. sessions.db (LEER — 0 Bytes)

**Pfad:** `<OPENAMER_HOME>/sessions.db`

Enthält keine Tabellen. Wird aktuell nicht verwendet. Nicht als Datenquelle für Analyse nutzbar.

### 3. sessions/*.json (NUR Error-Dumps)

**Pfad:** `<OPENAMER_HOME>/sessions/request_dump_*.json`

Enthalten ausschließlich fehlgeschlagene API-Requests (`reason: max_retries_exhausted`).
Diese Dateien repräsentieren **keine vollständigen Sessions**, sondern nur API-Fehler.

Format:
```json
{
  "timestamp": "2026-09-13T22:31:40.500904",
  "session_id": "20260913_221717_cc57dd",
  "reason": "max_retries_exhausted",
  "request": {
    "body": {
      "model": "nvidia/nemotron-3.5-lightning:free",
      "messages": [{"role": "system", "content": "..."}, {"role": "user", "content": "..."}]
    }
  },
  "error": "..."
}
```

## Nützliche Metriken (für Reports & Training)

| Metrik | Quelle | Query |
|--------|--------|-------|
| Sessions insgesamt | `state.db:messages` | `COUNT(DISTINCT session_id)` |
| Messages pro Session | `state.db:messages` | `COUNT(*) GROUP BY session_id` |
| Top-Tools | `state.db:messages` | `WHERE role='tool' GROUP BY tool_name` |
| Finish-Reasons | `state.db:messages` | `WHERE finish_reason IS NOT NULL GROUP BY finish_reason` |
| Session-Dauer | `state.db:messages` | `MAX(timestamp) - MIN(timestamp) per session_id` |
| Error-Dichte | `state.db:messages` | Regex auf content nach Error-Patterns |
| Token-Verbrauch | `state.db:messages` | `SUM(token_count)` — Daten oft spärlich |

## Verwandte Scripts

- `<OPENAMER_HOME>/scripts/metacognition.py` — vollständige Pattern-Analyse über state.db (Topics, Tools, Finish-Reasons, Error-Dichte)
- `<OPENAMER_HOME>/scripts/training/session_to_brain.py` — Session-Export für Training (nutzt dieselbe state.db-Quelle)