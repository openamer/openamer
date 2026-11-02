"""Bound filesystem work on the Desktop's synchronous skill-sync boot path."""
from pathlib import Path

from tools import skills_sync


def test_optional_backfill_scans_active_tree_once_per_pass(tmp_path, monkeypatch):
    active = tmp_path / "skills"
    optional = tmp_path / "optional"
    active.mkdir()
    for name in ("relocated", "missing-a", "missing-b"):
        source = optional / "new" / name
        source.mkdir(parents=True)
        (source / "SKILL.md").write_text(f"# {name}\n", encoding="utf-8")
    relocated = active / "old" / "relocated"
    relocated.mkdir(parents=True)
    (relocated / "SKILL.md").write_text("# relocated\n", encoding="utf-8")
    monkeypatch.setattr(skills_sync, "SKILLS_DIR", active)
    monkeypatch.setattr(skills_sync, "_get_optional_dir", lambda: optional)
    original = Path.rglob
    scans = []

    def counted_rglob(path, pattern):
        if path == active and pattern == "SKILL.md":
            scans.append(path)
        return original(path, pattern)

    monkeypatch.setattr(Path, "rglob", counted_rglob)
    assert skills_sync._backfill_optional_provenance(quiet=True) == ["relocated"]
    assert len(scans) == 1, "Missing optional skills must share one active-tree scan"

    # The index must be local to this pass: a newly installed skill is visible.
    added = active / "old" / "missing-a"
    added.mkdir()
    (added / "SKILL.md").write_text("# missing-a\n", encoding="utf-8")
    scans.clear()
    assert skills_sync._backfill_optional_provenance(quiet=True) == ["missing-a"]
    assert len(scans) == 1
