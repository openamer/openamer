"""Tests for openamer_cli.a2a.brain_share — A2A brain knowledge sharing."""
import json
import pathlib
import tempfile

import pytest

from openamer_cli.a2a.brain_share import (
    BrainInsight,
    extract_insights_from_brain,
    export_insights,
    import_insights,
    list_imported_insights,
    get_brain_share_stats,
    cmd_brain_share,
    build_brain_share_parser,
)


@pytest.fixture(autouse=True)
def isolate_home(monkeypatch):
    """Redirect brain dirs to a temp location."""
    with tempfile.TemporaryDirectory() as tmp:
        p = pathlib.Path(tmp)
        brain_dir = p / "a2a"
        brain_dir.mkdir(parents=True)
        insights_dir = brain_dir / "insights"
        insights_dir.mkdir()
        imported_dir = brain_dir / "imported"
        imported_dir.mkdir()
        monkeypatch.setattr("openamer_cli.a2a.brain_share._BRAIN_DIR", brain_dir)
        monkeypatch.setattr("openamer_cli.a2a.brain_share._INSIGHTS_DIR", insights_dir)
        monkeypatch.setattr("openamer_cli.a2a.brain_share._IMPORTED_DIR", imported_dir)
        yield p


@pytest.fixture
def brain_file(isolate_home):
    """Create a minimal brain JSONL file."""
    brain_path = isolate_home / "a2a" / "openamer-brain.jsonl"
    records = [
        {"engine": "trajectory", "topic": "Debugging Python errors", "messages": [{"role": "user", "content": "fix error"}, {"role": "assistant", "content": "try this"}]},
        {"engine": "trajectory", "topic": "Installing Docker on Windows", "messages": [{"role": "user", "content": "install docker"}, {"role": "assistant", "content": "download here"}, {"role": "user", "content": "thanks"}, {"role": "assistant", "content": "welcome"}]},
        {"engine": "memory", "topic": "User prefers VS Code", "messages": [{"role": "user", "content": "I use VS Code"}]},
    ]
    brain_path.write_text(
        "\n".join(json.dumps(r) for r in records),
        encoding="utf-8",
    )
    return brain_path


class TestBrainInsight:
    def test_to_dict_roundtrip(self):
        ins = BrainInsight(
            id="test-1",
            topic="How to fix X",
            summary="Try Y then Z",
            source="skill",
            confidence=0.9,
            tags=["python", "debug"],
        )
        d = ins.to_dict()
        assert d["id"] == "test-1"
        assert d["confidence"] == 0.9

        ins2 = BrainInsight.from_dict(d)
        assert ins2.topic == "How to fix X"
        assert ins2.tags == ["python", "debug"]


class TestExtractInsights:
    def test_no_brain_file(self, isolate_home):
        insights = extract_insights_from_brain()
        assert insights == []

    def test_extracts_from_brain(self, brain_file):
        insights = extract_insights_from_brain(max_insights=10)
        assert len(insights) >= 2
        topics = [i.topic for i in insights]
        assert any("Debugging" in t for t in topics)
        assert any("Docker" in t for t in topics)

    def test_respects_max_insights(self, brain_file):
        insights = extract_insights_from_brain(max_insights=1)
        assert len(insights) == 1


class TestExportInsights:
    def test_export_insights(self, isolate_home):
        insights = [BrainInsight(id="t1", topic="test", summary="test summary", source="skill", confidence=0.5)]
        count = export_insights(insights)
        assert count == 1
        # Check file was written
        exported_files = list(isolate_home.glob("a2a/insights/*.json"))
        assert len(exported_files) == 1


class TestImportInsights:
    def test_import_insights(self, isolate_home):
        # Create a source file
        source = isolate_home / "source.json"
        data = {
            "insights": [
                {"id": "p1", "topic": "Remote topic", "summary": "Remote summary", "source": "skill", "confidence": 0.8},
            ]
        }
        source.write_text(json.dumps(data), encoding="utf-8")

        imported = import_insights(source)
        assert len(imported) == 1
        assert imported[0].topic == "Remote topic"

        # Check it was saved to imported dir
        imported_files = list(isolate_home.glob("a2a/imported/*.json"))
        assert len(imported_files) >= 1

    def test_import_nonexistent(self, isolate_home):
        imported = import_insights(isolate_home / "no-such-file.json")
        assert imported == []


class TestListImported:
    def test_list_imported(self, isolate_home):
        imported_dir = isolate_home / "a2a" / "imported"
        imported_dir.mkdir(parents=True, exist_ok=True)
        (imported_dir / "test.json").write_text(
            json.dumps({"imported_at": "2026-01-01T00:00:00", "count": 3, "insights": []}),
            encoding="utf-8",
        )
        listing = list_imported_insights()
        assert len(listing) == 1
        assert listing[0]["count"] == 3

    def test_list_imported_empty(self, isolate_home):
        assert list_imported_insights() == []


class TestStats:
    def test_get_brain_share_stats(self, brain_file):
        stats = get_brain_share_stats()
        assert stats["local_insights"] >= 2
        assert stats["exported_files"] == 0
        assert stats["imported_files"] == 0


class TestCLI:
    def test_cmd_brain_share_imports(self):
        assert callable(cmd_brain_share)
        assert callable(build_brain_share_parser)

    def test_build_parser(self):
        import argparse
        parser = argparse.ArgumentParser()
        sub = parser.add_subparsers()
        build_brain_share_parser(sub)
        assert "share" in sub.choices