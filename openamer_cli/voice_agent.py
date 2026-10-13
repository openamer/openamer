"""Voice Agents — realtime voice interaction for OpenAmer.

Enables voice-driven agent conversations:
- Voice input via microphone (STT)
- Voice output via TTS
- Full voice agent sessions
"""

from __future__ import annotations

import logging
import os
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class VoiceSession:
    """A voice agent session."""

    session_id: str
    started_at: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%S"))
    messages: List[Dict[str, Any]] = field(default_factory=list)
    duration_seconds: float = 0.0


class VoiceAgent:
    """Voice-enabled agent that can listen and speak."""

    def __init__(self, stt_model: str = "base", tts_enabled: bool = True):
        self.stt_model = stt_model
        self.tts_enabled = tts_enabled
        self._session: Optional[VoiceSession] = None

    def start_session(self) -> VoiceSession:
        """Start a new voice session."""
        import uuid
        self._session = VoiceSession(session_id=str(uuid.uuid4())[:8])
        return self._session

    def transcribe_audio(self, audio_path: str) -> str:
        """Transcribe audio file to text using configured STT."""
        from openamer_cli.config import load_config
        cfg = load_config()
        stt_cfg = cfg.get("stt", {})
        provider = stt_cfg.get("local", {}).get("model", "base")

        try:
            import whisper
            model = whisper.load_model(provider)
            result = model.transcribe(audio_path)
            return result["text"].strip()
        except ImportError:
            logger.warning("whisper not installed, using fallback")
            return self._fallback_stt(audio_path)
        except Exception as exc:
            logger.error("STT failed: %s", exc)
            return ""

    def _fallback_stt(self, audio_path: str) -> str:
        """Fallback STT using system tools."""
        import subprocess
        try:
            result = subprocess.run(
                ["python", "-m", "whisper", audio_path, "--model", "base", "--output_dir", tempfile.gettempdir()],
                capture_output=True, text=True, timeout=60,
            )
            return result.stdout.strip() or result.stderr.strip()
        except Exception:
            return "[STT unavailable]"

    def speak(self, text: str, voice: str = "") -> Optional[str]:
        """Convert text to speech and play it.

        Returns path to the audio file.
        """
        if not self.tts_enabled:
            return None

        from openamer_cli.config import load_config
        cfg = load_config()

        # Try to use the configured TTS provider
        try:
            from openamer_cli import tts
            audio_path = tts.text_to_speech(text, voice=voice)
            return audio_path
        except Exception:
            pass

        # Fallback: use system TTS
        try:
            import subprocess
            tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
            result = subprocess.run(
                ["python", "-m", "edge_tts", "--voice", voice or "de-DE-KatjaNeural",
                 "--text", text, "--write-media", tmp.name],
                capture_output=True, text=True, timeout=30,
            )
            if result.returncode == 0:
                return tmp.name
        except Exception:
            pass

        return None

    def end_session(self) -> VoiceSession:
        """End the current voice session and return stats."""
        if self._session:
            self._session.duration_seconds = time.time() - time.mktime(
                time.strptime(self._session.started_at, "%Y-%m-%dT%H:%M:%S")
            )
        return self._session


def cmd_voice(args) -> None:
    """Start a voice agent session."""
    agent = VoiceAgent()
    session = agent.start_session()
    print(f"🎤 Voice session started: {session.session_id}")
    print("Speak into your microphone. Press Ctrl+C to stop.")

    try:
        import sounddevice as sd
        import soundfile as sf
        import numpy as np

        samplerate = 16000
        duration = 5  # seconds per chunk
        print("Listening...")

        while True:
            recording = sd.rec(int(samplerate * duration), samplerate=samplerate, channels=1)
            sd.wait()
            tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            sf.write(tmp.name, recording, samplerate)

            text = agent.transcribe_audio(tmp.name)
            if text.strip():
                print(f"  You: {text}")
                session.messages.append({"role": "user", "content": text})

            os.unlink(tmp.name)

    except KeyboardInterrupt:
        print("\nVoice session ended.")
    except ImportError:
        print("Voice agent requires: pip install sounddevice soundfile numpy")
        print("Install with: openamer setup voice")
    except Exception as exc:
        print(f"Voice session error: {exc}")

    session = agent.end_session()
    print(f"Session: {session.session_id}, Duration: {session.duration_seconds:.1f}s, "
          f"Messages: {len(session.messages)}")


def build_voice_parser(subparsers) -> None:
    """Add ``openamer voice`` subcommand."""
    parser = subparsers.add_parser(
        "voice",
        help="Start a voice agent session (speech-to-speech)",
        description="Start an interactive voice session with the agent. Speak and listen.",
    )
    parser.add_argument("--stt-model", default="base", help="Whisper model size")
    parser.add_argument("--no-tts", action="store_true", help="Disable text-to-speech")
    parser.set_defaults(func=cmd_voice)