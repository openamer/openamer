---
description: Use when datei- und berechtigungsprobleme lösen. Automatisch generiert aus dem Continuous Learning Loop.
category: learning-loop
---

# Datei- und Berechtigungsprobleme lösen

Automatisch generierter Skill aus dem Learning Loop.

## Auslöser

Wiederkehrender Fehler (Kategorie: `permission`):

```
^^^^^^^^^^^^^^^^^^^^^^^^ File "C:\Users\damir\AppData\Local\openamer-laptop\openamer-agent\tools\computer_use\cua_backend.py", line 1773, in _call_capture_tool raise RuntimeError( RuntimeError: cua-driver get_window_state failed: Permission denied: Cua Driver refuses operations that target its...
```

## Lösung

Prüfe Dateiberechtigungen (chmod/icacls). Führe ggf. mit Admin-Rechten aus. Prüfe ob die Datei von einem anderen Prozess gesperrt ist.

## Prävention

- Regelmäßige Log-Analyse mit `learning-loop.py --auto`
- Bei erneuten Auftreten: Skill aktualisieren und Lösung verfeinern
- Monitoring auf diesen Fehlertyp einrichten
