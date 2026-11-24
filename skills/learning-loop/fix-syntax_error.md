---
description: Use when json/yaml/regex-syntax-fehler validieren und reparieren. Automatisch generiert aus dem Continuous Learning Loop.
category: learning-loop
---

# JSON/YAML/Regex-Syntax-Fehler validieren und reparieren

Automatisch generierter Skill aus dem Learning Loop.

## Auslöser

Wiederkehrender Fehler (Kategorie: `syntax_error`):

```
2026-08-21 04:29:49,016 WARNING [cron_9487843b3633_20260821_042927] agent.tool_executor: Tool search_files returned error (1.06s): {"total_count": 0, "error": "Search failed: rg: regex parse error:\n (?:*test*log*)\n ^\nerror: repetition operator missing expression"}
```

## Lösung

Prüfe JSON/YAML auf Syntax-Fehler. Nutze `python -m json.tool` oder einen Validator. Bei Regex: Sonderzeichen escapen.

## Prävention

- Regelmäßige Log-Analyse mit `learning-loop.py --auto`
- Bei erneuten Auftreten: Skill aktualisieren und Lösung verfeinern
- Monitoring auf diesen Fehlertyp einrichten
