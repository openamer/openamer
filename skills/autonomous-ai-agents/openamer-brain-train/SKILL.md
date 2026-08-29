---
name: openamer-brain-train
description: "Train an OpenAmer-specific small model from the collected brain data (QLoRA on NVIDIA, CPU smoke-test on laptop). 'The organism becomes its own brain' — build a fine-tune dataset, train, eval, export."
version: 1.0.0
author: OpenAmer + damir
license: Apache-2.0
platforms: [linux, macos, windows]
metadata:
  openamer:
    tags: [finetune, training, llm, dataset, brain, qlora, unsloth, openamer-model, self-train]
    homepage: https://github.com/openamer/openamer
    related_skills: [openamer-finetune-plan, huggingface-hub, llama-cpp, a2a-swarm]
---

# OpenAmer Brain Train — "train your own brain" (automatisiert)

Erzeugt aus der gesammelten Brain-Daten (`openamer-brain.jsonl`) ein eigenes,
OpenAmer-spezifisches **kleines Modell** — über den kompletten Kreislauf:
**Daten kuratieren → Dataset → Training → Evaluation → GGUF-Export → Deployment-Konfig.**

## Trigger

- Du hast genug Brain-Daten (typisch 500+ Sessions, die `openamer-brain.jsonl` wächst).
- Du willst ein kleines Modell, das perfekt für OpenAmer funktioniert (eigene Brain).
- Halbautomatisch; läuft ganz auf-NVIDIA-Rechner (3060Ti), CPU-Smoke-Test auf Laptop.

## Hardware-Erkennung (das Skript macht das selbst)

```
scripts/brain_train.py --detect
```
- **GPU vorhanden (NVIDIA)** → voller QLoRA-Trainingspfad (via unsloth/trl).
- **Kein NVIDIA (Laptop)** → CPU-Smoke-Test mit winzigem Modell, sonst Training vorbereiten
  und Ausführung auf den NVIDIA-PC verschieben.

## Ablauf

### 1. Prüfen & Daten vorbereiten
```bash
OPENAMER_HOME="C:/Users/damir/AppData/Local/openamer-laptop" \
  python scripts/brain_train.py --dataset
```
- Liest `<OPENAMER_HOME>/a2a/openamer-brain.jsonl`.
- Dedupe via `braindata.digest`, entfernt Secrets (ruft `privacy.redact`).
- Balance: sample umfasst max ~50 messages; priorisiert Tool-Calls + Thinking + Antwort.
- Ausgabe: `<OPENAMER_HOME>/training/train.jsonl` (ChatML `{"messages":[...]}`).

### 2. Trainieren
```bash
python scripts/brain_train.py --train            # volle QLoRA (NVIDIA, 3060Ti 8GB passt 7B)
python scripts/brain_train.py --train --smoke    # CPU-Smoke-Test (Laptop, winzig/langsam)
```
- NVIDIA-Pfad (unsloth/trl): base Modell = starkes Chat-Modell, LoRA rank 8–32, low epochs,
  split 95/5. Ausgabe-Checkpoint nach `<OPENAMER_HOME>/training/out/`.
- Laptop (--smoke): testet nur die Pipeline mit 2–8 Datensätzen, keine nützliche Ausgabe —
  beweist aber, dass die Daten/das Script funktionieren.

### 3. Evaluieren (ehrlich)
```bash
python scripts/brain_train.py --eval
```
- Testet: Tool-Call-Korrektheit (auf offenem Gate), Kurz-Antworten, Privacy-Refusal
  (GLEICHE keine private Nummer). Vergleich gegen Basis-Modell.
- Wenn nicht klar besser → **nicht deployen**, Basis behalten (gem. finetune-plan).

### 4. Export + Deploy
```bash
python scripts/brain_train.py --export        # GGUF via llama.cpp (falls GPU-Rechenzeit verfügbar)
python scripts/brain_train.py --deploy-check  # zeigt openamer model-Konfig für den neuen Checkpoint
```
- Modell-Name z.B. `openamer/brain-v1`. `openamer model` zeigt dann darauf.

### 5. Alle Schritte echt end-zu-end (NVIDIA-PC)
```bash
python scripts/brain_train.py --all
```

## Wichtige ehrliche Hinweise

- **Auf diesem Laptop (AMD iGPU, kein nvidia-smi, 21.8GB RAM):** QLoRA 7B ist NICHT
  praktikabel (unerndlich langsam auf CPU). Nutze hier `--smoke`/`--dataset` zum Verifizieren;
  die echte Training-Ausführung gehört auf den **3060Ti-PC** (wenn er an ist). Das Skript
  ist dafür bestimmt, dort per `openamer` ausgeführt zu werden.
- **Training braucht zusätzliche libs** (unsloth, trl, peft, datasets) — das Skript versucht,
  sie lazy zu installieren, wenn GPU erkannt wird (kann auf Laptop übersprungen werden).
- **Privacy:** reale Daten vor dem Trainieren roden — `privacy.redact` muss laufen.
  Ein geleakter private String vergiftet das Modell.
- **Kuration > Volumen:** 10k saubere, Tool-reiche Samples > 1M Dumps. Lieber kleiner Loop.

## Verify
```bash
OPENAMER_HOME="C:/Users/damir/AppData/Local/openamer-laptop" \
  python scripts/brain_train.py --dataset && \
  python scripts/brain_train.py --smoke
```
Beide müssen sauber aussteigen (Exit 0), bevor du auf dem 3060Ti `--all` startest.