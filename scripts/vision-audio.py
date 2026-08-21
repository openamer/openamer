#!/usr/bin/env python3
"""
Vision + Audio Pipeline — Multimodal Understanding
===================================================
CLI-Werkzeug für Screenshot-Analyse, Bildbeschreibung,
Code-Diagramm-Lesen, Audio-Transkription und Mikrofon-Aufnahme.

Usage:
  python vision-audio.py --screenshot          Screenshot + beschreiben
  python vision-audio.py --describe image.png  Bild beschreiben
  python vision-audio.py --diagram diagram.png Code-Diagramm analysieren
  python vision-audio.py --transcribe audio.wav Audio transkribieren
  python vision-audio.py --record              Mikrofon aufnehmen + transkribieren
  python vision-audio.py --help                Diese Hilfe
"""

import argparse
import base64
import json
import os
import subprocess
import sys
import tempfile
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Optional

# ─── Konfiguration ───────────────────────────────────────────────────────────

OUTPUT_DIR = Path.home() / ".openamer" / "vision-audio"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
SAMPLE_RATE = 16000       # für Whisper
RECORD_SECONDS = 10       # Standard-Aufnahmedauer
WHISPER_MODEL = "base"    # tiny/base/small/medium/large


# ─── Helper: JSON-Output ────────────────────────────────────────────────────

def make_result(action: str, status: str, text: str = "",
                file_path: str = "", metadata: dict = None) -> dict:
    return {
        "action": action,
        "status": status,
        "timestamp": datetime.now().isoformat(),
        "text": text,
        "file_path": file_path,
        "metadata": metadata or {},
    }


def print_json(result: dict):
    print(json.dumps(result, ensure_ascii=False, indent=2))


# ═══════════════════════════════════════════════════════════════════════════════
# VISION
# ═══════════════════════════════════════════════════════════════════════════════

def vision_screenshot() -> dict:
    """Nimmt einen Screenshot via mss auf und beschreibt ihn."""
    try:
        import mss
    except ImportError:
        return make_result("screenshot", "error",
                           text="mss nicht installiert (pip install mss)")

    temp_path = OUTPUT_DIR / f"screenshot_{int(time.time())}.png"
    try:
        with mss.MSS() as sct:
            monitor = sct.monitors[1]  # primärer Monitor
            sct_screenshot = sct.grab(monitor)
            mss.tools.to_png(sct_screenshot.rgb, sct_screenshot.size,
                             output=str(temp_path))
    except Exception as e:
        # Fallback: PowerShell PrintScreen
        try:
            ps_script = """
Add-Type -Assembly System.Windows.Forms
$bitmap = [System.Windows.Forms.Clipboard]::GetImage()
if ($bitmap) {
    $path = "{0}"
    $bitmap.Save($path, [System.Drawing.Imaging.ImageFormat]::Png)
    Write-Output $path
}
""" .format(str(temp_path))
            subprocess.run(["powershell", "-Command", ps_script],
                           capture_output=True, timeout=15, shell=True)
        except Exception as e2:
            return make_result("screenshot", "error",
                               text=f"Screenshot fehlgeschlagen: mss: {e}; PS: {e2}")

    return vision_describe(str(temp_path))


def vision_describe(image_path: str) -> dict:
    """Analysiert ein Bild via Pillow und gibt eine Text-Deskription."""
    try:
        from PIL import Image
    except ImportError:
        return make_result("describe", "error",
                           text="Pillow nicht installiert (pip install Pillow)")

    path = Path(image_path)
    if not path.exists():
        return make_result("describe", "error",
                           text=f"Datei nicht gefunden: {image_path}")

    try:
        img = Image.open(path)
        width, height = img.size
        mode = img.mode
        format_name = img.format or "UNKNOWN"

        # Grundlegende Pixelanalyse – besseres Sampling über Grid
        img_data = img.get_flattened_data()
        total_pixels = len(img_data) // 3 if mode == "RGB" else len(img_data)
        step_x = max(1, width // 40)
        step_y = max(1, height // 40)
        sample = []
        for y in range(0, height, step_y):
            for x in range(0, width, step_x):
                px = img.getpixel((x, y))
                sample.append(px)

        # Farbanalyse – dominante Farben per Sampling
        color_count: dict = {}
        for px in sample:
            if isinstance(px, (tuple, list)):
                key = f"rgb({px[0]},{px[1]},{px[2]})"
                color_count[key] = color_count.get(key, 0) + 1
            else:
                key = f"gray({px})"
                color_count[key] = color_count.get(key, 0) + 1

        sorted_colors = sorted(color_count.items(),
                               key=lambda x: -x[1])[:10]

        # Helligkeit / Kontrast
        brightness_values = []
        for px in sample:
            if isinstance(px, (tuple, list)):
                brightness_values.append(
                    (0.299 * px[0] + 0.587 * px[1] + 0.114 * px[2]) / 255.0)
            else:
                brightness_values.append(px / 255.0)

        avg_brightness = (sum(brightness_values) / len(brightness_values)
                          if brightness_values else 0)
        contrast = (max(brightness_values) - min(brightness_values)
                    if brightness_values else 0)

        # Text-Deskription generieren
        lines = [
            f"Bild-Deskription: {path.name}",
            f"  Format: {format_name} | Größe: {width}x{height}px | Modus: {mode}",
            f"  Helligkeit: {avg_brightness:.2f} (0=schwarz, 1=weiß)",
            f"  Kontrast: {contrast:.2f}",
            f"  Pixel gesamt: {total_pixels:,}",
            f"  Dominante Farben (aus {len(sample)} Sample-Pixeln):",
        ]
        for color, count in sorted_colors:
            pct = (count / len(sample)) * 100
            lines.append(f"    {color}: {pct:.1f}%")

        # Kategorisierung
        if avg_brightness < 0.15:
            lines.append("  Kategorie: sehr dunkel / Nacht")
        elif avg_brightness < 0.35:
            lines.append("  Kategorie: dunkel")
        elif avg_brightness < 0.65:
            lines.append("  Kategorie: normal / ausgewogen")
        elif avg_brightness < 0.85:
            lines.append("  Kategorie: hell")
        else:
            lines.append("  Kategorie: sehr hell / überstrahlt")

        # Text-/Code-Verdacht
        sample_edges = sum(1 for i in range(len(brightness_values) - 1)
                           if abs(brightness_values[i] -
                                  brightness_values[i+1]) > 0.2)
        edge_ratio = sample_edges / max(len(brightness_values) - 1, 1)
        if edge_ratio > 0.3:
            lines.append("  Vermutung: starke Kontrastübergänge → Code/Text/UI")
        elif edge_ratio > 0.15:
            lines.append("  Vermutung: moderate Kontrastübergänge → Foto/Grafik")
        else:
            lines.append("  Vermutung: weiche Übergänge → Natur/Gradient")

        description = "\n".join(lines)

        # Base64-Thumbnail (klein) für Weiterverarbeitung
        thumb = img.copy()
        thumb.thumbnail((320, 240))
        buf = tempfile.SpooledTemporaryFile()
        thumb.save(buf, format="PNG")
        buf.seek(0)
        b64 = base64.b64encode(buf.read()).decode()
        buf.close()

        return make_result(
            "describe", "ok",
            text=description,
            file_path=str(path),
            metadata={
                "width": width,
                "height": height,
                "format": format_name,
                "mode": mode,
                "avg_brightness": round(avg_brightness, 3),
                "contrast": round(contrast, 3),
                "total_pixels": total_pixels,
                "dominant_colors": sorted_colors[:5],
                "thumbnail_base64": b64[:200] + "...",  # nur Preview
            }
        )
    except Exception as e:
        return make_result("describe", "error",
                           text=f"Fehler bei Bildanalyse: {e}",
                           file_path=image_path)


def vision_diagram(image_path: str) -> dict:
    """Extrahiert Text aus Code-Diagramm-Screenshots (OCR-artig)."""
    try:
        from PIL import Image
    except ImportError:
        return make_result("diagram", "error",
                           text="Pillow nicht installiert")

    path = Path(image_path)
    if not path.exists():
        return make_result("diagram", "error",
                           text=f"Datei nicht gefunden: {image_path}")

    try:
        img = Image.open(path)
        w, h = img.size

        # 1. Regionen mit hohem Kontrast als "Text-Blobs" erkennen
        #    (vereinfachte Heuristik)
        regions = []
        step = max(1, w // 80)  # horizontales Sampling
        prev_bright = None
        region_start = 0

        for x in range(0, w, step):
            # Durchschnittshelligkeit in einem vertikalen Streifen
            strip_bright = 0
            count = 0
            for y in range(0, h, step):
                px = img.getpixel((x, y))
                if isinstance(px, (tuple, list)):
                    b = (0.299 * px[0] + 0.587 * px[1] + 0.114 * px[2]) / 255
                else:
                    b = px / 255
                strip_bright += b
                count += 1

            if count:
                strip_bright /= count

            if prev_bright is not None:
                if abs(strip_bright - prev_bright) > 0.25:
                    if region_start < x:
                        regions.append((region_start, x))
                    region_start = x
            prev_bright = strip_bright

        regions.append((region_start, w))

        # 2. Text in "leise" Regionen extrahieren (hell auf dunkel / dunkel auf hell)
        text_fragments = []
        for rx_start, rx_end in regions:
            if rx_end - rx_start < step * 2:
                continue
            # Scan vertical stripe for text-like patterns
            text_lines = []
            for y in range(0, h, step * 2):
                line_brights = []
                for x in range(rx_start, rx_end, step):
                    px = img.getpixel((x, y))
                    if isinstance(px, (tuple, list)):
                        b = (0.299 * px[0] + 0.587 * px[1] + 0.114 * px[2]) / 255
                    else:
                        b = px / 255
                    line_brights.append(b)

                if line_brights:
                    local_contrast = max(line_brights) - min(line_brights)
                    if local_contrast > 0.3:
                        # Text-Zeile gefunden
                        chars = []
                        for b in line_brights:
                            if b > 0.5:
                                chars.append("█")
                            elif b > 0.3:
                                chars.append("▓")
                            elif b > 0.15:
                                chars.append("▒")
                            else:
                                chars.append("░")
                        text_lines.append("".join(chars))

            if text_lines:
                sep = " | "
                text_fragments.append(
                    f"[Region {rx_start}-{rx_end}px] {sep.join(text_lines[:5])}")

        text = "\n".join(text_fragments)
        summary = (
            f"Diagramm: {path.name} ({w}x{h}px)\n"
            f"Erkannte Kontrast-Regionen: {len(regions)}\n"
            f"Text-ähnliche Zeilen: {len(text_fragments)}\n"
            f"\nASCII-Darstellung der hellen Textregionen:\n{text}"
        )

        return make_result(
            "diagram", "ok",
            text=summary,
            file_path=str(path),
            metadata={
                "width": w,
                "height": h,
                "regions_detected": len(regions),
                "text_lines_detected": len(text_fragments),
            }
        )
    except Exception as e:
        return make_result("diagram", "error",
                           text=f"Fehler bei Diagramm-Analyse: {e}",
                           file_path=image_path)


# ═══════════════════════════════════════════════════════════════════════════════
# AUDIO
# ═══════════════════════════════════════════════════════════════════════════════

def audio_transcribe(audio_path: str) -> dict:
    """Transkribiert eine Audiodatei via Whisper (falls installiert)."""
    try:
        import whisper
    except ImportError:
        return make_result("transcribe", "error",
                           text="openai-whisper nicht installiert (pip install openai-whisper)")

    path = Path(audio_path)
    if not path.exists():
        return make_result("transcribe", "error",
                           text=f"Datei nicht gefunden: {audio_path}")

    try:
        model = whisper.load_model(WHISPER_MODEL)
        result = model.transcribe(str(path), language="de")
        transcription = result.get("text", "").strip()
        segments = result.get("segments", [])
        duration = result.get("duration", 0)
        language = result.get("language", "de")

        metadata = {
            "model": WHISPER_MODEL,
            "language": language,
            "duration_sec": round(duration, 2),
            "segments": len(segments),
        }
        return make_result("transcribe", "ok",
                           text=transcription,
                           file_path=str(path),
                           metadata=metadata)
    except Exception as e:
        return make_result("transcribe", "error",
                           text=f"Transkription fehlgeschlagen: {e}",
                           file_path=audio_path)


def audio_record(seconds: int = RECORD_SECONDS) -> dict:
    """Nimmt Mikrofon auf (PyAudio) und transkribiert."""
    temp_path = OUTPUT_DIR / f"recording_{int(time.time())}.wav"

    # Versuche PyAudio
    try:
        import pyaudio
        import wave
    except ImportError:
        # Fallback: PowerShell SoundRecorder
        try:
            ps_script = f"""
$rec = New-Object System.Media.SoundRecorder
$rec.FileName = "{temp_path}"
$rec.Record()
Start-Sleep -Seconds {seconds}
$rec.Stop()
Write-Output "Aufnahme gespeichert: {temp_path}"
"""
            subprocess.run(["powershell", "-Command", ps_script],
                           capture_output=True, timeout=seconds + 10, shell=True)
            # PowerShell kann kein WAV aus System.Media:
            # Fallback auf ffmpeg-los direkt WAV mit Python
            return make_result("record", "error",
                               text="PowerShell SoundRecorder unterstützt kein WAV. "
                                    "Installiere PyAudio: pip install PyAudio")
        except Exception as e:
            return make_result("record", "error",
                               text=f"Mikrofon-Aufnahme fehlgeschlagen: {e}")

    # PyAudio-Aufnahme
    try:
        p = pyaudio.PyAudio()
        stream = p.open(format=pyaudio.paInt16,
                        channels=1,
                        rate=SAMPLE_RATE,
                        input=True,
                        frames_per_buffer=1024)

        print(f"🟢 Aufnahme läuft ({seconds}s) …", file=sys.stderr)
        frames = []
        for _ in range(0, int(SAMPLE_RATE / 1024 * seconds)):
            data = stream.read(1024, exception_on_overflow=False)
            frames.append(data)

        stream.stop_stream()
        stream.close()
        p.terminate()

        # WAV speichern
        import wave
        with wave.open(str(temp_path), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(p.get_sample_size(pyaudio.paInt16))
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(b"".join(frames))

        print(f"✅ Aufnahme gespeichert: {temp_path}", file=sys.stderr)
    except Exception as e:
        return make_result("record", "error",
                           text=f"PyAudio-Aufnahme fehlgeschlagen: {e}")

    # Transkribieren
    return audio_transcribe(str(temp_path))


# ═══════════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Vision + Audio Pipeline — Multimodal Understanding",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Beispiele:
  python vision-audio.py --screenshot
  python vision-audio.py --describe screenshot.png
  python vision-audio.py --diagram code-flow.png
  python vision-audio.py --transcribe meeting.wav
  python vision-audio.py --record
  python vision-audio.py --record --seconds 30
        """,
    )

    # Vision
    parser.add_argument("--screenshot", action="store_true",
                        help="Screenshot aufnehmen + beschreiben")
    parser.add_argument("--describe", metavar="BILD",
                        help="Bilddatei beschreiben (Pixel-Analyse)")
    parser.add_argument("--diagram", metavar="DIAGRAMM",
                        help="Code-Diagramm-Screenshot analysieren")

    # Audio
    parser.add_argument("--transcribe", metavar="AUDIO",
                        help="Audiodatei transkribieren")
    parser.add_argument("--record", action="store_true",
                        help="Mikrofon aufnehmen + transkribieren")
    parser.add_argument("--seconds", type=int, default=RECORD_SECONDS,
                        help=f"Aufnahmedauer in Sekunden (Default: {RECORD_SECONDS})")

    # Output
    parser.add_argument("--json", action="store_true",
                        help="Nur JSON ausgeben (keine Stderr-Info)")

    args = parser.parse_args()

    result = None

    if args.screenshot:
        result = vision_screenshot()
    elif args.describe:
        result = vision_describe(args.describe)
    elif args.diagram:
        result = vision_diagram(args.diagram)
    elif args.transcribe:
        result = audio_transcribe(args.transcribe)
    elif args.record:
        result = audio_record(args.seconds)
    else:
        parser.print_help()
        sys.exit(1)

    print_json(result)


if __name__ == "__main__":
    main()