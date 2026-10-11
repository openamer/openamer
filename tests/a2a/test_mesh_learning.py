"""Tests for openamer_cli.a2a.mesh_learning — cross-node collective learning."""
import json
from pathlib import Path

import pytest

from openamer_cli.a2a import mesh_learning
from openamer_cli.a2a.core import IdentityStore
from openamer_cli.a2a.mesh_learning import MeshLearningCoordinator


@pytest.fixture(autouse=True)
def isolate_home(monkeypatch, tmp_path):
    """Point every path constant at a temp dir, so the coord is built from its
    defaults without touching the real OPENAMER_HOME."""
    for name in ("_MESH_DIR", "_LESSONS_DIR", "_PUBLISH_DIR", "_IMPORTED_DIR", "_INSIGHTS_DIR"):
        d = tmp_path / name.strip("_").lower()
        d.mkdir()
        # raising=False: on the pre-fix module a constant may not exist yet, and
        # the fixture failing would hide the bug the test is meant to report.
        monkeypatch.setattr(mesh_learning, name, d, raising=False)
    skills = tmp_path / "skills"
    skills.mkdir()
    monkeypatch.setattr(mesh_learning, "_MEMORY_PATH", tmp_path / "memory.md")
    monkeypatch.setattr(mesh_learning, "_SKILLS_DIR", skills)
    return tmp_path


def _coord(tmp_path):
    """A coordinator using the (patched) module defaults."""
    return MeshLearningCoordinator(identity_store=IdentityStore(tmp_path))


def _stage_insight(tmp_path, title="Wire the mesh cycle", **extra):
    """Write one locally staged insight, the shape MeshLearningCoordinator reads."""
    (mesh_learning._INSIGHTS_DIR / "cf971ad8-staged.json").write_text(
        json.dumps({"title": title, "body": "…", "topic": "mesh", **extra}),
        encoding="utf-8",
    )


class TestMeshLearningStats:
    def test_stats_reads_the_default_imported_dir(self, tmp_path):
        # Regression: stats read self._IMPORTED_DIR, which __init__ never set,
        # so any bare stats call raised AttributeError on the first run.
        (mesh_learning._IMPORTED_DIR / "peer.json").write_text(
            json.dumps({"topic": "general"}), encoding="utf-8"
        )
        stats = _coord(tmp_path).get_mesh_learning_stats()
        assert stats["lessons_imported"] == 1

    def test_imported_dir_defaults_to_module_constant(self, tmp_path):
        assert _coord(tmp_path)._imported_dir == mesh_learning._IMPORTED_DIR


class TestPublishLesson:
    def test_publish_lesson_signs_and_writes_the_lesson(self, tmp_path):
        # Regression: MeshLesson was constructed without its three required
        # fields (source/source_pubkey/ts), so `openamer a2a mesh publish`
        # raised TypeError before it ever reached the signing step.
        result = _coord(tmp_path).publish_lesson(
            {"title": "Wire the mesh cycle", "body": "…", "topic": "mesh"}
        )

        assert result["ok"] is True
        assert result["signed"] is True
        lesson = json.loads(Path(result["path"]).read_text(encoding="utf-8"))
        assert lesson["source"] == result["source"]
        assert lesson["source_pubkey"]
        assert lesson["ts"] > 0


class TestMeshLearningCycle:
    def test_cycle_runs_and_reports_the_cli_shape(self, tmp_path):
        # Regression: `openamer a2a mesh learn` called run_mesh_learning_cycle(),
        # which the coordinator never defined -> AttributeError inside _cmd_mesh.
        result = _coord(tmp_path).run_mesh_learning_cycle()

        assert set(result) == {"published", "imported", "applied"}
        assert all(isinstance(v, int) for v in result.values())

    def test_cycle_publishes_a_staged_insight_once(self, tmp_path):
        _stage_insight(tmp_path)
        coord = _coord(tmp_path)

        first = coord.run_mesh_learning_cycle()
        assert first["published"] == 1
        assert len(list(mesh_learning._PUBLISH_DIR.glob("*.json"))) == 1

        # Idempotent: the same staged insight is not published a second time.
        second = coord.run_mesh_learning_cycle()
        assert second["published"] == 0
        assert len(list(mesh_learning._PUBLISH_DIR.glob("*.json"))) == 1

    def test_published_lesson_is_signed_by_this_node(self, tmp_path):
        _stage_insight(tmp_path, title="Signed lesson")
        _coord(tmp_path).run_mesh_learning_cycle()

        lesson = json.loads(
            next(mesh_learning._PUBLISH_DIR.glob("*.json")).read_text(encoding="utf-8")
        )
        assert lesson["signature"]
        assert lesson["source_pubkey"]
        assert lesson["lesson_id"]
        assert lesson["topic"] == "mesh"

    def test_cycle_never_fans_a_lesson_out_over_every_skill(self, tmp_path):
        # apply_lesson_to_skills() falls back to *every* local skill when a
        # lesson names no target. The cycle must not do that to 100+ skills.
        skill = mesh_learning._SKILLS_DIR / "demo"
        skill.mkdir()
        (skill / "SKILL.md").write_text("# demo\n", encoding="utf-8")
        (mesh_learning._PUBLISH_DIR / "cf971ad8-peer-lesson.json").write_text(
            json.dumps(
                {
                    "lesson_id": "mesh-peer-1",
                    "title": "Untargeted peer lesson",
                    "body": "do this",
                    "topic": "general",
                    "ts": 1,
                }
            ),
            encoding="utf-8",
        )

        result = _coord(tmp_path).run_mesh_learning_cycle()

        assert result["imported"] == 1
        assert result["applied"] == 0
        assert (skill / "SKILL.md").read_text(encoding="utf-8") == "# demo\n"
