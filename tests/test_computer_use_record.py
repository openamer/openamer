"""Tests for openamer_cli.computer_use_record — recording/playback system."""
import pathlib
import tempfile

import pytest

from openamer_cli.computer_use_record import (
    ComputerUseRecording,
    ComputerUseAction,
    RecordingStore,
    play_recording,
)


@pytest.fixture(autouse=True)
def isolate_home(monkeypatch):
    """Isolate OPENAMER_HOME to a temp dir so recordings don't collide."""
    with tempfile.TemporaryDirectory() as tmp:
        p = pathlib.Path(tmp)
        (p / "recordings").mkdir(parents=True, exist_ok=True)
        monkeypatch.setenv("OPENAMER_HOME", str(p))
        yield p


@pytest.fixture
def sample_recording():
    """Create a sample recording in the temp home."""
    recording = ComputerUseRecording(
        name="test-recording",
        description="A test recording",
    )
    recording.actions = [
        ComputerUseAction(action="click", coordinate=[100, 200], delay=0.5),
        ComputerUseAction(action="type", text="hello world", delay=0.3),
    ]
    RecordingStore.save(recording)
    return recording


class TestRecordingStore:
    def test_save_and_load(self):
        recording = ComputerUseRecording(name="my-recording")
        recording.actions = [ComputerUseAction(action="click", coordinate=[10, 20])]
        RecordingStore.save(recording)
        loaded = RecordingStore.load("my-recording")
        assert loaded is not None
        assert loaded.name == "my-recording"
        assert len(loaded.actions) == 1

    def test_save_and_load_roundtrip(self):
        rec = ComputerUseRecording(name="roundtrip")
        rec.actions = [ComputerUseAction(action="key", keys="cmd+s")]
        RecordingStore.save(rec)
        loaded = RecordingStore.load("roundtrip")
        assert loaded is not None
        assert loaded.actions[0].action == "key"

    def test_load_missing(self):
        loaded = RecordingStore.load("does-not-exist")
        assert loaded is None

    def test_list_recordings(self, sample_recording):
        recordings = RecordingStore.list_recordings()
        names = [r["name"] for r in recordings]
        assert "test-recording" in names

    def test_list_empty(self):
        recordings = RecordingStore.list_recordings()
        assert isinstance(recordings, list)

    def test_delete(self, sample_recording):
        assert RecordingStore.delete("test-recording") is True
        assert RecordingStore.load("test-recording") is None

    def test_delete_missing(self):
        assert RecordingStore.delete("does-not-exist") is False


class TestComputerUseRecording:
    def test_default_creation(self):
        rec = ComputerUseRecording(name="test")
        assert rec.name == "test"
        assert rec.description == ""
        assert len(rec.actions) == 0
        assert rec.created_at is not None

    def test_action_dataclass_roundtrip(self):
        action = ComputerUseAction(action="click", coordinate=[100, 200], delay=0.5)
        assert action.action == "click"
        assert action.coordinate == [100, 200]
        assert action.text is None  # default


class TestPlayRecording:
    def test_play_missing(self):
        result = play_recording("does-not-exist", verbose=False)
        assert result is False

    def test_structure(self, sample_recording):
        """Verify the recording has proper structure."""
        loaded = RecordingStore.load("test-recording")
        assert loaded is not None
        assert len(loaded.actions) == 2
        assert loaded.actions[0].action == "click"


class TestCLICommands:
    def test_all_cmds_callable(self):
        """All CLI handler functions are importable and callable."""
        from openamer_cli.computer_use_record import (
            cmd_record, cmd_play, cmd_list_recordings,
            cmd_delete_recording, cmd_schedule_recording,
        )
        assert callable(cmd_record)
        assert callable(cmd_play)
        assert callable(cmd_list_recordings)
        assert callable(cmd_delete_recording)
        assert callable(cmd_schedule_recording)