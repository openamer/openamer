# Session 2026-09-13: Model Pinning Fix

## Problem
KOSTEN-LEAK: Cron job.model-Pin divergierte von config.yaml default model. OpenRouter `slug=null` → nicht in `/apps` gelistet → 403 Fehler für Free-Modelle.

## Fix Applied
```bash
openamer sync_cron_default.py --follow
```

## Result
- Alle 29 Agent-Jobs folgen jetzt `nvidia/nemotron-3.5-lightning:free`
- Wie in config.yaml default definiert
- Model-Diversität: 3 Fallback-Provider konfiguriert (TokenHarbor, lokal Ollama)
- Kein manueller Key in `.env` nötig für Basis-Funktionalität

## References
- config.yaml model.default: `nvidia/nemotron-3.5-lightning:free`
- Commit 15b82a0ed: fix(openrouter): send only recognised app categories
- OpenRouter Models: inkling:free (403), 550b (Timeout), gemma:free (429)