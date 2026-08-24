# 🧠 Backup-Gehirne — Notfall-Kette wenn OpenRouter komplett kollabiert

> Stand: 24.08.2026, live geprüft

## Die komplette Hungernotkette (in dieser Reihenfolge)

```
1. stealth/ox-alpha            ← Standard (gratis, aber 429-anfällig)
2. nvidia/nemotron-3.5-lightning:free   ← Reserve-Stufe 1  ✓ live getestet
3. dots-studio/dots-3-note-preview:free ← Reserve-Stufe 2  ✓ live getestet
4. poolside/laguna-xs-2.1:free          ← Reserve-Stufe 3  ✓ live getestet
5. liquid/lfm-2.5-2.6b:free             ← Reserve-Stufe 4  ✓ live getestet
6. HuggingFace Inference API           ← letzte Ebene (Key nötig)
7. Ollama lokal                        ← Endstufe (kein Internet nötig!)
```

Stufen 1–5 sind **aktiv** (`scripts/hunger_reserve.py`, gleicher OpenRouter-Key,
nur anderes Modell). Stufe 6 braucht einmalig einen HF-Key, Stufe 7 braucht
einmalig eine Installation.

## Stufe 6 aktivieren: HuggingFace (deine Hand, 3 Min)

1. https://huggingface.co/settings/tokens → "Create new token" (Read)
2. In `.env` ergänzen:
   ```
   HF_TOKEN=hf_dein_token_hier
   ```
3. Sag mir Bescheid → ich baue den HF-Fallback in hunger_reserve.py ein.

**Kostenlose Modelle via HF Inference API (Stand heute):**
- `deepseek-ai/DeepSeek-R1` (13.6k♥)
- `meta-llama/Llama-3.1-8B-Instruct` (6.6k♥)
- Free-Tier: Rate-Limited, aber für Cron-Nachtjobs völlig ausreichend

## Stufe 7: Ollama (die Festplatte als letztes Gehirn)

```powershell
winget install Ollama.Ollama
ollama pull llama3.1:8b        # ~4.7 GB, läuft danach offline
```

In `.env` ist `OLLAMA_BASE_URL` + `OLLAMA_API_KEY` bereits vorbereitet.
Danach funktioniert OpenAmer **komplett ohne Internet** — der Organismus
atmet dann seine eigene Luft.

## Testen der Kette

```bash
python scripts/hunger_reserve.py check   # welche Stufen leben?
python scripts/hunger_reserve.py best    # beste verfügbare Ausweich-Modell
```
