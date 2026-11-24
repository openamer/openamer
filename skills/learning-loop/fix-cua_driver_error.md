---
description: Use when cua-driver-fehler diagnostizieren und neu starten. Automatisch generiert aus dem Continuous Learning Loop.
category: learning-loop
---

# cua-driver-Fehler diagnostizieren und neu starten

Automatisch generierter Skill aus dem Learning Loop.

## Auslöser

Wiederkehrender Fehler (Kategorie: `cua_driver_error`):

```
^^^^^^^^^^^^^^^^^^^^^^^^ File "C:\Users\damir\AppData\Local\openamer-laptop\openamer-agent\tools\computer_use\cua_backend.py", line 1685, in _call_capture_tool raise RuntimeError( RuntimeError: cua-driver list_windows failed: this session has ended; call start_session explicitly to reuse its...
```

## Lösung

Starte cua-driver neu: `openamer computer-use doctor` für Diagnose. Prüfe ob der Session-Status gültig ist.

## Prävention

- Regelmäßige Log-Analyse mit `learning-loop.py --auto`
- Bei erneuten Auftreten: Skill aktualisieren und Lösung verfeinern
- Monitoring auf diesen Fehlertyp einrichten
