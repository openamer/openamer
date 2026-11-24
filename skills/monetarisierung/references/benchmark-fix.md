# Benchmark Fix — API Key Bug

## Symptom
`_cron_benchmark.py` → `benchmark.py --cron` → `{"status": "done", "accuracy": 0.0}`

## Root Cause
1. **Modell:** benchmark.py nutzte hartcodiert `nex-agi/nex-n2.5-mini:free` — ein Free-Modell, zu schwach für korrekte Antworten.
2. **API-Key:** Der Key wurde aus der env var `OPENROUTER_API_KEY` gelesen, aber diese env var wird bei Subprocess-Aufrufen nicht weitergereicht. Der Key steht nur in der `.env` Datei, nicht in der Umgebung.

## Fix
**Model:** `nex-agi/nex-n2.5-mini:free` → `deepseek/deepseek-v4-flash` (€0.15/M tokens, Budget-freundlich)

**API-Key Reader:** Statt `os.environ.get("OPENROUTER_API_KEY")`:
```python
env_path = HOME / ".env"
api_key = os.environ.get("OPENROUTER_API_KEY", "")
if not api_key and env_path.exists():
    for line in env_path.read_text().splitlines():
        if line.startswith("OPENROUTER_API_KEY="):
            api_key = line.split("=", 1)[1].strip().strip("\"'")
            break
```

## Result
Quick-Benchmark: Knowledge 65.2%, Reasoning 80%  
Kosten: ~€0.01 pro Benchmark-Lauf (deepseek-v4-flash, ~140 Fragen)

## Datei
`scripts/benchmark.py` (Zeile 172+, `score_answer_gpt` Funktion)