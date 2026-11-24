---
description: Use when provider/api-key-probleme diagnostizieren und beheben. Automatisch generiert aus dem Continuous Learning Loop.
category: learning-loop
---

# Provider/API-Key-Probleme diagnostizieren und beheben

Automatisch generierter Skill aus dem Learning Loop.

## Auslöser

Wiederkehrender Fehler (Kategorie: `provider_error`):

```
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ File "C:\Users\damir\AppData\Local\openamer-laptop\openamer-agent\agent\auxiliary_client.py", line 8255, in async_call_llm raise RuntimeError( RuntimeError: No LLM provider configured for task=vision provider=auto. Run: openamer setup RuntimeError: No LLM...
```

## Lösung

API-Key prüfen und ggf. erneuern. Prüfe Kontostand/Abonnement. Bei Provider-unhealthy: warte 60s oder wechsle Provider.

## Prävention

- Regelmäßige Log-Analyse mit `learning-loop.py --auto`
- Bei erneuten Auftreten: Skill aktualisieren und Lösung verfeinern
- Monitoring auf diesen Fehlertyp einrichten
