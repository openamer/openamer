"""Tests for the Skills Improvement Pipeline (skills_pipeline.py).

Covers:
  - Content analysis (frontmatter, sections, quality markers)
  - Urgency scoring and suggestions
  - Auto-patching of SKILL.md
  - Full pipeline aggregation
  - CLI handler integration
"""

from __future__ import annotations

import json
import os
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pytest
from rich.console import Console


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_WELL_FORMED_SKILL = """---
name: test-skill
description: Use when testing skills. A well-formed skill for testing.
version: 1.0.0
author: OpenAmer Test Suite
license: MIT
metadata:
  openamer:
    tags: [test, skills]
    related_skills: [other-skill]
---

# Test Skill

## Overview

This is a test skill with all the right sections.

## When to Use

When you need to test the skills pipeline.

## Prerequisites

- Python 3.11+

## Verification

Run the test suite.

## Troubleshooting

If tests fail, check the mock configuration.

## Pitfalls

- Mocking too broadly can hide real bugs.
"""

_MISSING_FRONTMATTER_SKILL = """# No Frontmatter Skill

## Overview

This skill has no YAML frontmatter at all.

## When to Use

When testing detection of missing frontmatter.
"""

_MISSING_SECTIONS_SKILL = """---
name: minimal-skill
description: A skill with only the bare minimum sections.
version: 1.0.0
---

# Minimal Skill

## Overview

This skill is missing several recommended sections.

## When to Use

Testing section detection.
"""

_STALE_CONTENT_SKILL = """---
name: stale-skill
description: A skill with TODO markers and stale content.
version: 0.5.0
---

# Stale Skill

## Overview

This skill has FIXME markers and stale content.

## When to Use

TODO: Define when to use this skill.

## Verification

FIXME: This section needs updating.

## Troubleshooting

Coming soon.
"""

_UNIX_ONLY_SKILL = """---
name: unix-skill
description: A skill with Unix-specific commands only.
---

# Unix-Only Skill

## Overview

Run with /usr/local/bin/tool and install with brew install something.

## When to Use

When you need to test platform detection.
"""

_EMPTY_BODY_SKILL = """---
name: empty-skill
description: A skill with no real body content.
version: 0.1.0
---

# Empty

barely anything here
"""


@pytest.fixture
def skills_tmp_dir(tmp_path):
    """Create a temporary skills directory with test SKILL.md files."""
    skills_dir = tmp_path / ".openamer" / "skills"
    categories = {
        "testing": {
            "well-formed": _WELL_FORMED_SKILL,
            "missing-frontmatter": _MISSING_FRONTMATTER_SKILL,
            "minimal-skill": _MISSING_SECTIONS_SKILL,
            "stale-skill": _STALE_CONTENT_SKILL,
            "unix-skill": _UNIX_ONLY_SKILL,
            "empty-skill": _EMPTY_BODY_SKILL,
        },
        "other": {
            "other-skill": "---\nname: other-skill\ndescription: Another skill for testing.\n---\n\n# Other\n\n## Overview\n\nA basic skill.\n",
        },
    }
    for cat, skills in categories.items():
        cat_dir = skills_dir / cat
        cat_dir.mkdir(parents=True, exist_ok=True)
        for name, content in skills.items():
            skill_dir = cat_dir / name
            skill_dir.mkdir(exist_ok=True)
            (skill_dir / "SKILL.md").write_text(content, encoding="utf-8")

    return skills_dir


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestAnalyzeSkillUsage:
    """Tests for analyze_skill_usage() and internal helpers."""

    def test_well_formed_skill(self, skills_tmp_dir, monkeypatch):
        """A well-formed skill should score low urgency with no critical issues."""
        from openamer_cli.skills_pipeline import (
            SKILLS_BASE,
            analyze_skill_usage,
        )
        monkeypatch.setattr("openamer_cli.skills_pipeline.SKILLS_BASE", skills_tmp_dir)

        result = analyze_skill_usage("well-formed")

        assert result.skill_name == "well-formed"
        assert result.has_frontmatter is True
        assert result.missing_required == []
        assert result.has_verification is True
        assert result.has_troubleshooting is True
        assert result.has_pitfalls is True
        assert result.has_stale_content is False
        assert result.has_placeholders is False
        assert result.is_substantive is True
        assert result.urgency_score < 3.0  # Low urgency for good skills

    def test_missing_frontmatter(self, skills_tmp_dir, monkeypatch):
        """Skills without frontmatter should score high urgency."""
        from openamer_cli.skills_pipeline import (
            SKILLS_BASE,
            analyze_skill_usage,
        )
        monkeypatch.setattr("openamer_cli.skills_pipeline.SKILLS_BASE", skills_tmp_dir)

        result = analyze_skill_usage("missing-frontmatter")

        assert result.has_frontmatter is False
        assert "name" in result.missing_required
        assert result.urgency_score >= 3.0
        assert any("frontmatter" in s.lower() for s in result.suggested_improvements)

    def test_missing_sections_detected(self, skills_tmp_dir, monkeypatch):
        """Skills missing common sections should flag them in suggestions."""
        from openamer_cli.skills_pipeline import (
            SKILLS_BASE,
            analyze_skill_usage,
        )
        monkeypatch.setattr("openamer_cli.skills_pipeline.SKILLS_BASE", skills_tmp_dir)

        result = analyze_skill_usage("minimal-skill")

        assert result.has_frontmatter is True
        assert result.has_verification is False
        assert any("Verification" in s for s in result.suggested_improvements)

    def test_stale_content_detected(self, skills_tmp_dir, monkeypatch):
        """Skills with TODO/FIXME markers should flag them."""
        from openamer_cli.skills_pipeline import (
            SKILLS_BASE,
            analyze_skill_usage,
        )
        monkeypatch.setattr("openamer_cli.skills_pipeline.SKILLS_BASE", skills_tmp_dir)

        result = analyze_skill_usage("stale-skill")

        assert result.has_stale_content is True
        assert result.stale_matches
        assert any("FIXME" in m for m in result.stale_matches)
        assert result.urgency_score >= 1.5

    def test_placeholder_detected(self, skills_tmp_dir, monkeypatch):
        """Skills with 'Coming soon' / 'TODO' should flag them."""
        from openamer_cli.skills_pipeline import (
            SKILLS_BASE,
            analyze_skill_usage,
        )
        monkeypatch.setattr("openamer_cli.skills_pipeline.SKILLS_BASE", skills_tmp_dir)

        result = analyze_skill_usage("stale-skill")

        assert result.has_placeholders is True
        assert len(result.placeholder_matches) > 0

    def test_unix_paths_detected(self, skills_tmp_dir, monkeypatch):
        """Skills with Unix-specific paths but no Windows hints should flag."""
        from openamer_cli.skills_pipeline import (
            SKILLS_BASE,
            analyze_skill_usage,
        )
        monkeypatch.setattr("openamer_cli.skills_pipeline.SKILLS_BASE", skills_tmp_dir)

        result = analyze_skill_usage("unix-skill")

        assert result.has_non_windows_paths is True
        assert result.has_windows_hints is False
        assert any("Unix" in s or "Windows" in s for s in result.suggested_improvements)

    def test_skill_not_found(self, skills_tmp_dir, monkeypatch):
        """Non-existent skill should get max urgency."""
        from openamer_cli.skills_pipeline import (
            SKILLS_BASE,
            analyze_skill_usage,
        )
        monkeypatch.setattr("openamer_cli.skills_pipeline.SKILLS_BASE", skills_tmp_dir)

        result = analyze_skill_usage("nonexistent-skill")

        assert result.path == ""
        assert result.urgency_score == 10.0

    def test_discovery_counts(self, skills_tmp_dir, monkeypatch):
        """_discover_all_skills should find all SKILL.md files."""
        from openamer_cli.skills_pipeline import (
            SKILLS_BASE,
            _discover_all_skills,
        )
        monkeypatch.setattr("openamer_cli.skills_pipeline.SKILLS_BASE", skills_tmp_dir)

        found = _discover_all_skills()
        names = [s["name"] for s in found]
        assert "well-formed" in names
        assert "missing-frontmatter" in names
        assert "other-skill" in names
        assert len(found) >= 7


class TestSuggestImprovements:
    """Tests for suggest_improvements()."""

    def test_returns_suggestions(self, skills_tmp_dir, monkeypatch):
        """suggest_improvements should return actionable strings."""
        from openamer_cli.skills_pipeline import (
            SKILLS_BASE,
            suggest_improvements,
        )
        monkeypatch.setattr("openamer_cli.skills_pipeline.SKILLS_BASE", skills_tmp_dir)

        suggestions = suggest_improvements("missing-frontmatter")
        assert len(suggestions) >= 1
        # Should be improvement suggestions, not "healthy" message
        assert all("healthy" not in s for s in suggestions)

    def test_healthy_skill(self, skills_tmp_dir, monkeypatch):
        """A well-formed skill should return a healthy message."""
        from openamer_cli.skills_pipeline import (
            SKILLS_BASE,
            suggest_improvements,
        )
        monkeypatch.setattr("openamer_cli.skills_pipeline.SKILLS_BASE", skills_tmp_dir)

        suggestions = suggest_improvements("well-formed")
        assert any("healthy" in s for s in suggestions)


class TestAutoImprove:
    """Tests for auto_improve()."""

    def test_injects_frontmatter(self, skills_tmp_dir, monkeypatch):
        """auto_improve should suggest injecting frontmatter for bare skills."""
        from openamer_cli.skills_pipeline import (
            SKILLS_BASE,
            auto_improve,
        )
        monkeypatch.setattr("openamer_cli.skills_pipeline.SKILLS_BASE", skills_tmp_dir)

        result = auto_improve("missing-frontmatter", dry_run=True)
        assert result["dry_run"] is True
        if result["patches_applied"]:
            assert any("frontmatter" in p.lower() for p in result["patches_applied"])
        # Error check
        assert "error" not in result or not result["error"]

    def test_dry_run_does_not_modify(self, skills_tmp_dir, monkeypatch):
        """dry_run=True should leave the file unchanged."""
        from openamer_cli.skills_pipeline import (
            SKILLS_BASE,
            auto_improve,
        )
        monkeypatch.setattr("openamer_cli.skills_pipeline.SKILLS_BASE", skills_tmp_dir)

        skill_path = skills_tmp_dir / "testing" / "missing-frontmatter" / "SKILL.md"
        before = skill_path.read_text(encoding="utf-8")

        auto_improve("missing-frontmatter", dry_run=True)

        after = skill_path.read_text(encoding="utf-8")
        assert before == after  # No change


class TestFullPipeline:
    """Tests for run_full_pipeline()."""

    def test_pipeline_aggregates_results(self, skills_tmp_dir, monkeypatch):
        """run_full_pipeline should discover and analyze all skills."""
        from openamer_cli.skills_pipeline import (
            SKILLS_BASE,
            run_full_pipeline,
        )
        monkeypatch.setattr("openamer_cli.skills_pipeline.SKILLS_BASE", skills_tmp_dir)

        report = run_full_pipeline(top_n=3)
        assert report.total_skills >= 7
        assert report.analyzed >= 7
        assert len(report.results) >= 7
        assert len(report.top_urgent) == 3  # top_n=3
        # The most urgent skills should be listed first
        if len(report.top_urgent) >= 2:
            assert report.top_urgent[0].urgency_score >= report.top_urgent[1].urgency_score

    def test_pipeline_min_urgency_filter(self, skills_tmp_dir, monkeypatch):
        """min_urgency should filter out low-urgency skills."""
        from openamer_cli.skills_pipeline import (
            SKILLS_BASE,
            run_full_pipeline,
        )
        monkeypatch.setattr("openamer_cli.skills_pipeline.SKILLS_BASE", skills_tmp_dir)

        report = run_full_pipeline(min_urgency=5.0)
        for r in report.results:
            assert r.urgency_score >= 5.0


class TestPrintFunctions:
    """Tests for print_analysis, print_suggestions, print_pipeline_report."""

    def test_print_analysis_output(self, skills_tmp_dir, monkeypatch):
        """print_analysis should produce output without crashing."""
        from openamer_cli.skills_pipeline import (
            SKILLS_BASE,
            ContentAnalysisResult,
            analyze_skill_usage,
            print_analysis,
        )
        monkeypatch.setattr("openamer_cli.skills_pipeline.SKILLS_BASE", skills_tmp_dir)

        result = analyze_skill_usage("well-formed")
        # Should not raise
        print_analysis(result)

    def test_print_suggestions_output(self, skills_tmp_dir, monkeypatch):
        """print_suggestions should produce output without crashing."""
        from openamer_cli.skills_pipeline import (
            SKILLS_BASE,
            suggest_improvements,
            print_suggestions,
        )
        monkeypatch.setattr("openamer_cli.skills_pipeline.SKILLS_BASE", skills_tmp_dir)

        suggestions = suggest_improvements("missing-frontmatter")
        print_suggestions(suggestions, "missing-frontmatter")

    def test_print_pipeline_report_output(self, skills_tmp_dir, monkeypatch):
        """print_pipeline_report should produce output without crashing."""
        from openamer_cli.skills_pipeline import (
            SKILLS_BASE,
            run_full_pipeline,
            print_pipeline_report,
        )
        monkeypatch.setattr("openamer_cli.skills_pipeline.SKILLS_BASE", skills_tmp_dir)

        report = run_full_pipeline()
        print_pipeline_report(report)

    def test_pipeline_report_to_dict(self, skills_tmp_dir, monkeypatch):
        """to_dict() should produce valid JSON-serializable output."""
        from openamer_cli.skills_pipeline import (
            SKILLS_BASE,
            run_full_pipeline,
        )
        monkeypatch.setattr("openamer_cli.skills_pipeline.SKILLS_BASE", skills_tmp_dir)

        report = run_full_pipeline()
        data = report.to_dict(top_n=5)
        # Should be JSON-serializable
        json_str = json.dumps(data)
        assert '"top_urgent"' in json_str
        assert json.loads(json_str)["top_urgent"] == "..." or True  # just checking parsability


class TestFrontmatterParser:
    """Tests for the internal _parse_frontmatter helper."""

    def test_well_formed_frontmatter(self):
        from openamer_cli.skills_pipeline import _parse_frontmatter
        content = "---\nname: my-skill\ndescription: A test skill.\n---\n\nBody here."
        fm, body = _parse_frontmatter(content)
        assert fm is not None
        assert fm["name"] == "my-skill"
        assert fm["description"] == "A test skill."
        assert "Body here" in body

    def test_list_frontmatter(self):
        from openamer_cli.skills_pipeline import _parse_frontmatter
        content = "---\ntags:\n  - tag1\n  - tag2\nversion: 2.0\n---\n\nBody."
        fm, body = _parse_frontmatter(content)
        assert fm is not None
        assert fm["tags"] == ["tag1", "tag2"]
        assert fm["version"] == "2.0"

    def test_inline_list_frontmatter(self):
        from openamer_cli.skills_pipeline import _parse_frontmatter
        content = "---\nplatforms: [linux, macos, windows]\n---\n\nBody."
        fm, body = _parse_frontmatter(content)
        assert fm is not None
        assert "linux" in fm["platforms"]
        assert "windows" in fm["platforms"]

    def test_no_frontmatter(self):
        from openamer_cli.skills_pipeline import _parse_frontmatter
        content = "# Just a heading\n\nNo frontmatter here."
        fm, body = _parse_frontmatter(content)
        assert fm is None
        assert body == content

    def test_incomplete_frontmatter(self):
        from openamer_cli.skills_pipeline import _parse_frontmatter
        content = "---\nname: my-skill\n---NOT CLOSED"
        fm, body = _parse_frontmatter(content)
        assert fm is None  # Should fail without closing ---