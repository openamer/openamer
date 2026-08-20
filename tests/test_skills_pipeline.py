"""Tests for the Skills Pipeline."""

from __future__ import annotations

import tempfile
from pathlib import Path

from openamer_cli.skills_pipeline import analyze_skill, run_full_pipeline, get_stats


def _create_skill_dirs(base: Path, skills: list[tuple[str, str, str, bool]]) -> None:
    """Create fake skill directories with SKILL.md files.
    Each tuple: (category, name, content, include_frontmatter)
    """
    for cat, name, content, has_front in skills:
        cat_dir = base / "skills" / cat
        cat_dir.mkdir(parents=True, exist_ok=True)
        skill_dir = cat_dir / name
        skill_dir.mkdir(exist_ok=True)
        skill_file = skill_dir / "SKILL.md"
        if has_front:
            text = f"""---
name: {name}
description: A test skill
---

# {name}

{content}

## Steps

1. Do something
2. Verify it works

## Pitfalls

- Watch out for edge cases

## Verification

Run the command and check output
"""
        else:
            text = f"# {name}\n\n{content} (no frontmatter, no sections)"
        skill_file.write_text(text, encoding="utf-8")


def test_analyze_skill_found_good():
    """Analyze a well-formed skill."""
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        _create_skill_dirs(base, [("mlops", "test-skill", "Good content", True)])
        # Override skills dir
        import openamer_cli.skills_pipeline as sp
        original_home = sp._home
        sp._home = lambda: base
        try:
            result = sp.analyze_skill("test-skill")
            assert result["found"] is True
            assert result["has_frontmatter"] is True
            assert result["has_steps"] is True
            assert result["has_pitfalls"] is True
            assert result["has_verification"] is True
            assert result["quality_score"] >= 80
        finally:
            sp._home = original_home


def test_analyze_skill_not_found():
    """Analyze a nonexistent skill."""
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        _create_skill_dirs(base, [("mlops", "exists", "content", True)])
        import openamer_cli.skills_pipeline as sp
        original_home = sp._home
        sp._home = lambda: base
        try:
            result = sp.analyze_skill("nonexistent")
            assert result["found"] is False
        finally:
            sp._home = original_home


def test_analyze_skill_bad_quality():
    """Analyze a poorly structured skill — should flag issues."""
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        _create_skill_dirs(base, [("general", "bad-skill", "Minimal content", False)])
        import openamer_cli.skills_pipeline as sp
        original_home = sp._home
        sp._home = lambda: base
        try:
            result = sp.analyze_skill("bad-skill")
            assert result["found"] is True
            assert result["has_frontmatter"] is False
            assert result["has_steps"] is False
            assert result["has_pitfalls"] is False
            assert result["has_verification"] is False
            assert len(result["issues"]) >= 3
            assert result["quality_score"] <= 60
        finally:
            sp._home = original_home


def test_run_full_pipeline():
    """Full pipeline should find candidates needing improvement."""
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        _create_skill_dirs(base, [
            ("coding", "good-skill", "Great content", True),
            ("general", "bad-skill", "Bad content", False),
        ])
        import openamer_cli.skills_pipeline as sp
        original_home = sp._home
        sp._home = lambda: base
        try:
            result = sp.run_full_pipeline(min_score=50)
            assert result["total_skills"] == 2
            assert len(result["top_candidates"]) == 1  # only bad-skill is below 50
            assert result["top_candidates"][0]["name"] == "bad-skill"
        finally:
            sp._home = original_home


def test_get_stats():
    """Stats should return correct counts."""
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        _create_skill_dirs(base, [
            ("mlops", "s1", "content", True),
            ("devops", "s2", "content", True),
            ("general", "s3", "content", False),
        ])
        import openamer_cli.skills_pipeline as sp
        original_home = sp._home
        sp._home = lambda: base
        try:
            stats = sp.get_stats()
            assert stats["total_skills"] == 3
            assert "average_quality_score" in stats
        finally:
            sp._home = original_home