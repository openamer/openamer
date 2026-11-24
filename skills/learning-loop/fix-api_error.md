---
description: Use when api-endpunkt-fehler behandeln (http 4xx/5xx). Automatisch generiert aus dem Continuous Learning Loop.
category: learning-loop
---

# API-Endpunkt-Fehler behandeln (HTTP 4xx/5xx)

Automatisch generierter Skill aus dem Learning Loop.

## Auslöser

Wiederkehrender Fehler (Kategorie: `api_error`):

```
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ File "C:\Users\damir\AppData\Local\openamer-laptop\openamer-agent\venv\Lib\site-packages\openai\_base_client.py", line 1669, in request raise self._make_status_error_from_response(err.response) from None openai.NotFoundError:...
```

## Lösung

Prüfe ob der API-Endpunkt erreichbar ist. Bei 404: URL prüfen. Bei 5xx: Server-Status prüfen, ggf. später wiederholen.

## Prävention

- Regelmäßige Log-Analyse mit `learning-loop.py --auto`
- Bei erneuten Auftreten: Skill aktualisieren und Lösung verfeinern
- Monitoring auf diesen Fehlertyp einrichten
