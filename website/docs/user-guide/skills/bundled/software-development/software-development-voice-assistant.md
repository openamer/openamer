---
title: "Voice Assistant — Use for the Windows TTS+STT voice interface in OpenAmer"
sidebar_label: "Voice Assistant"
description: "Use for the Windows TTS+STT voice interface in OpenAmer"
---

{/* This page is auto-generated from the skill's SKILL.md by website/scripts/generate-skill-docs.py. Edit the source SKILL.md, not this page. */}

# Voice Assistant

Use for the Windows TTS+STT voice interface in OpenAmer.

## Skill metadata

| | |
|---|---|
| Source | Bundled (installed by default) |
| Path | `skills/software-development\voice-assistant` |

## Reference: full SKILL.md

:::info
The following is the complete skill definition that OpenAmer loads when this skill is triggered. This is what the agent sees as instructions when the skill is active.
:::

# voice-assistant – KI-Sprech-Assistent

## Beschreibung

Ein reines Python-Standardbibliothek Voice-Interface für OpenAmer auf Windows.
Nutzt **PowerShell System.Speech** für Text-to-Speech (TTS) und Speech-to-Text
(STT, Windows Diktat-API via DictationGrammar).

**Datei:** `scripts/voice-assistant.py` im OpenAmer-Home (`$OPENAMER_HOME/scripts/`)

## CLI-Modi

| Flag | Beschreibung |
|------|-------------|
| `--listen` | Nimmt Mikrofon auf (10s Standard-Timeout), gibt erkannten Text auf stdout aus. |
| `--speak 'Text'` | Gibt Text per PowerShell TTS aus (System.Speech). |
| `--chat` | Interaktiver Chat: sprich oder tippe, erhalte TTS-Antwort (Echo-Demo). |
| `--list-voices` | Listet installierte Windows-TTS-Stimmen. |
| `--log N` | Zeigt Konversations-Log der letzten N Tage. |
| `--voice 'Name'` | Wählt eine bestimmte TTS-Stimme (z. B. 'Microsoft Zira Desktop'). |

## Exit-Codes

- `0` – Erfolg
- `1` – Mikrofon/STT nicht verfügbar (kein Mikrofon, keine Sprache)
- `2` – TTS-Fehler

## Konversations-Log

Alle Sitzungen werden als **JSONL** in `~/.voice-assistant/conversations/` geloggt.
Dateinamen: `conversation_YYYYMMDD_HH.jsonl` (stündlich rotiert).

Einträge enthalten: `session_id`, `turn`, `role`, `text`, `timestamp`, `mode` (speech|text).

## Voraussetzungen

- Windows 10/11
- PowerShell (installiert)
- Mikrofon (für STT)
- Python 3.11+ (Standardbibliothek, keine externen Dependencies)

## Kurztest

```bash
cd "$OPENAMER_HOME/scripts"
python voice-assistant.py --list-voices
python voice-assistant.py --speak 'Hallo Welt'
python voice-assistant.py --listen --timeout 5
python voice-assistant.py --chat
```

## Fehlerbehebung

| Problem | Ursache | Lösung |
|---------|---------|--------|
| `SpeechRecognitionEngine` nicht verfügbar | Windows Speech Recognition deaktiviert | `Systemsteuerung > Spracherkennung` aktivieren |
| `Add-Type … System.Speech` schlägt fehl | .NET Framework 3.5 fehlt | `dism /online /Enable-Feature /FeatureName:NetFx3` |
| Keine TTS zu hören | Standard-Lautsprecher falsch | Windows Audio-Einstellungen prüfen |
| STT timeout | Kein Mikrofon oder keine Sprache | Mikrofon-Eingabe prüfen, `--timeout 15` versuchen |
| `--speak` mit Sonderzeichen | Escaping in PowerShell | Text in einfache Anführungszeichen setzen |

## Skills-Integration

Der Voice-Assistent kann aus anderen Skills/OA-Scripts importiert werden:

```python
import sys
sys.path.insert(0, r'$OPENAMER_HOME\scripts')
from voice_assistant import tts_powershell, stt_listen, log_conversation
```

## Architecture

<!-- ascii-guard-ignore -->
```
┌─────────────────────┐     subprocess      ┌───────────────────────────┐
│  voice-assistant.py  │ ──────────────────> │  PowerShell               │
│  (Python, stdlib)    │                     │  - System.Speech.Synthesis│
│                      │ <────────────────── │  - System.Speech.Recog.   │
│  CLI argparse        │     stdout/stderr   └───────────────────────────┘
│  Session-Log (JSONL) │
│  ~/.voice-assistant/ │
└─────────────────────┘
```
<!-- ascii-guard-ignore-end -->

## Verwandte Skills

`windows-compatibility`, `windows-computer-use`
