---
description: Use when behebung von unknown-fehlern. Automatisch generiert aus dem Continuous Learning Loop.
category: learning-loop
---

# Behebung von unknown-Fehlern

Automatisch generierter Skill aus dem Learning Loop.

## Auslöser

Wiederkehrender Fehler (Kategorie: `unknown`):

```
self.set_meta( File "C:\Users\damir\AppData\Local\openamer-laptop\openamer-agent\openamer_state.py", line 9854, in set_meta cursor.execute( sqlite3.OperationalError: database is locked sqlite3.OperationalError: database is locked
```

## Lösung

Manuelle Analyse erforderlich.

## Prävention

- Regelmäßige Log-Analyse mit `learning-loop.py --auto`
- Bei erneuten Auftreten: Skill aktualisieren und Lösung verfeinern
- Monitoring auf diesen Fehlertyp einrichten
