"""Tests for openamer_cli.a2a.mesh_learning — cross-node collective learning."""
import json

import pytest

from openamer_cli.a2a import mesh_learning
from openamer_cli.a2a.core import IdentityStore
from openamer_cli.a2a.mesh_learning import MeshLearningCoordinator


@pytest.fixture(autouse=True)
def isolate_home(monkeypatch, tmp_path):
    """Point every path constant at a temp dir, so the coord is built from its
    defaults without touching the real OPENAMER_HOME."""
    for name in ("_MESH_DIR", "_LESSONS_DIR", "_PUBLISH_DIR", "_IMPORTED_DIR"):
        d = tmp_path / name.strip("_").lower()
        d.mkdir()
        monkeypatch.setattr(mesh_learning, name, d)
    skills = tmp_path / "skills"
    skills.mkdir()
    monkeypatch.setattr(mesh_learning, "_MEMORY_PATH", tmp_path / "memory.md")
    monkeypatch.setattr(mesh_learning, "_SKILLS_DIR", skills)
    return tmp_path


def _coord(tmp_path):
    """A coordinator using the (patched) module defaults."""
    return MeshLearningCoordinator(identity_store=IdentityStore(tmp_path))


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
