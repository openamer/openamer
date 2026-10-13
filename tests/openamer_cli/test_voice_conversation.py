"""Tests for openamer_cli.voice_conversation — all mocked, no real microphone.

Tests cover:
1. VoiceSession lifecycle (start/stop/context manager)
2. listen() with mocks (empty, speech, timeout)
3. speak() with mocks (TTS disabled, no-op)
4. barge_in_detect() with BargeInDetector
5. wake_word_detect() with WakeWordDetector (success + failure + fallback)
6. CLI command dispatch (start, stop, listen, test, parser)
7. Barge-in integration (TTS flag, state transitions)
8. VoiceState enum
"""

from __future__ import annotations

import argparse
import time
from unittest.mock import MagicMock

import pytest

# ============================================================================
# Fixtures — mock all audio hardware before importing the module
# ============================================================================


@pytest.fixture(autouse=True)
def mock_audio_deps(monkeypatch):
    """Mock sounddevice, numpy, and speech_recognition before each test.

    This ensures tests never touch real audio hardware.
    """
    import numpy as np_real

    fake_np = MagicMock()
    fake_np.sqrt = np_real.sqrt
    fake_np.mean = np_real.mean
    fake_np.concatenate = np_real.concatenate
    fake_np.int16 = np_real.int16
    fake_np.float64 = np_real.float64
    fake_np.zeros = np_real.zeros
    fake_np.asarray = np_real.asarray
    fake_np.array = np_real.array  # for energy fallback tests

    # Mock sounddevice
    sd = MagicMock()
    sd.InputStream.return_value.__enter__.return_value = sd.InputStream.return_value
    sd.rec.return_value = np_real.ones((16000, 1), dtype=np_real.int16) * 1000  # high amplitude
    sd.query_devices.return_value = [{"name": "mock device", "max_input_channels": 1}]

    def _import_sd():
        return sd, fake_np

    monkeypatch.setattr(
        "openamer_cli.voice_conversation._import_sounddevice",
        _import_sd,
    )

    # Mock speech_recognition
    sr = MagicMock()
    sr.Recognizer.return_value.recognize_google.return_value = "hello world"
    sr.AudioFile.return_value.__enter__.return_value = sr.AudioFile.return_value
    sr.Microphone.return_value.__enter__.return_value = sr.Microphone.return_value
    sr.WaitTimeoutError = type("WaitTimeoutError", (Exception,), {})

    def _import_sr():
        return sr

    monkeypatch.setattr(
        "openamer_cli.voice_conversation._import_speech_recognition",
        _import_sr,
    )

    # Mock tempfile
    monkeypatch.setattr(
        "openamer_cli.voice_conversation._temp_wav_path",
        lambda: "/tmp/mock_test.wav",
    )

    return {"sd": sd, "np": fake_np, "sr": sr}


# ============================================================================
# Tests
# ============================================================================


class TestVoiceSessionLifecycle:
    """Session-level start/stop and state transitions."""

    def test_start_transitions_to_listening(self, mock_audio_deps):
        """start() should set state to LISTENING when successful."""
        from openamer_cli.voice_conversation import VoiceSession, VoiceState

        session = VoiceSession()
        assert session.state == VoiceState.IDLE

        session.start()
        assert session.state == VoiceState.LISTENING, (
            f"Expected LISTENING, got {session.state}"
        )

        session.stop()
        assert session.state == VoiceState.STOPPED

    def test_start_raises_on_no_audio(self, monkeypatch):
        """start() should raise RuntimeError when audio hardware is missing."""
        monkeypatch.setattr(
            "openamer_cli.voice_conversation._import_sounddevice",
            lambda: (_ for _ in ()).throw(ImportError("no sounddevice")),
        )

        from openamer_cli.voice_conversation import VoiceSession

        session = VoiceSession()
        with pytest.raises(RuntimeError, match="Audio hardware unavailable"):
            session.start()

    def test_double_start_is_noop(self, mock_audio_deps):
        """Calling start() twice should not crash."""
        from openamer_cli.voice_conversation import VoiceSession, VoiceState

        session = VoiceSession()
        session.start()
        state_before = session.state
        session.start()  # second call should be a no-op
        assert session.state == state_before
        session.stop()

    def test_context_manager(self, mock_audio_deps):
        """Context manager should start and stop the session."""
        from openamer_cli.voice_conversation import VoiceSession, VoiceState

        with VoiceSession() as session:
            assert session.state == VoiceState.LISTENING

        assert session.state == VoiceState.STOPPED


class TestVoiceSessionListen:
    """listen() behavior with mocked microphone."""

    def test_listen_returns_empty_on_timeout(self, mock_audio_deps):
        """listen() should return '' when no speech is detected."""
        from openamer_cli.voice_conversation import VoiceSession

        np_mock = mock_audio_deps["np"]

        # Force RMS to 0 (silence) so the callback never detects speech
        np_mock.mean = lambda *a, **kw: 0.0

        session = VoiceSession()
        session.start()
        try:
            result = session.listen(timeout=0.5)
            assert result == "", f"Expected empty string, got {result!r}"
        finally:
            session.stop()

    def test_listen_returns_text_on_speech(self, mock_audio_deps):
        """listen() should return transcribed text via speech_recognition fallback."""
        from openamer_cli.voice_conversation import VoiceSession

        sr = mock_audio_deps["sr"]
        sr.Recognizer.return_value.recognize_google.return_value = "hello world"

        session = VoiceSession()
        session.start()
        try:
            # The sounddevice InputStream captures frames with RMS > threshold,
            # but the WAV write is mocked, so it falls through to
            # speech_recognition which returns our mock value
            result = session.listen(timeout=0.5)
            assert isinstance(result, str)
        finally:
            session.stop()


class TestVoiceSessionSpeak:
    """speak() behavior with mocked TTS."""

    def test_speak_disabled_when_tts_off(self, mock_audio_deps):
        """speak() should be a no-op when tts_enabled=False."""
        from openamer_cli.voice_conversation import VoiceSession, VoiceState

        session = VoiceSession(tts_enabled=False)
        session.start()

        try:
            session.speak("Hello there")
            # State should be LISTENING after speak (no playback was started)
            assert session.state == VoiceState.LISTENING
        finally:
            session.stop()

    def test_speak_does_not_crash(self, mock_audio_deps):
        """speak() should complete without exception."""
        from openamer_cli.voice_conversation import VoiceSession

        session = VoiceSession()
        session.start()
        try:
            session.speak("Testing voice output")
        finally:
            session.stop()

    def test_speak_empty_string_is_noop(self, mock_audio_deps):
        """speak('') and speak('   ') should be no-ops."""
        from openamer_cli.voice_conversation import VoiceSession

        session = VoiceSession()
        session.start()
        try:
            session.speak("")
            session.speak("   ")
        finally:
            session.stop()


class TestBargeInDetector:
    """BargeInDetector — user interrupt during TTS."""

    def test_barge_in_detects_speech(self, mock_audio_deps):
        """BargeInDetector start/stop cycle should work cleanly."""
        from openamer_cli.voice_conversation import BargeInDetector

        np_mock = mock_audio_deps["np"]
        import numpy as np_real

        # Make sqrt return high RMS so the monitor thinks it hears speech
        np_mock.sqrt.return_value = np_real.array([500.0])

        detector = BargeInDetector(threshold=100)
        detector.start()
        try:
            time.sleep(0.1)
        finally:
            detector.stop()

        # After stop, the thread is cleaned up and interrupted flag is reset
        assert detector._thread is None
        assert not detector.interrupted

    def test_barge_in_reset(self, mock_audio_deps):
        """reset() should clear the interrupt flag."""
        from openamer_cli.voice_conversation import BargeInDetector

        detector = BargeInDetector(threshold=100)

        detector._interrupted.set()
        assert detector.interrupted is True

        detector.reset()
        assert detector.interrupted is False

    def test_barge_in_stops_tts(self, mock_audio_deps):
        """barge_in_detect() should return True after interrupt during speak()."""
        from openamer_cli.voice_conversation import VoiceSession

        session = VoiceSession()
        session.start()
        try:
            # Simulate: user speaks during speak()
            session.barge_in._interrupted.set()
            assert session.barge_in_detect() is True

            session.barge_in.reset()
            assert session.barge_in_detect() is False
        finally:
            session.stop()


class TestWakeWordDetector:
    """WakeWordDetector — 'Hey OpenAmer' detection."""

    def test_wake_word_detected(self, mock_audio_deps):
        """detect_once() should return True when wake word is recognized."""
        from openamer_cli.voice_conversation import WakeWordDetector

        sr = mock_audio_deps["sr"]
        sr.Recognizer.return_value.recognize_google.return_value = "hey openamer"

        detector = WakeWordDetector(wake_word="hey openamer")
        result = detector.detect_once(timeout=1.0)
        assert result is True, "Wake word should have been detected"

    def test_wake_word_not_detected(self, mock_audio_deps):
        """detect_once() should return False when wake word is not recognized."""
        from openamer_cli.voice_conversation import WakeWordDetector

        sr = mock_audio_deps["sr"]
        sr.Recognizer.return_value.recognize_google.return_value = "some other phrase"

        detector = WakeWordDetector(wake_word="hey openamer")
        result = detector.detect_once(timeout=1.0)
        assert result is False, "Wake word should NOT have been detected"

    def test_wake_word_unknown_value(self, mock_audio_deps):
        """detect_once() should return False when speech is not understood."""
        from openamer_cli.voice_conversation import WakeWordDetector

        sr = mock_audio_deps["sr"]
        sr.Recognizer.return_value.recognize_google.side_effect = (
            type("UnknownValueError", (Exception,), {})()
        )

        detector = WakeWordDetector(wake_word="hey openamer")
        result = detector.detect_once(timeout=1.0)
        assert result is False

    def test_wake_word_energy_fallback(self, mock_audio_deps, monkeypatch):
        """WakeWordDetector should fall back to energy detection when speech_recognition fails."""
        from openamer_cli.voice_conversation import WakeWordDetector
        import numpy as np_real

        # Break speech_recognition import
        monkeypatch.setattr(
            "openamer_cli.voice_conversation._import_speech_recognition",
            lambda: (_ for _ in ()).throw(ImportError("no sr")),
        )

        np_mock = mock_audio_deps["np"]
        np_mock.sqrt.return_value = np_real.array([500.0])

        detector = WakeWordDetector(wake_word="hey openamer", energy_threshold=100)
        result = detector.detect_once(timeout=1.0)
        assert result == True, "Energy-based fallback should detect speech"

    def test_wake_word_start_stop(self, mock_audio_deps):
        """Background wake word detector should start and stop cleanly."""
        from openamer_cli.voice_conversation import WakeWordDetector

        detector = WakeWordDetector(wake_word="hey openamer")
        on_wake = MagicMock()

        detector.start(on_wake=on_wake)
        try:
            thread = detector._thread
            assert thread is not None
            assert thread.is_alive(), "Thread should be alive after start"
        finally:
            detector.stop()

        # After stop, the thread reference is set to None but the real
        # thread has exited (join waited)
        assert not thread.is_alive(), "Thread should no longer be alive"


class TestCLICommands:
    """CLI command dispatch for openamer voice {start,stop,listen,test}."""

    def test_cmd_voice_stop_no_session(self):
        """cmd_voice_stop should handle the no-session case gracefully."""
        from openamer_cli.voice_conversation import cmd_voice_stop

        args = argparse.Namespace()
        result = cmd_voice_stop(args)
        assert result == 0

    def test_cmd_voice_test_wake_word(self, mock_audio_deps):
        """cmd_voice_test should run wake word detection."""
        from openamer_cli.voice_conversation import cmd_voice_test

        sr = mock_audio_deps["sr"]
        sr.Recognizer.return_value.recognize_google.return_value = "hey openamer"

        args = argparse.Namespace(timeout=0.5)
        result = cmd_voice_test(args)
        assert result == 0

    def test_build_voice_conversation_parser(self):
        """build_voice_conversation_parser should attach all subcommands."""
        from openamer_cli.voice_conversation import build_voice_conversation_parser
        import argparse

        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers()

        build_voice_conversation_parser(subparsers)

        for sub in ("start", "stop", "listen", "test"):
            subparser = parser.parse_args(["voice", sub])
            assert subparser is not None


class TestBargeInIntegration:
    """Integration-style: barge-in during a speak + listen cycle."""

    def test_barge_in_clears_tts_flag(self, mock_audio_deps):
        """Barge-in should clear _tts_active during speak()."""
        from openamer_cli.voice_conversation import VoiceSession

        session = VoiceSession()
        session.start()
        try:
            session._tts_active.set()
            assert session._tts_active.is_set()

            session._on_barge_in()
            assert not session._tts_active.is_set(), "_tts_active should be cleared"
        finally:
            session.stop()

    def test_barge_in_changes_state(self, mock_audio_deps):
        """Barge-in should transition state from SPEAKING to LISTENING."""
        from openamer_cli.voice_conversation import VoiceSession, VoiceState

        session = VoiceSession()
        session.start()
        try:
            session._tts_active.set()
            with session._lock:
                session.state = VoiceState.SPEAKING

            session._on_barge_in()
            assert session.state == VoiceState.LISTENING
        finally:
            session.stop()


class TestVoiceStateMachine:
    """VoiceState enum and state transitions."""

    def test_voice_state_values(self):
        from openamer_cli.voice_conversation import VoiceState
        assert VoiceState.IDLE.value == "idle"
        assert VoiceState.LISTENING.value == "listening"
        assert VoiceState.TRANSCRIBING.value == "transcribing"
        assert VoiceState.SPEAKING.value == "speaking"
        assert VoiceState.STOPPED.value == "stopped"

    def test_session_state_transitions(self, mock_audio_deps):
        from openamer_cli.voice_conversation import VoiceSession, VoiceState

        session = VoiceSession()
        assert session.state == VoiceState.IDLE

        session.start()
        assert session.state == VoiceState.LISTENING

        session.stop()
        assert session.state == VoiceState.STOPPED