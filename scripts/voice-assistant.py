#!/usr/bin/env python3
"""
KI-Sprech-Assistent — Voice-Interface für OpenAmer
====================================================
CLI-Modi:
  --listen           Nimmt Sprache auf (via Windows Speech Recognition) und gibt Text aus
  --speak 'text'     Gibt Text via PowerShell System.Speech TTS aus
  --chat             Interaktiver Modus: hört zu → verarbeitet → antwortet (Loop)
  --list-voices      Listet installierte TTS-Stimmen auf

Exit-Codes:
  0 = OK
  1 = Mikrofon / STT nicht verfügbar
  2 = TTS-Fehler

Abhängigkeiten: Nur Python-Standardbibliothek + Windows PowerShell (System.Speech)
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

# ── Konfiguration ──────────────────────────────────────────────────────────────

CONV_DIR = Path.home() / ".voice-assistant" / "conversations"
SCRIPT_DIR = Path(__file__).parent.resolve()
HOME_DIR = SCRIPT_DIR.parent  # openamer-laptop root
LOG_FILE = HOME_DIR / "logs" / "voice-assistant.log"

# Stelle sicher, dass Log-Verzeichnis existiert
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)


# ── Hilfsfunktionen ────────────────────────────────────────────────────────────

def log(msg: str, level: str = "INFO") -> None:
    """Schreibt eine Log-Zeile in die Log-Datei."""
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    line = f"[{ts}] {level}: {msg}"
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")
    if level in ("ERROR", "WARN"):
        print(line, file=sys.stderr)
    else:
        print(line)


def _powershell(script: str, timeout: int = 30) -> subprocess.CompletedProcess:
    """Führt ein PowerShell-Skript aus und gibt das CompletedProcess-Objekt zurück."""
    return subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
        capture_output=True,
        text=True,
        timeout=timeout,
    )


# ── Text-to-Speech (PowerShell System.Speech) ─────────────────────────────────

def tts_powershell(text: str, voice: str | None = None) -> int:
    """Gibt Text über die Windows-eigene Sprachsynthese aus.
    
    Args:
        text: Der auszugebende Text.
        voice: Optionaler Name der Stimme (z. B. 'Microsoft Hedda Desktop').
    
    Returns:
        0 bei Erfolg, 2 bei Fehler.
    """
    try:
        if voice:
            ps_script = (
                f'Add-Type -AssemblyName System.Speech; '
                f'$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; '
                f'$s.SelectVoice("{voice}"); '
                f'$s.Speak([System.Security.SecurityElement]::Escape(\'{text}\'))'
            )
        else:
            ps_script = (
                f'Add-Type -AssemblyName System.Speech; '
                f'$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; '
                f'$s.Speak([System.Security.SecurityElement]::Escape(\'{text}\'))'
            )
        result = _powershell(ps_script, timeout=120)
        if result.returncode != 0:
            log(f"TTS fehlgeschlagen: {result.stderr.strip()}", "ERROR")
            return 2
        log(f"TTS ausgegeben: {text[:80]}{'...' if len(text) > 80 else ''}")
        return 0
    except subprocess.TimeoutExpired:
        log("TTS-Zeitüberschreitung", "ERROR")
        return 2
    except Exception as e:
        log(f"TTS-Fehler: {e}", "ERROR")
        return 2


def tts_to_wav(text: str, out_path: str | Path, voice: str | None = None) -> int:
    """Rendert Text in eine WAV-Datei (offline-Smoketest, kein Lautsprecher nötig).

    Returns: 0 bei Erfolg, 2 bei Fehler.
    """
    try:
        out = str(out_path).replace("'", "''")
        select = f'$s.SelectVoice("{voice}"); ' if voice else ""
        ps_script = (
            'Add-Type -AssemblyName System.Speech; '
            '$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; '
            f'{select}'
            f'$s.SetOutputToWaveFile(\'{out}\'); '
            f'$s.Speak([System.Security.SecurityElement]::Escape(\'{text}\')); '
            '$s.Dispose()'
        )
        result = _powershell(ps_script, timeout=60)
        if result.returncode != 0:
            log(f"TTS-WAV fehlgeschlagen: {result.stderr.strip()}", "ERROR")
            return 2
        size = Path(out).stat().st_size if Path(out).exists() else 0
        if size <= 44:  # nur Header = keine Audio-Daten
            log(f"TTS-WAV leer/ungueltig ({size} Bytes)", "ERROR")
            return 2
        log(f"TTS-WAV erzeugt: {out} ({size} Bytes)")
        return 0
    except Exception as e:
        log(f"TTS-WAV-Fehler: {e}", "ERROR")
        return 2


def selftest(voice: str | None = None) -> int:
    """End-to-End-Smoketest: Text in -> WAV-Datei out -> Lautsprecherausgabe."""
    print("== Voice-Assistant Selftest ==")
    ok = True

    # 1) Stimmen
    voices = list_tts_voices()
    print(f"[1] TTS-Stimmen: {len(voices)} gefunden")
    if not voices:
        print("    FAIL: keine Stimmen installiert")
        ok = False

    # 2) Offline-TTS: WAV erzeugen
    wav = Path(tempfile.gettempdir()) / "voice-assistant-selftest.wav"
    wav.unlink(missing_ok=True)
    rc = tts_to_wav("Selbsttest: hallo, das ist ein Sprachtest.", wav, voice=voice)
    if rc == 0:
        print(f"[2] TTS->WAV: OK ({wav.stat().st_size} Bytes: {wav})")
    else:
        print("    FAIL: WAV-Erzeugung fehlgeschlagen")
        ok = False

    # 3) Live-TTS über Lautsprecher
    rc = tts_powershell("Selbsttest abgeschlossen.", voice=voice)
    if rc == 0:
        print("[3] TTS (Lautsprecher): OK")
    else:
        print("    FAIL: Lautsprecher-TTS fehlgeschlagen")
        ok = False

    # 4) STT-Verfügbarkeit (kurzer Probe-Lauf, kein Mikrofon erforderlich um zu 'passen',
    #    aber ERROR-Codes (z. B. kein Audiogerät) schlagen fehl)
    text, code = stt_listen(timeout=2)
    if code == 0:
        print(f"[4] STT: verfügbar (erkannt: {text!r})" if text else "[4] STT: verfügbar (keine Sprache)")
    else:
        print("    FAIL: STT nicht verfügbar (Exit 1)")
        ok = False

    print("== ERGEBNIS:", "PASS" if ok else "FAIL", "==")
    return 0 if ok else 1


def list_tts_voices() -> list[dict]:
    """Listet alle installierten TTS-Stimmen auf."""
    ps_script = (
        'Add-Type -AssemblyName System.Speech; '
        '$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; '
        '$voices = $s.GetInstalledVoices(); '
        'foreach ($v in $voices) { '
        '  $info = $v.VoiceInfo; '
        '  Write-Output "$($info.Name)|$($info.Culture)|$($info.Gender)|$($info.Age)" '
        '}'
    )
    result = _powershell(ps_script)
    voices = []
    for line in result.stdout.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        parts = line.split("|")
        if len(parts) >= 1:
            voices.append({
                "name": parts[0],
                "culture": parts[1] if len(parts) > 1 else "",
                "gender": parts[2] if len(parts) > 2 else "",
                "age": parts[3] if len(parts) > 3 else "",
            })
    return voices


# ── Speech-to-Text (Windows Speech Recognition / Dictation) ───────────────────

def stt_listen(timeout: int = 10) -> tuple[str | None, int]:
    """Nimmt Sprache über das Mikrofon auf und erkennt den Text.
    
    Nutzt Windows Speech Recognition (System.Speech.Recognition) mit
    DictationGrammar. Das Skript startet einen asynchronen Recognizer,
    wartet auf das nächste Ergebnis und gibt den erkannten Text zurück.
    
    Args:
        timeout: Maximale Wartezeit in Sekunden (Standard: 10).
    
    Returns:
        (text, exit_code): text ist None bei Fehler, sonst der erkannte String.
        exit_code: 0=Erfolg, 1=Mikrofon/STT nicht verfügbar.
    """
    # PowerShell-Skript für Speech Recognition mit DictationGrammar
    # Nutzt Events und einen Timeout-Mechanismus
    ps_script = f'''
Add-Type -AssemblyName System.Speech

$recognized = $null
$done = New-Object System.Threading.AutoResetEvent($false)

$recognizer = New-Object System.Speech.Recognition.SpeechRecognitionEngine
$grammar = New-Object System.Speech.Recognition.DictationGrammar
$recognizer.LoadGrammar($grammar)

# Event-Handler für Erkennung
Register-ObjectEvent -InputObject $recognizer -EventName SpeechRecognized -Action {{
    $global:recognized = $eventArgs.Result.Text
    $done.Set()
}} > $null

# Event-Handler für Fehler
Register-ObjectEvent -InputObject $recognizer -EventName SpeechRecognitionRejected -Action {{
    $done.Set()
}} > $null

try {{
    $recognizer.SetInputToDefaultAudioDevice()
    $recognizer.RecognizeAsync([System.Speech.Recognition.RecognizeMode]::Multiple)

    if ($done.WaitOne({timeout * 1000})) {{
        if ($global:recognized) {{
            Write-Output "RECOGNIZED:$($global:recognized)"
        }} else {{
            Write-Output "NO_SPEECH"
        }}
    }} else {{
        Write-Output "TIMEOUT"
    }}
}} catch {{
    Write-Output "ERROR:$($_.Exception.Message)"
}} finally {{
    $recognizer.RecognizeAsyncCancel()
    $recognizer.Dispose()
    Get-EventSubscriber | Unregister-Event > $null 2>$null
}}
'''
    try:
        result = _powershell(ps_script, timeout=timeout + 10)
        output = result.stdout.strip()

        if output.startswith("RECOGNIZED:"):
            text = output[len("RECOGNIZED:"):]
            log(f"STT erkannt: {text[:80]}{'...' if len(text) > 80 else ''}")
            return text, 0
        elif output == "NO_SPEECH":
            log("STT: Keine Sprache erkannt")
            return None, 0
        elif output == "TIMEOUT":
            log("STT: Zeitüberschreitung (keine Eingabe)")
            return None, 0
        elif output.startswith("ERROR:"):
            err_msg = output[len("ERROR:"):]
            log(f"STT-Fehler: {err_msg}", "ERROR")
            return None, 1
        else:
            log(f"STT unerwartete Ausgabe: {output[:100]}", "WARN")
            return None, 1
    except subprocess.TimeoutExpired:
        log("STT-Zeitüberschreitung (Prozess)", "ERROR")
        return None, 1
    except Exception as e:
        log(f"STT-Ausnahme: {e}", "ERROR")
        return None, 1


# ── Konversations-Log ─────────────────────────────────────────────────────────

def _ensure_conv_dir():
    """Erstellt das Konversations-Verzeichnis, falls nicht vorhanden."""
    CONV_DIR.mkdir(parents=True, exist_ok=True)


def _conv_file() -> Path:
    """Gibt den Pfad zur aktuellen Konversationsdatei zurück (stündlich rotiert)."""
    now = datetime.now(timezone.utc)
    filename = f"conversation_{now.strftime('%Y%m%d_%H')}.jsonl"
    return CONV_DIR / filename


def log_conversation(entry: dict) -> None:
    """Hängt einen Eintrag an die Konversations-Logdatei an (JSONL-Format).
    
    Args:
        entry: Dict mit mindestens 'role' und 'text'. Optional: 'timestamp'.
    """
    _ensure_conv_dir()
    if "timestamp" not in entry:
        entry["timestamp"] = datetime.now(timezone.utc).isoformat()
    filepath = _conv_file()
    with open(filepath, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def list_conversations(days: int = 7) -> list[Path]:
    """Listet Konversationsdateien der letzten N Tage auf."""
    _ensure_conv_dir()
    cutoff = datetime.now(timezone.utc).timestamp() - (days * 86400)
    files = sorted(CONV_DIR.glob("conversation_*.jsonl"), reverse=True)
    return [f for f in files if f.stat().st_mtime >= cutoff]


# ── Chat-Modus (interaktiv) ────────────────────────────────────────────────────

def run_chat(voice: str | None = None) -> int:
    """Interaktiver Chat-Modus: Hört zu → zeigt Text → gibt Antwort aus.
    
    Der Benutzer kann sprechen oder 'exit' / 'quit' / 'bye' eingeben, um
    zu beenden. Bei Eingabe von 'help' werden die Befehle angezeigt.
    
    Im Chat-Modus antwortet das System mit einer TTS-Ausgabe der
    zurückgespiegelten Benutzereingabe (Echo-Modus als Demo).
    """
    print("=" * 60)
    print("  KI-Sprech-Assistent — Chat-Modus")
    print("=" * 60)
    print("  Sprich in das Mikrofon oder tippe eine Nachricht.")
    print("  Befehle: 'exit' (beenden), 'help' (Hilfe), 'voices' (Stimmen)")
    print("-" * 60)

    session_start = datetime.now(timezone.utc)
    session_id = session_start.strftime("%Y%m%d_%H%M%S")

    log_conversation({
        "session_id": session_id,
        "event": "session_start",
        "timestamp": session_start.isoformat(),
    })

    exit_code = 0
    turn = 0

    while True:
        turn += 1
        print(f"\n[{turn}] Höre zu... (sprich oder tippe, max 10s Pause)")

        # Versuche STT, fallback zu Texteingabe
        text, stt_code = stt_listen(timeout=10)

        if text is None:
            # STT hat nichts erkannt → Texteingabe als Fallback
            print("  (Mikrofon: keine Eingabe — tippe deine Nachricht)")
            try:
                text = input("  Du: ").strip()
            except (EOFError, KeyboardInterrupt):
                text = "exit"

        if not text:
            continue

        user_text = text.strip()
        print(f"  Du: {user_text}")

        log_conversation({
            "session_id": session_id,
            "turn": turn,
            "role": "user",
            "mode": "speech" if stt_code == 0 else "text",
            "text": user_text,
        })

        # Befehle
        lower = user_text.lower()
        if lower in ("exit", "quit", "bye", "beenden", "tschüss"):
            print("  Assistent: Auf Wiedersehen!")
            tts_powershell("Auf Wiedersehen!", voice=voice)
            log_conversation({
                "session_id": session_id,
                "turn": turn,
                "role": "assistant",
                "text": "Auf Wiedersehen!",
            })
            break
        elif lower in ("help", "hilfe"):
            print("  Befehle: exit, help, voices")
            print("  Sag etwas oder tippe — ich wiederhole es per Sprachausgabe.")
            continue
        elif lower in ("voices", "stimmen"):
            voices = list_tts_voices()
            print(f"  Installierte Stimmen ({len(voices)}):")
            for v in voices:
                print(f"    - {v['name']} ({v['culture']}, {v['gender']})")
            continue

        # Echo-Antwort (Demo-Modus): wiederhole, was der Benutzer gesagt hat
        answer = user_text
        print(f"  Assistent: {answer}")

        tts_result = tts_powershell(answer, voice=voice)
        if tts_result != 0 and exit_code == 0:
            exit_code = 2

        log_conversation({
            "session_id": session_id,
            "turn": turn,
            "role": "assistant",
            "text": answer,
        })

    log_conversation({
        "session_id": session_id,
        "event": "session_end",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "turns": turn,
    })

    print(f"\n  Sitzung beendet. {turn} Runden geloggt in {CONV_DIR}")
    return exit_code


# ── CLI-Main ────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(
        description="KI-Sprech-Assistent — Voice-Interface für OpenAmer",
        epilog="Beispiele:\n  voice-assistant --speak 'Hallo Welt'\n  voice-assistant --listen\n  voice-assistant --chat",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--listen", action="store_true",
        help="Nimmt Mikrofon auf und gibt erkannten Text aus"
    )
    mode.add_argument(
        "--speak", type=str, metavar="TEXT",
        help="Gibt Text via TTS aus"
    )
    mode.add_argument(
        "--chat", action="store_true",
        help="Interaktiver Modus: hört zu → verarbeitet → antwortet"
    )
    mode.add_argument(
        "--selftest", action="store_true",
        help="Smoketest: Stimmen, TTS->WAV-Datei, Lautsprecher-TTS und STT prüfen"
    )
    mode.add_argument(
        "--list-voices", action="store_true",
        help="Listet installierte TTS-Stimmen auf"
    )

    parser.add_argument(
        "--voice", type=str, default=None,
        help="TTS-Stimme auswählen (z. B. 'Microsoft Hedda Desktop')"
    )
    parser.add_argument(
        "--timeout", type=int, default=10,
        help="Maximale Wartezeit für STT in Sekunden (Standard: 10)"
    )
    parser.add_argument(
        "--log", type=str, default=None,
        help="Zeige Konversations-Log der letzten N Tage (z. B. '7')"
    )

    args = parser.parse_args()

    # Log-Level setzen
    log("Voice-Assistant gestartet", "INFO")

    # ── Konversations-Log anzeigen ──
    if args.log:
        days = int(args.log)
        files = list_conversations(days=days)
        if not files:
            print(f"Keine Konversationen in den letzten {days} Tagen gefunden.")
            return 0
        print(f"Letzte {len(files)} Konversationsdatei(en):\n")
        for fpath in files:
            print(f"  {fpath.name} ({datetime.fromtimestamp(fpath.stat().st_mtime).strftime('%Y-%m-%d %H:%M')})")
            with open(fpath, encoding="utf-8") as f:
                lines = f.readlines()
            print(f"    → {len(lines)} Einträge")
            # Zeige die letzten 3 Einträge
            for line in lines[-3:]:
                data = json.loads(line)
                role = data.get("role", data.get("event", "?"))
                txt = data.get("text", "")[:100]
                print(f"      [{role}] {txt}")
            print()
        return 0

    # ── --selftest ──
    if args.selftest:
        return selftest(voice=args.voice)

    # ── --list-voices ──
    if args.list_voices:
        voices = list_tts_voices()
        if not voices:
            print("Keine TTS-Stimmen gefunden.")
            return 1
        print(f"Installierte TTS-Stimmen ({len(voices)}):")
        for v in voices:
            print(f"  - {v['name']} ({v['culture']}, {v['gender']}, {v['age']})")
        return 0

    # ── --listen ──
    if args.listen:
        text, code = stt_listen(timeout=args.timeout)
        if text:
            print(text)
            return 0
        else:
            print("Keine Sprache erkannt.", file=sys.stderr)
            return code if code else 1

    # ── --speak ──
    if args.speak:
        code = tts_powershell(args.speak, voice=args.voice)
        return code

    # ── --chat ──
    if args.chat:
        return run_chat(voice=args.voice)

    # Kein Modus → Hilfe anzeigen
    parser.print_help()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nAbgebrochen.")
        sys.exit(0)
    except Exception as e:
        print(f"Fehler: {e}", file=sys.stderr)
        sys.exit(1)