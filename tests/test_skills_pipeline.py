"""Tests for the Skills Pipeline — adapted for current API (2026-08)."""

from __future__ import annotations

import tempfile
from pathlib import Path

from openamer_cli.skills_pipeline import get_analysis, run_full_pipeline


def _create_skill_dirs(base: Path, skills: list[tuple[str, str, str, bool]]) -> Path:
    """Create fake skill directories with SKILL.md files.
    Each tuple: (category, name, content, include_frontmatter)
    Returns the skills base path.
    """
    skills_base = base / "skills"
    for cat, name, content, has_front in skills:
        cat_dir = skills_base / cat
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
    return skills_base


def test_get_analysis_found_good():
    """Analyze a well-formed skill."""
    import openamer_cli.skills_pipeline as sp

    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        skills_base = _create_skill_dirs(base, [("mlops", "test-skill", "Good content " * 50, True)])
        original = sp.SKILLS_BASE
        sp.SKILLS_BASE = skills_base
        try:
            result = sp.get_analysis("test-skill")
            assert result["has_frontmatter"] is True
            assert result["has_verification"] is True
            assert result["has_pitfalls"] is True
            assert result["is_substantive"] is True
            assert result["missing_required"] == []
            assert result["urgency_score"] < 5.0  # good skill = low urgency
        finally:
            sp.SKILLS_BASE = original


def test_get_analysis_not_found():
    """Analyze a nonexistent skill."""
    import openamer_cli.skills_pipeline as sp

    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        skills_base = _create_skill_dirs(base, [("mlops", "exists", "content", True)])
        original = sp.SKILLS_BASE
        sp.SKILLS_BASE = skills_base
        try:
            result = sp.get_analysis("nonexistent")
            assert result["skill_name"] == "nonexistent"
            assert result["path"] == ""
            assert result["urgency_score"] == 10.0  # not found = max urgency
        finally:
            sp.SKILLS_BASE = original


def test_get_analysis_bad_quality():
    """Analyze a poorly structured skill — should flag issues."""
    import openamer_cli.skills_pipeline as sp

    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        skills_base = _create_skill_dirs(base, [("general", "bad-skill", "Minimal content", False)])
        original = sp.SKILLS_BASE
        sp.SKILLS_BASE = skills_base
        try:
            result = sp.get_analysis("bad-skill")
            assert result["has_frontmatter"] is False
            assert result["has_verification"] is False
            assert result["has_pitfalls"] is False
            assert len(result["missing_required"]) > 0
            assert len(result["missing_common_sections"]) > 0
            assert result["urgency_score"] >= 5.0  # poor quality = high urgency
        finally:
            sp.SKILLS_BASE = original


def test_run_full_pipeline():
    """Full pipeline should find candidates needing improvement."""
    import openamer_cli.skills_pipeline as sp

    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        skills_base = _create_skill_dirs(base, [
            ("coding", "good-skill", "Great content", True),
            ("general", "bad-skill", "Bad content", False),
        ])
        original = sp.SKILLS_BASE
        sp.SKILLS_BASE = skills_base
        try:
            report = sp.run_full_pipeline(min_urgency=0.0, skip_errors=True)
            result = report.to_dict()
            assert result["total_skills"] == 2
            assert result["analyzed"] == 2
            assert len(result["top_urgent"]) == 2
            # bad-skill should have higher urgency than good-skill
            bad = [r for r in result["top_urgent"] if r["skill_name"] == "bad-skill"]
            good = [r for r in result["top_urgent"] if r["skill_name"] == "good-skill"]
            assert len(bad) == 1
            assert len(good) == 1
            assert bad[0]["urgency_score"] > good[0]["urgency_score"]
        finally:
            sp.SKILLS_BASE = original


def test_get_stats():
    """Stats via pipeline should return correct counts."""
    import openamer_cli.skills_pipeline as sp

    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        skills_base = _create_skill_dirs(base, [
            ("mlops", "s1", "content", True),
            ("devops", "s2", "content", True),
            ("general", "s3", "content", False),
        ])
        original = sp.SKILLS_BASE
        sp.SKILLS_BASE = skills_base
        try:
            report = sp.run_full_pipeline(min_urgency=0.0, skip_errors=True)
            result = report.to_dict()
            assert result["total_skills"] == 3
            assert result["analyzed"] == 3
            # s3 has no frontmatter — should have highest urgency
            s3 = [r for r in result["top_urgent"] if r["skill_name"] == "s3"]
            assert len(s3) == 1
            assert s3[0]["urgency_score"] > 0
        finally:
            sp.SKILLS_BASE = original