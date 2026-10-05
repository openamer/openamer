---
title: "Model Benchmarker — Use when: benchmark model latency, throughput, or quality"
sidebar_label: "Model Benchmarker"
description: "Use when: benchmark model latency, throughput, or quality"
---

{/* This page is auto-generated from the skill's SKILL.md by website/scripts/generate-skill-docs.py. Edit the source SKILL.md, not this page. */}

# Model Benchmarker

Use when: benchmark model latency, throughput, or quality.

## Skill metadata

| | |
|---|---|
| Source | Bundled (installed by default) |
| Path | `skills/system\model-benchmarker` |

## Reference: full SKILL.md

:::info
The following is the complete skill definition that OpenAmer loads when this skill is triggered. This is what the agent sees as instructions when the skill is active.
:::

# Model Benchmarker

Tests Model-Performance über mehrere Provider (OpenRouter, lokale Ollama-Instanzen).

## Tests

| Test | Beschreibung | Runs | Metrik |
|------|-------------|------|--------|
| **Latenz** | Zeit bis erster Token (kleiner Prompt) | 10 | Median in Sekunden |
| **Durchsatz** | Tokens pro Sekunde (4K Prompt) | 5 | Median tok/s |
| **Qualität** | Antwort auf 4 Testfragen bewertet | 1 | Score 0-100% |

## CLI-Verwendung

```bash
# Einmaliger Test
python model-benchmarker.py --run openrouter/deepseek-v4-flash
python model-benchmarker.py --run "local/qwen3.5:9b"

# Alle Provider testen (Default-Modell pro Provider)
python model-benchmarker.py --all

# Vergleichstabelle aller getesteten Modelle
python model-benchmarker.py --compare
python model-benchmarker.py --compare --json   # JSON-Ausgabe

# Trend-Historie
python model-benchmarker.py --history openrouter
python model-benchmarker.py --history local
```

## Provider-Konfiguration

Liest automatisch aus `config.yaml`:
- `model.default` → OpenRouter-Modell
- `custom_providers` → Lokale Ollama-Instanzen und deren Modelle
- API-Keys aus `.env` (`OPENROUTER_API_KEY`)

## Ergebnisverzeichnis

Alle Ergebnisse in `~/.model-benchmarks/results/<provider>-<model>.json`
mit vollständiger Historie (max 50 Einträge).

## Cron-Job

Wöchentlicher `--all` Run ist als Cron-Job eingerichtet:
- Führt alle Provider-Modelle durch
- Sendet Ergebnisse an Terminal (lokal)
- Kein Agent nötig (`no_agent: true`)

## Abhängigkeiten

Keine — nur Python-Standardbibliothek (urllib, json, statistics, etc.)
