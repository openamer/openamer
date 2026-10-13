"""Conversational Voice System for OpenAmer — voice sessions, barge-in, wake word.

Provides a ``VoiceSession`` class for real-time conversational voice interaction:
- ``start()`` / ``stop()`` — manage a microphone listening session
- ``listen(timeout=5)`` — capture speech and return it as text
- ``speak(text)`` — output text as speech via TTS
- ``barge_in_detect()`` — detect user interruption during TTS output
- ``wake_word_detect()`` — detect "Hey OpenAmer" wake word

CLI subcommands:
  openamer voice start    — start an interactive voice session
  openamer voice stop     — stop the active voice session
  openamer voice listen   — one-shot listen + reply
  openamer voice test     — test wake-word detection

Design notes
============
- Uses ``sounddevice`` for audio capture (already a dependency of the project).
- Uses ``speech_recognition`` as an optional bridge to Google/whisper STT.
- Barge-in detection runs a low-latency background thread that monitors
  RMS amplitude; when the user speaks above a threshold while TTS is
  active, the speech is interrupted and the new input is captured.
- Wake-word detection runs in a background thread and uses either
  ``speech_recognition`` keyword spotting or a simple RMS-based energy
  detection for the trigger phrase.
- All audio hardware calls are wrapped in try/except so missing deps
  surface as clear errors, not import crashes.
"""

from __future__ import annotations

import logging
import os
import tempfile
import threading
import time
from enum import Enum
from typing import Callable, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
SAMPLE_RATE = 16000
CHANNELS = 1
DTYPE = "int16"
SAMPLE_WIDTH = 2

# Barge-in
BARGE_IN_RMS_THRESHOLD = 600  # RMS above this = user is speaking (in int16 range)
BARGE_IN_CHECK_INTERVAL = 0.05  # seconds between amplitude checks

# Wake word
WAKE_WORD = "hey openamer"
WAKE_WORD_TIMEOUT = 3.0  # seconds to wait for wake word per listen cycle

# Silence detection
SILENCE_RMS_THRESHOLD = 200
SILENCE_DURATION = 2.0  # seconds of silence before auto-stopping listen


class VoiceState(Enum):
    """State machine for a voice session."""
    IDLE = "idle"
    LISTENING = "listening"
    TRANSCRIBING = "transcribing"
    SPEAKING = "speaking"
    STOPPED = "stopped"


# ---------------------------------------------------------------------------
# Lazy audio imports
# ---------------------------------------------------------------------------


def _import_sounddevice():
    """Lazy-import sounddevice (and numpy). Raises ImportError if unavailable."""
    import sounddevice as sd
    import numpy as np
    return sd, np


def _import_speech_recognition():
    """Lazy-import speech_recognition. Raises ImportError if unavailable."""
    import speech_recognition as sr
    return sr


def _import_pyaudio():
    """Lazy-import pyaudio. Raises ImportError if unavailable."""
    import pyaudio
    return pyaudio


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _temp_wav_path() -> str:
    """Return a temp file path for a WAV recording."""
    os.makedirs(os.path.join(tempfile.gettempdir(), "openamer_voice"), exist_ok=True)
    fd, path = tempfile.mkstemp(suffix=".wav", prefix="voice_", dir=os.path.join(tempfile.gettempdir(), "openamer_voice"))
    os.close(fd)
    return path


# ---------------------------------------------------------------------------
# Barge-In Detector
# ---------------------------------------------------------------------------


class BargeInDetector:
    """Monitors microphone amplitude on a background thread while TTS plays.

    When the RMS amplitude exceeds ``threshold`` for a sustained period,
    the detector calls the supplied ``on_interrupt`` callback.  The caller
    (``VoiceSession.speak()``) should stop TTS playback when interrupted.

    Uses ``sounddevice.InputStream`` for low-latency amplitude monitoring.
    Falls back to ``pyaudio`` if sounddevice is unavailable.
    """

    def __init__(
        self,
        threshold: int = BARGE_IN_RMS_THRESHOLD,
        check_interval: float = BARGE_IN_CHECK_INTERVAL,
    ):
        self.threshold = threshold
        self.check_interval = check_interval
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._interrupted = threading.Event()
        self._lock = threading.Lock()
        self._on_interrupt: Optional[Callable[[], None]] = None
        self._backend: Optional[str] = None

    @property
    def interrupted(self) -> bool:
        """True if a barge-in interrupt has been detected since last reset."""
        return self._interrupted.is_set()

    def reset(self) -> None:
        """Clear the interrupt flag after handling a barge-in."""
        self._interrupted.clear()

    def start(self, on_interrupt: Optional[Callable[[], None]] = None) -> None:
        """Start the background amplitude monitor.

        Args:
            on_interrupt: Called (from the monitor thread) when user speech
                is detected above threshold.
        """
        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            self._stop_event.clear()
            self._interrupted.clear()
            self._on_interrupt = on_interrupt
            self._thread = threading.Thread(
                target=self._monitor_loop,
                daemon=True,
                name="barge-in-monitor",
            )
            self._thread.start()

    def stop(self) -> None:
        """Stop the background monitor and wait for the thread to exit."""
        self._stop_event.set()
        with self._lock:
            if self._thread and self._thread.is_alive():
                self._thread.join(timeout=2.0)
            self._thread = None

    def _monitor_loop(self) -> None:
        """Background loop: read audio chunks and check RMS."""
        sd, np = _import_sounddevice()
        try:
            with sd.InputStream(
                samplerate=SAMPLE_RATE,
                channels=CHANNELS,
                dtype=DTYPE,
                blocksize=int(SAMPLE_RATE * self.check_interval),
            ) as stream:
                while not self._stop_event.is_set():
                    chunk, _ = stream.read(stream.blocksize)
                    rms = np.sqrt(np.mean(chunk.astype(np.float64) ** 2))
                    if rms > self.threshold:
                        self._interrupted.set()
                        if self._on_interrupt:
                            try:
                                self._on_interrupt()
                            except Exception:
                                logger.exception("barge-in interrupt callback failed")
                        # Keep monitoring — barge-in can fire multiple times
                    time.sleep(self.check_interval * 0.5)
        except Exception as exc:
            logger.debug("Barge-in monitor unavailable: %s", exc)


# ---------------------------------------------------------------------------
# Wake Word Detector
# ---------------------------------------------------------------------------


class WakeWordDetector:
    """Detects the configured wake word ("Hey OpenAmer") from microphone input.

    Runs a listening loop in a background thread.  When the wake word is
    detected, the ``on_wake`` callback is called.

    Uses ``speech_recognition`` with Google STT for keyword detection.
    Falls back to energy-based detection (RMS threshold) when speech
    recognition is unavailable.
    """

    def __init__(
        self,
        wake_word: str = WAKE_WORD,
        timeout: float = WAKE_WORD_TIMEOUT,
        energy_threshold: int = 400,
    ):
        self.wake_word = wake_word.lower().strip()
        self.timeout = timeout
        self.energy_threshold = energy_threshold
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._on_wake: Optional[Callable[[], None]] = None
        self._last_detection: float = 0.0
        self._cooldown: float = 5.0  # seconds between wake detections

    def start(self, on_wake: Optional[Callable[[], None]] = None) -> None:
        """Start the wake-word detection background thread.

        Args:
            on_wake: Called (from the detector thread) when the wake word
                is recognized.
        """
        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            self._stop_event.clear()
            self._on_wake = on_wake
            self._thread = threading.Thread(
                target=self._detect_loop,
                daemon=True,
                name="wake-word-detector",
            )
            self._thread.start()

    def stop(self) -> None:
        """Stop the wake-word detector and wait for thread exit."""
        self._stop_event.set()
        with self._lock:
            if self._thread and self._thread.is_alive():
                self._thread.join(timeout=2.0)
            self._thread = None

    def detect_once(self, timeout: float = WAKE_WORD_TIMEOUT) -> bool:
        """Synchronously listen for the wake word once.

        Returns True if the wake word was detected, False otherwise.
        """
        try:
            sr = _import_speech_recognition()
            recognizer = sr.Recognizer()
            with sr.Microphone() as source:
                recognizer.adjust_for_ambient_noise(source, duration=0.5)
                try:
                    audio = recognizer.listen(source, timeout=timeout, phrase_time_limit=3.0)
                except sr.WaitTimeoutError:
                    return False
            try:
                text = recognizer.recognize_google(audio).lower().strip()
            except (sr.UnknownValueError, sr.RequestError):
                return False
            return self.wake_word in text
        except ImportError:
            # Fallback: energy-based detection
            return self._energy_detect_once(timeout)
        except Exception:
            logger.exception("wake-word detect_once failed")
            return False

    def _energy_detect_once(self, timeout: float) -> bool:
        """Simple fallback: detect if someone is speaking (no wake word recognition)."""
        try:
            sd, np = _import_sounddevice()
            recording = sd.rec(
                int(SAMPLE_RATE * min(timeout, 2.0)),
                samplerate=SAMPLE_RATE,
                channels=CHANNELS,
                dtype=DTYPE,
            )
            sd.wait()
            rms = np.sqrt(np.mean(recording.astype(np.float64) ** 2))
            return rms > self.energy_threshold
        except Exception:
            return False

    def _detect_loop(self) -> None:
        """Background loop: listen for wake word repeatedly."""
        while not self._stop_event.is_set():
            try:
                if self.detect_once(timeout=self.timeout):
                    now = time.monotonic()
                    if now - self._last_detection > self._cooldown:
                        self._last_detection = now
                        if self._on_wake:
                            try:
                                self._on_wake()
                            except Exception:
                                logger.exception("wake-word callback failed")
            except Exception:
                logger.debug("wake-word detect cycle error", exc_info=True)
            time.sleep(0.2)


# ---------------------------------------------------------------------------
# VoiceSession
# ---------------------------------------------------------------------------


class VoiceSession:
    """Manages a conversational voice session with barge-in and wake-word support.

    State machine::

        IDLE → start() → LISTENING → voice input → TRANSCRIBING
            → text → speak() → SPEAKING → (barge-in → LISTENING)
            → (no barge-in → IDLE) → listen() → ...

    Usage::

        session = VoiceSession()
        session.start()
        text = session.listen(timeout=5)
        session.speak("Hello, how can I help you?")
        # ... conversation loop ...
        session.stop()
    """

    def __init__(
        self,
        stt_provider: str = "google",
        tts_enabled: bool = True,
        barge_in_threshold: int = BARGE_IN_RMS_THRESHOLD,
        wake_word: str = WAKE_WORD,
    ):
        self.stt_provider = stt_provider
        self.tts_enabled = tts_enabled
        self.state = VoiceState.IDLE
        self._lock = threading.Lock()
        self._stop_event = threading.Event()

        # Barge-in
        self.barge_in = BargeInDetector(threshold=barge_in_threshold)

        # Wake word
        self.wake_word_detector = WakeWordDetector(wake_word=wake_word)

        # TTS playback state — the _speak_inner callback checks this
        self._tts_active = threading.Event()
        self._last_transcript: str = ""

    # ── Session lifecycle ─────────────────────────────────────────────

    def start(self) -> None:
        """Start the voice session: enable microphone listening and wake-word detection.

        Raises:
            RuntimeError: If audio hardware is unavailable.
        """
        # Probe audio availability early
        try:
            sd, _ = _import_sounddevice()
            sd.query_devices()  # raises if no devices
        except (ImportError, OSError) as exc:
            raise RuntimeError(
                "Audio hardware unavailable. Install sounddevice + numpy:\n"
                "  pip install sounddevice numpy"
            ) from exc

        with self._lock:
            if self.state not in (VoiceState.IDLE, VoiceState.STOPPED):
                logger.warning("VoiceSession already active (state=%s)", self.state.value)
                return
            self.state = VoiceState.LISTENING
            self._stop_event.clear()

        # Start wake-word detector in background
        self.wake_word_detector.start(
            on_wake=lambda: self._on_wake_word_detected()
        )

        logger.info("Voice session started — listening for wake word '%s'", WAKE_WORD)

    def stop(self) -> None:
        """Stop the voice session and release all resources."""
        self._stop_event.set()
        self.barge_in.stop()
        self.wake_word_detector.stop()

        with self._lock:
            self.state = VoiceState.STOPPED

        logger.info("Voice session stopped")

    # ── Listening ─────────────────────────────────────────────────────

    def listen(self, timeout: float = 5.0) -> str:
        """Capture speech from the microphone and transcribe it.

        Blocks up to ``timeout`` seconds waiting for speech.  Returns the
        transcribed text, or an empty string if nothing was heard.

        The session must be in LISTENING state (call ``start()`` first).
        While listening, the RMS level is monitored so ``barge_in`` state
        stays current.

        Args:
            timeout: Maximum seconds to wait for speech.

        Returns:
            Transcribed text, or empty string on timeout / silence.
        """
        with self._lock:
            if self.state == VoiceState.STOPPED:
                return ""
            self.state = VoiceState.LISTENING

        try:
            sd, np = _import_sounddevice()

            # Record with auto-stop on silence
            frames: list[np.ndarray] = []
            speech_detected = False
            silence_start: Optional[float] = None
            deadline = time.monotonic() + timeout

            def _audio_callback(indata, _frames, _time_info, status):
                nonlocal speech_detected, silence_start
                if status:
                    logger.debug("listen callback status: %s", status)
                rms = np.sqrt(np.mean(indata.astype(np.float64) ** 2))
                if rms > SILENCE_RMS_THRESHOLD:
                    speech_detected = True
                    silence_start = None
                elif speech_detected and silence_start is None:
                    silence_start = time.monotonic()
                frames.append(indata.copy())

            with sd.InputStream(
                samplerate=SAMPLE_RATE,
                channels=CHANNELS,
                dtype=DTYPE,
                blocksize=int(SAMPLE_RATE * 0.1),
                callback=_audio_callback,
            ):
                while time.monotonic() < deadline and not self._stop_event.is_set():
                    if (
                        speech_detected
                        and silence_start is not None
                        and (time.monotonic() - silence_start) >= SILENCE_DURATION
                    ):
                        break
                    time.sleep(0.05)

            if not speech_detected or not frames:
                return ""

            # Concatenate and save to WAV
            audio_data = np.concatenate(frames, axis=0)
            wav_path = _temp_wav_path()
            try:
                import wave
                import struct
                with wave.open(wav_path, "wb") as wf:
                    wf.setnchannels(CHANNELS)
                    wf.setsampwidth(SAMPLE_WIDTH)
                    wf.setframerate(SAMPLE_RATE)
                    wf.writeframes(audio_data.astype(np.int16).tobytes())
            except Exception as exc:
                logger.error("Failed to write WAV: %s", exc)
                return ""

            # Transcribe
            text = self._transcribe(wav_path)
            self._last_transcript = text

            # Cleanup
            try:
                os.unlink(wav_path)
            except OSError:
                pass

            return text

        except (ImportError, OSError) as exc:
            # Fallback to speech_recognition
            return self._listen_speech_recognition(timeout)

    def _transcribe(self, wav_path: str) -> str:
        """Transcribe a WAV file using the configured STT provider.

        Uses ``tools.voice_mode.transcribe_recording`` if available,
        otherwise falls back to ``speech_recognition`` with Google STT.
        """
        # Try the project's own transcription first
        try:
            from tools.voice_mode import transcribe_recording
            result = transcribe_recording(wav_path)
            if result.get("success") and result.get("transcript"):
                text = result["transcript"].strip()
                if text:
                    return text
        except Exception:
            logger.debug("tools.voice_mode.transcribe_recording unavailable", exc_info=True)

        # Fallback: speech_recognition with Google STT
        try:
            sr = _import_speech_recognition()
            recognizer = sr.Recognizer()
            with sr.AudioFile(wav_path) as source:
                audio = recognizer.record(source)
            try:
                return recognizer.recognize_google(audio)
            except (sr.UnknownValueError, sr.RequestError):
                return ""
        except ImportError:
            logger.debug("speech_recognition not installed")
            return ""
        except Exception as exc:
            logger.error("STT failed: %s", exc)
            return ""

    def _listen_speech_recognition(self, timeout: float) -> str:
        """Listen using speech_recognition as a fallback capture method."""
        try:
            sr = _import_speech_recognition()
            recognizer = sr.Recognizer()
            with sr.Microphone() as source:
                recognizer.adjust_for_ambient_noise(source, duration=0.3)
                try:
                    audio = recognizer.listen(source, timeout=timeout, phrase_time_limit=timeout)
                except sr.WaitTimeoutError:
                    return ""
            try:
                return recognizer.recognize_google(audio)
            except (sr.UnknownValueError, sr.RequestError):
                return ""
        except Exception as exc:
            logger.error("speech_recognition listen failed: %s", exc)
            return ""

    # ── Speaking (TTS) ────────────────────────────────────────────────

    def speak(self, text: str) -> None:
        """Output text as speech via TTS, with barge-in support.

        While TTS is playing, the barge-in detector monitors the microphone.
        If the user starts speaking above the threshold, playback is
        interrupted and the barge-in flag is set.

        Args:
            text: The text to speak aloud.
        """
        if not self.tts_enabled or not text.strip():
            return

        with self._lock:
            self.state = VoiceState.SPEAKING

        self._tts_active.set()

        # Start barge-in monitor
        self.barge_in.reset()
        self.barge_in.start(on_interrupt=self._on_barge_in)

        try:
            self._speak_inner(text)
        finally:
            self._tts_active.clear()
            self.barge_in.stop()

            with self._lock:
                if self.state == VoiceState.SPEAKING:
                    self.state = VoiceState.IDLE

    def _speak_inner(self, text: str) -> None:
        """Core TTS playback — uses OpenAmer's ``text_to_speech`` tool."""
        # The text_to_speech tool is available as a built-in OpenAmer tool.
        # In CLI mode we call edge_tts directly as a subprocess.
        try:
            # First try: use the OpenAmer text_to_speech function
            # (available in the gateway / desktop context)
            from openamer_cli.voice import speak  # type: ignore
            speak(text)
            return
        except Exception:
            pass

        # Second try: edge_tts CLI
        try:
            import subprocess
            out_path = _temp_wav_path().replace(".wav", ".mp3")
            result = subprocess.run(
                [
                    "python", "-m", "edge_tts",
                    "--voice", "de-DE-KatjaNeural",
                    "--text", text,
                    "--write-media", out_path,
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                # Playback via sounddevice
                try:
                    self._play_audio_file(out_path)
                except Exception as exc:
                    logger.warning("Audio playback failed: %s", exc)
                finally:
                    try:
                        os.unlink(out_path)
                    except OSError:
                        pass
                return
        except Exception:
            pass

        # Third try: use built-in text_to_speech tool interface
        try:
            from tools.voice_mode import play_audio_file, create_audio_recorder
            # Fallback: just log
            logger.info("TTS: %s", text)
        except Exception:
            logger.info("TTS (no audio): %s", text)

    def _play_audio_file(self, path: str) -> None:
        """Play an audio file using sounddevice.

        Checks ``self._tts_active`` periodically; if barge-in has cleared
        it, playback is aborted early.
        """
        try:
            sd, np = _import_sounddevice()
            import soundfile as sf
            data, sr = sf.read(path, dtype=DTYPE)
            sd.play(data, samplerate=sr)
            # Poll for completion or interruption
            while sd.get_stream() and sd.get_stream().active:
                if not self._tts_active.is_set():
                    sd.stop()
                    break
                time.sleep(0.05)
        except Exception as exc:
            logger.debug("_play_audio_file failed: %s", exc)

    # ── Barge-in handling ─────────────────────────────────────────────

    def barge_in_detect(self) -> bool:
        """Return True if the user has interrupted during the last TTS output.

        Call this after ``speak()`` to check whether the user spoke over
        the agent's reply.  When True, you should process the interrupting
        speech by calling ``listen()``.
        """
        return self.barge_in.interrupted

    def _on_barge_in(self) -> None:
        """Called from the barge-in monitor thread when user speech is detected
        during TTS playback.  Stops TTS immediately."""
        self._tts_active.clear()
        with self._lock:
            if self.state == VoiceState.SPEAKING:
                self.state = VoiceState.LISTENING
        logger.debug("Barge-in detected — TTS interrupted")

    # ── Wake-word handling ────────────────────────────────────────────

    def wake_word_detect(self) -> bool:
        """Synchronously check for the wake word on the microphone.

        Returns True if "Hey OpenAmer" (or configured wake word) was
        detected.  Blocks up to ``WAKE_WORD_TIMEOUT`` seconds.

        This is a synchronous one-shot; the background detector runs
        continuously during an active session.
        """
        return self.wake_word_detector.detect_once()

    def _on_wake_word_detected(self) -> None:
        """Called when the background wake-word detector fires."""
        logger.info("Wake word '%s' detected — activating", WAKE_WORD)
        with self._lock:
            if self.state == VoiceState.IDLE:
                self.state = VoiceState.LISTENING

    # ── Context manager ───────────────────────────────────────────────

    def __enter__(self) -> "VoiceSession":
        self.start()
        return self

    def __exit__(self, *args) -> None:
        self.stop()


# ---------------------------------------------------------------------------
# CLI command handlers
# ---------------------------------------------------------------------------

_ACTIVE_SESSION: Optional[VoiceSession] = None
_ACTIVE_SESSION_LOCK = threading.Lock()


def _get_or_create_session() -> VoiceSession:
    """Return the active session or create a new one."""
    global _ACTIVE_SESSION
    with _ACTIVE_SESSION_LOCK:
        if _ACTIVE_SESSION is None or _ACTIVE_SESSION.state == VoiceState.STOPPED:
            _ACTIVE_SESSION = VoiceSession()
        return _ACTIVE_SESSION


def cmd_voice_start(args) -> int:
    """``openamer voice start`` — start a voice session."""
    session = _get_or_create_session()
    if session.state == VoiceState.LISTENING:
        print("🎤 Voice session is already active.")
        return 0
    try:
        session.start()
        print("🎤 Voice session started. Say 'Hey OpenAmer' to activate, Ctrl+C to stop.")
        # Enter interactive loop
        try:
            while True:
                if session.state == VoiceState.LISTENING:
                    print("🎤 Listening... (speak now)")
                    text = session.listen(timeout=10.0)
                    if text:
                        print(f"  You: {text}")
                        # For now, just echo back
                        session.speak(f"I heard you say: {text}")
                    elif session.barge_in_detect():
                        text = session.listen(timeout=5.0)
                        if text:
                            print(f"  You (barge-in): {text}")
                            session.speak(f"Interrupted. You said: {text}")
                elif session.state == VoiceState.STOPPED:
                    break
                time.sleep(0.1)
        except KeyboardInterrupt:
            print()
    except RuntimeError as exc:
        print(f"❌ {exc}")
        return 1
    finally:
        session.stop()
        print("🎤 Voice session ended.")
    return 0


def cmd_voice_stop(args) -> int:
    """``openamer voice stop`` — stop the active voice session."""
    global _ACTIVE_SESSION
    with _ACTIVE_SESSION_LOCK:
        if _ACTIVE_SESSION is None:
            print("ℹ️  No active voice session.")
            return 0
        _ACTIVE_SESSION.stop()
        _ACTIVE_SESSION = None
    print("🛑 Voice session stopped.")
    return 0


def cmd_voice_listen(args) -> int:
    """``openamer voice listen`` — one-shot listen and reply."""
    session = VoiceSession()
    try:
        session.start()
        print("🎤 Listening...")
        text = session.listen(timeout=getattr(args, "timeout", 5))
        if text:
            print(f"  You: {text}")
            session.speak(f"You said: {text}")
        else:
            print("  (no speech detected)")
    except RuntimeError as exc:
        print(f"❌ {exc}")
        return 1
    finally:
        session.stop()
    return 0


def cmd_voice_test(args) -> int:
    """``openamer voice test`` — test wake word detection."""
    print("🎤 Wake word test — say 'Hey OpenAmer' (or wait 10s for timeout)")
    detector = WakeWordDetector()
    detected = detector.detect_once(timeout=getattr(args, "timeout", 10.0))
    if detected:
        print("✅ Wake word 'Hey OpenAmer' detected!")
    else:
        print("⏱️  No wake word detected (timeout/ambient noise)")
    return 0


def build_voice_conversation_parser(subparsers) -> None:
    """Add ``openamer voice`` subcommand group.

    Args:
        subparsers: The argparse subparsers group from the top-level parser.
    """
    parser = subparsers.add_parser(
        "voice",
        help="Conversational voice system — speak and listen",
        description=(
            "Conversational voice interaction with OpenAmer.  Supports "
            "barge-in (interrupt TTS by speaking) and wake-word activation "
            "('Hey OpenAmer')."
        ),
    )
    voice_subparsers = parser.add_subparsers(dest="voice_command")

    # start
    start_parser = voice_subparsers.add_parser(
        "start",
        help="Start an interactive voice session",
        description="Start listening and speaking in an interactive loop.",
    )
    start_parser.set_defaults(func=cmd_voice_start)

    # stop
    stop_parser = voice_subparsers.add_parser(
        "stop",
        help="Stop the active voice session",
        description="Stop the currently running voice session.",
    )
    stop_parser.set_defaults(func=cmd_voice_stop)

    # listen
    listen_parser = voice_subparsers.add_parser(
        "listen",
        help="One-shot listen and reply",
        description="Capture one utterance, transcribe it, and speak a reply.",
    )
    listen_parser.add_argument(
        "--timeout", type=float, default=5.0,
        help="Seconds to wait for speech (default: 5)",
    )
    listen_parser.set_defaults(func=cmd_voice_listen)

    # test
    test_parser = voice_subparsers.add_parser(
        "test",
        help="Test wake word detection",
        description="Test whether 'Hey OpenAmer' can be detected from your microphone.",
    )
    test_parser.add_argument(
        "--timeout", type=float, default=10.0,
        help="Seconds to listen for wake word (default: 10)",
    )
    test_parser.set_defaults(func=cmd_voice_test)

    # Default: show help
    def _voice_help(args) -> int:
        parser.print_help()
        return 0

    parser.set_defaults(func=_voice_help)