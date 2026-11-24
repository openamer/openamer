---
description: Use when tool-ausführungsfehler beheben und parameter prüfen. Automatisch generiert aus dem Continuous Learning Loop.
category: learning-loop
---

# Tool-Ausführungsfehler beheben und Parameter prüfen

Automatisch generierter Skill aus dem Learning Loop.

## Auslöser

Wiederkehrender Fehler (Kategorie: `tool_error`):

```
2026-08-19 23:17:55,640 WARNING [20260819_222451_1e3f70] agent.tool_executor: Tool execute_code returned error (0.00s): {"status": "error", "error": "BLOCKED: execute_code runs arbitrary local Python (including subprocess calls that bypass shell-string approval checks). Cron jobs run without a...
```

## Lösung

Prüfe die Tool-Parameter. Bei execute_code-Blockade: Cron-Job hat keine execute_code-Rechte — nutze terminal() stattdessen.

## Prävention

- Regelmäßige Log-Analyse mit `learning-loop.py --auto`
- Bei erneuten Auftreten: Skill aktualisieren und Lösung verfeinern
- Monitoring auf diesen Fehlertyp einrichten
