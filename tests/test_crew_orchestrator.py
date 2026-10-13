"""Tests for openamer_cli.crew_orchestrator — multi-agent crew system."""
import json
import pathlib
import tempfile

import pytest

from openamer_cli.crew_orchestrator import (
    CrewMember,
    Crew,
    CrewStore,
)


@pytest.fixture(autouse=True)
def isolated_store(monkeypatch):
    """Return a CrewStore backed by a temp dir."""
    with tempfile.TemporaryDirectory() as tmp:
        p = pathlib.Path(tmp)
        crews_dir = p / "crews"
        crews_dir.mkdir(parents=True)
        monkeypatch.setattr("openamer_cli.crew_orchestrator.CREWS_DIR", crews_dir)
        yield CrewStore(crews_dir=crews_dir)


class TestCrewMember:
    def test_default_creation(self):
        m = CrewMember(name="researcher-1", role="researcher", goal="Find info", backstory="Expert researcher")
        assert m.name == "researcher-1"
        assert m.role == "researcher"
        assert m.goal == "Find info"


class TestCrew:
    def test_default_creation(self):
        m1 = CrewMember(name="r1", role="researcher", goal="Find", backstory="Researcher")
        m2 = CrewMember(name="w1", role="writer", goal="Write", backstory="Writer")
        crew = Crew(name="test-crew", members=[m1, m2])
        assert crew.name == "test-crew"
        assert len(crew.members) == 2

    def test_to_dict_roundtrip(self):
        m = CrewMember(name="r1", role="researcher", goal="Find", backstory="R")
        crew = Crew(name="roundtrip", members=[m])
        d = crew.to_dict()
        assert d["name"] == "roundtrip"
        c2 = Crew.from_dict(d)
        assert c2.name == "roundtrip"
        assert c2.members[0].role == "researcher"


class TestCrewStore:
    def test_save_and_load(self, isolated_store):
        m = CrewMember(name="a1", role="analyst", goal="Analyze", backstory="Analyst")
        crew = Crew(name="analysis-crew", members=[m])
        isolated_store.save(crew)
        loaded = isolated_store.load("analysis-crew")
        assert loaded is not None
        assert loaded.name == "analysis-crew"
        assert len(loaded.members) == 1

    def test_load_missing(self, isolated_store):
        with pytest.raises(FileNotFoundError):
            isolated_store.load("does-not-exist")

    def test_list_crews(self, isolated_store):
        m = CrewMember(name="r1", role="researcher", goal="Find", backstory="R")
        isolated_store.save(Crew(name="crew-a", members=[m]))
        isolated_store.save(Crew(name="crew-b", members=[m]))
        crews = isolated_store.list()
        assert len(crews) == 2
        assert "crew-a" in crews
        assert "crew-b" in crews

    def test_delete(self, isolated_store):
        m = CrewMember(name="r1", role="researcher", goal="Find", backstory="R")
        isolated_store.save(Crew(name="delete-me", members=[m]))
        assert isolated_store.delete("delete-me") is True
        with pytest.raises(FileNotFoundError):
            isolated_store.load("delete-me")

    def test_delete_missing(self, isolated_store):
        assert isolated_store.delete("ghost") is False