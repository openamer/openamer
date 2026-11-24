---
name: openamer-free-models-db
description: Complete catalog of every free LLM API provider and free model on the internet. 86+ verified free API providers, 450+ free models, plus 2.96M self-hosted open-weight models from Hugging Face. Use this to route OpenAmer to any free provider/model.
category: data
version: 1.0.0
author: OpenAmer
last_updated: 2026-11-08
triggers:
  - "free provider"
  - "free model"
  - "free LLM API"
  - "kostenloser Anbieter"
  - "kostenloses Modell"
  - "openamer free"
  - "beste free provider"
  - "alle free modelle"
  - "free llm directory"
  - "open source model self-host"
---

# OpenAmer Free Provider & Model Database

## Was diese Skill kann

Diese Skill listet **alle kostenlosen LLM-Provider und kostenlosen Modelle** im Internet, die OpenAmer nutzen kann:

- **86+ verifizierte Free-API-Provider** (permanent free tier, keyless, trial credits)
- **450+ kostenlose API-Modelle** mit konkreten Rate-Limits
- **2,96 Millionen Open-Weight-Modelle** auf Hugging Face zum Selbst-Hosten (kostenlos, eigene Hardware)

## Quellen (alle live verifiziert, 2026)

| Quelle | Provider | Modelle | Stand |
|---|---|---|---|
| free-llm.com / nejib1/Free-LLM | 86+ | 450+ | täglich synced |
| free-model.com | 20 | 147 | 2026 |
| jtig37/free-llm-api-resources | 13+ | 100+ | 2026 |
| OpenRouter Blog | 13 | 20+ | Sep 2026 |
| freellmpool | ~20 | - | Aug 2026 |
| Hugging Face Hub | - | 2,96M | Aug 2026 |

## Datenbank-Datei

`C:/Users/damir/AppData/Local/openamer-laptop/skills/openamer-free-models-db/openamer_free_models_db.json`

## Usage in OpenAmer

Die JSON-Datenbank kann direkt von OpenAmer gelesen werden, um:

1. Alle Free-Provider aufzulisten
2. Alle Free-Modelle pro Provider aufzulisten
3. Den besten Free-Provider für einen Use-Case zu empfehlen
4. Auf Selbst-Hosting mit lokalen Modellen (NPU/GPU) zu verweisen

## Top-Empfehlungen für OpenAmer

| Use-Case | Bester Free-Provider | Warum |
|---|---|---|
| Allgemein, viele Modelle | OpenRouter | 30 Free-Modelle, 1 Key, 70+ Provider im Backend |
| Geschwindigkeit | Groq | LPU, ~320 tok/s, 30 RPM / 1.000 RPD |
| Langes Kontext | Google AI Studio | bis 1M Token Kontext, 5-15 RPM |
| Kein Signup/Keyless | Pollinations, Kilo Code | Ohne API-Key, pro IP rate-limited |
| Unbegrenzt & privat | Selbst-Host (Hugging Face) | 2,96M Modelle, lokale NPU/GPU, keine API-Limits |

## Beispiel: OpenAmer auf OpenRouter Free leiten

```
base_url: https://openrouter.ai/api/v1
api_key: <dein OpenRouter Key>
model: openai/gpt-oss-120b:free
```

## Beispiel: Lokal selbst-hosten (kostenlos, unbegrenzt)

```
base_url: http://localhost:11434/v1  # Ollama lokal
model: qwen3-32b  # oder Llama 3.3 70B, DeepSeek-R1 etc.
```

## Wartung

Die Datenbank sollte regelmäßig aktualisiert werden, da Free-Tiers sich ständig ändern. Quellen: free-llm.com (täglich synced), OpenRouter Blog, free-model.com.
