---
description: Use when diagnose und behebung von verbindungsfehlern. Automatisch generiert aus dem Continuous Learning Loop.
category: learning-loop
---

# Diagnose und Behebung von Verbindungsfehlern

Automatisch generierter Skill aus dem Learning Loop.

## Auslöser

Wiederkehrender Fehler (Kategorie: `connection_failed`):

```
self.gen.throw(typ, value, traceback) File "C:\Users\damir\AppData\Local\openamer-laptop\openamer-agent\venv\Lib\site-packages\httpcore\_exceptions.py", line 14, in map_exceptions raise to_exc(exc) from exc httpcore.ConnectError: [Errno 11001] getaddrinfo failed httpcore.ConnectError: [Errno...
```

## Lösung

Prüfe Internetverbindung, Firewall und ob der Dienst läuft. Bei API-Endpunkten: URL und Port prüfen.

## Prävention

- Regelmäßige Log-Analyse mit `learning-loop.py --auto`
- Bei erneuten Auftreten: Skill aktualisieren und Lösung verfeinern
- Monitoring auf diesen Fehlertyp einrichten
