"""Hermetic test for knowledge_inventory: retrieval over a small fake set."""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import knowledge_inventory as ki  # noqa: E402


def test_score_counts_terms():
    assert ki._score("mcp catalog server", ["mcp", "catalog"]) == 2
    assert ki._score("catalog", ["mcp"]) == 0


def test_inventory_counts(tmp_path, monkeypatch):
    # fake skills root
    root = tmp_path / "skills"
    (root / "dev" / "a").mkdir(parents=True)
    (root / "dev" / "b").mkdir(parents=True)
    (root / "dev" / "a" / "SKILL.md").write_text("---\nname: a\n---\nDesc A here.\n", encoding="utf-8")
    (root / "dev" / "b" / "SKILL.md").write_text("---\nname: b\n---\nOther.\n", encoding="utf-8")
    monkeypatch.setattr(ki, "SKILLS_ROOT", root)
    sk = ki._iter_skills()
    assert len(sk) == 2
    assert all(s["description"] for s in sk)  # description extracted


def test_find_surfaces_relevant(tmp_path, monkeypatch):
    root = tmp_path / "skills"
    (root / "mcp" / "mcp-catalog").mkdir(parents=True)
    (root / "mcp" / "mcp-catalog" / "SKILL.md").write_text(
        "---\nname: mcp-catalog\n---\nMCP server catalog discovery.\n", encoding="utf-8")
    monkeypatch.setattr(ki, "SKILLS_ROOT", root)
    out = ki.find("mcp catalog")
    assert "mcp-catalog" in out
    assert "skill" in out