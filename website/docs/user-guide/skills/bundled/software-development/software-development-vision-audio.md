---
title: "Vision Audio — vision-audio: screenshot, describe, transcribe, diagram"
sidebar_label: "Vision Audio"
description: "vision-audio: screenshot, describe, transcribe, diagram"
---

{/* This page is auto-generated from the skill's SKILL.md by website/scripts/generate-skill-docs.py. Edit the source SKILL.md, not this page. */}

# Vision Audio

vision-audio: screenshot, describe, transcribe, diagram.

## Skill metadata

| | |
|---|---|
| Source | Bundled (installed by default) |
| Path | `skills/software-development\vision-audio` |

## Reference: full SKILL.md

:::info
The following is the complete skill definition that OpenAmer loads when this skill is triggered. This is what the agent sees as instructions when the skill is active.
:::

# Vision + Audio Pipeline — Multimodal Understanding

## Beschreibung

`scripts/vision-audio.py` ist ein CLI-Tool für:
- **Screenshot** aufnehmen und analysieren (`--screenshot`)
- **Bildbeschreibung** via Pixelanalyse/Pillow (`--describe`)
- **Code-Diagramm**-Screenshots lesen (Kontrast-basiert) (`--diagram`)
- **Audio-Transkription** via OpenAI Whisper (`--transcribe`)
- **Mikrofon-Aufnahme** + Transkription (`--record`)

Alle Ausgaben erfolgen als strukturiertes JSON.

## Abhängigkeiten

```
pip install mss PyAudio openai-whisper Pillow
```

## CLI Usage

```
usage: vision-audio.py [-h] [--screenshot] [--describe BILD]
                       [--diagram DIAGRAMM] [--transcribe AUDIO] [--record]
                       [--seconds SECONDS] [--json]

Vision + Audio Pipeline — Multimodal Understanding

options:
  -h, --help           show this help message and exit
  --screenshot         Screenshot aufnehmen + beschreiben
  --describe BILD      Bilddatei beschreiben (Pixel-Analyse)
  --diagram DIAGRAMM   Code-Diagramm-Screenshot analysieren
  --transcribe AUDIO   Audiodatei transkribieren
  --record             Mikrofon aufnehmen + transkribieren
  --seconds SECONDS    Aufnahmedauer in Sekunden (Default: 10)
  --json               Nur JSON ausgeben (keine Stderr-Info)
```

## Beispiele

```bash
# Screenshot + beschreiben
python scripts/vision-audio.py --screenshot

# Bild beschreiben
python scripts/vision-audio.py --describe screenshot.png

# Code-Diagramm analysieren
python scripts/vision-audio.py --diagram code-flow.png

# Audio transkribieren
python scripts/vision-audio.py --transcribe meeting.wav

# Mikrofon aufnehmen + transkribieren
python scripts/vision-audio.py --record
python scripts/vision-audio.py --record --seconds 30
```

## Architektur

<!-- ascii-guard-ignore -->
```
vision-audio.py
├── Vision
│   ├── vision_screenshot()   → MSS / PowerShell-Fallback
│   ├── vision_describe()     → Pillow Pixelanalyse + Farbextraktion
│   └── vision_diagram()      → Kontrast-basierte Text-Bereichs-Detektion
├── Audio
│   ├── audio_transcribe()    → openai-whisper (Model: base)
│   └── audio_record()        → PyAudio → WAV → whisper
└── CLI (argparse)
```
<!-- ascii-guard-ignore-end -->

## Output Format (JSON)

```json
{
  "action": "describe|screenshot|transcribe|diagram|record",
  "status": "ok|error",
  "timestamp": "2026-08-22T00:40:21.551751",
  "text": "Bild-Deskription / Transkription / Diagramm …",
  "file_path": "path/to/file.png",
  "metadata": {
    "width": 1920,
    "height": 1200,
    "format": "PNG",
    "mode": "RGB",
    "avg_brightness": 0.635,
    "contrast": 0.883,
    "total_pixels": 26666,
    "dominant_colors": [["rgb(240,240,245)", 820], ...],
    "thumbnail_base64": "iVBOR..."
  }
}
```

## Tips & Pitfalls

1. **Whisper-Modell**: Beim ersten `--transcribe` lädt Whisper das `base`-Modell herunter (~150 MB).
2. **Mikrofon**: PyAudio benötigt ein funktionierendes Mikrofon. Fallback via PowerShell, falls PyAudio fehlt.
3. **Screenshot**: mss (MSS) ist Standard; bei Fehler Fallback auf PowerShell PrintScreen.
4. **Code-Diagramm**: Die Diagramm-Analyse ist heuristisch (Kontrast-Erkennung) – für echten OCR empfehle ich Tesseract.
5. **Bildbeschreibung**: Sampling über Grid (40×40 Punkte) – gute Balance zwischen Performance und Genauigkeit.
6. **Ausgabeverzeichnis**: Screenshots und Aufnahmen liegen unter `~/.openamer/vision-audio/`.
