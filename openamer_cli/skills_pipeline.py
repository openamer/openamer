"""
Skills Improvement Pipeline for OpenAmer.

Deep-content analysis of SKILL.md files that goes beyond usage stats:
  - Reads actual SKILL.md content and checks for quality markers
  - Detects missing sections, outdated commands, frontmatter issues
  - Scores and ranks skills by improvement urgency
  - Auto-patches SKILL.md files with non-destructive improvements

CLI integration via ``openamer skills analyze|suggest|improve|pipeline``.
"""

from __future__ import annotations

import os
import re
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from openamer_cli.skills_improver import SkillImprover, SkillUsageStore


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SKILLS_BASE = Path.home() / ".openamer" / "skills"

# Minimum quality markers every skill should have
REQUIRED_FRONTMATTER_KEYS = {"name", "description"}
RECOMMENDED_FRONTMATTER_KEYS = {"version", "author", "license", "metadata"}
RECOMMENDED_SECTIONS = {
    "## Overview": "Brief explanation of what the skill does",
    "## When to Use": "Triggers that should cause the agent to load this skill",
}
NICE_TO_HAVE_SECTIONS = {
    "## Prerequisites": "Preconditions before running the skill",
    "## Verification": "How to confirm success after running the skill",
    "## Troubleshooting": "Common failures and how to handle them",
    "## Pitfalls": "Known pitfalls to watch out for",
    "### Pitfalls": "Known pitfalls (subsection variant)",
}

# Patterns that suggest outdated / stale content
STALE_PATTERNS = re.compile(
    r"\{TODO\}|FIXME|HACK|deprecated\b|legacy\b|"
    r"\bsoon\b.*\bupdated?\b|need[s]?\s+update|"
    r"temporary\s+workaround|temp\s+fix",
    re.IGNORECASE,
)

# Windows paths — skills written on macOS/Linux often reference /usr/bin etc.
# Note: non-capturing groups (?: ... ) to avoid findall returning tuples
NON_WINDOWS_PATHS = re.compile(
    r"/usr/(?:local/)?bin/|/etc/|/var/|/opt/homebrew|"
    r"brew\s+install|apt-get|yum\s+install|dnf\s+install"
)

# Markers for incomplete sections
PLACEHOLDER_PATTERNS = re.compile(
    r"(TODO|FIXME|coming soon|placeholder|TBD|to\s+be\s+done|"
    r"add\s+more\s+details|fill\s+this\s+in|your\s+content\s+here)",
    re.IGNORECASE,
)

# Max description length enforced by the agent
MAX_DESCRIPTION_LENGTH = 1024
# First 57 chars of the description are shown in the system prompt index
DESCRIPTION_TRUNCATION_LIMIT = 57

# Minimum body length to be considered substantive
MIN_SUBSTANTIVE_BODY_CHARS = 200


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class ContentAnalysisResult:
    """Result of analyzing a single skill's SKILL.md content."""

    skill_name: str
    category: str = ""
    path: str = ""
    total_lines: int = 0
    total_chars: int = 0
    body_chars: int = 0

    # Frontmatter
    has_frontmatter: bool = False
    frontmatter_keys: List[str] = field(default_factory=list)
    missing_required: List[str] = field(default_factory=list)
    missing_recommended: List[str] = field(default_factory=list)
    description_length: int = 0
    description_truncated: bool = False

    # Structure
    found_sections: List[str] = field(default_factory=list)
    missing_common_sections: List[str] = field(default_factory=list)
    has_prerequisites: bool = False
    has_verification: bool = False
    has_troubleshooting: bool = False
    has_pitfalls: bool = False

    # Quality
    has_stale_content: bool = False
    stale_matches: List[str] = field(default_factory=list)
    has_placeholders: bool = False
    placeholder_matches: List[str] = field(default_factory=list)
    has_non_windows_paths: bool = False
    non_windows_paths: List[str] = field(default_factory=list)
    has_windows_hints: bool = False
    is_substantive: bool = False

    # Usage (from SkillImprover)
    usage_data: Dict[str, Any] = field(default_factory=dict)
    times_used: int = 0
    success_rate: float = 0.0
    avg_duration: float = 0.0

    # Composite
    urgency_score: float = 0.0  # 0.0 = perfect, 10.0 = needs urgent help
    suggested_improvements: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "skill_name": self.skill_name,
            "category": self.category,
            "path": self.path,
            "total_lines": self.total_lines,
            "total_chars": self.total_chars,
            "body_chars": self.body_chars,
            "has_frontmatter": self.has_frontmatter,
            "frontmatter_keys": self.frontmatter_keys,
            "missing_required": self.missing_required,
            "missing_recommended": self.missing_recommended,
            "description_length": self.description_length,
            "description_truncated": self.description_truncated,
            "found_sections": self.found_sections,
            "missing_common_sections": self.missing_common_sections,
            "has_prerequisites": self.has_prerequisites,
            "has_verification": self.has_verification,
            "has_troubleshooting": self.has_troubleshooting,
            "has_pitfalls": self.has_pitfalls,
            "has_stale_content": self.has_stale_content,
            "stale_matches": self.stale_matches,
            "has_placeholders": self.has_placeholders,
            "placeholder_matches": self.placeholder_matches,
            "has_non_windows_paths": self.has_non_windows_paths,
            "non_windows_paths": self.non_windows_paths,
            "has_windows_hints": self.has_windows_hints,
            "is_substantive": self.is_substantive,
            "usage_data": self.usage_data,
            "times_used": self.times_used,
            "success_rate": self.success_rate,
            "avg_duration": self.avg_duration,
            "urgency_score": self.urgency_score,
            "suggested_improvements": self.suggested_improvements,
        }


@dataclass
class PipelineReport:
    """Full pipeline output."""

    total_skills: int = 0
    analyzed: int = 0
    skipped: int = 0
    results: List[ContentAnalysisResult] = field(default_factory=list)
    top_urgent: List[ContentAnalysisResult] = field(default_factory=list)
    auto_fixes_applied: int = 0
    errors: List[str] = field(default_factory=list)
    duration_seconds: float = 0.0

    def to_dict(self, top_n: int = 10) -> dict:
        return {
            "total_skills": self.total_skills,
            "analyzed": self.analyzed,
            "skipped": self.skipped,
            "auto_fixes_applied": self.auto_fixes_applied,
            "duration_seconds": round(self.duration_seconds, 2),
            "errors": self.errors[:10],
            "top_urgent": [
                {
                    "skill_name": r.skill_name,
                    "category": r.category,
                    "urgency_score": r.urgency_score,
                    "times_used": r.times_used,
                    "success_rate": r.success_rate,
                    "top_issues": r.suggested_improvements[:5],
                }
                for r in self.top_urgent[:top_n]
            ],
        }


# ---------------------------------------------------------------------------
# Content analysis
# ---------------------------------------------------------------------------


def _discover_all_skills() -> List[dict]:
    """Discover all installed skill directories with SKILL.md files."""
    skills: List[dict] = []
    if not SKILLS_BASE.exists():
        return skills
    try:
        for entry in SKILLS_BASE.iterdir():
            if not entry.is_dir() or entry.name.startswith("."):
                continue
            category = entry.name
            for skill_dir in entry.iterdir():
                if not skill_dir.is_dir():
                    continue
                skill_md = skill_dir / "SKILL.md"
                if skill_md.exists():
                    skills.append({
                        "name": skill_dir.name,
                        "category": category,
                        "path": str(skill_md),
                    })
    except OSError:
        pass
    return skills


def _parse_frontmatter(content: str) -> Tuple[Optional[dict], str]:
    """Parse YAML-like frontmatter from SKILL.md content.

    Returns (frontmatter_dict, body_string). If frontmatter is missing or
    unparseable, returns (None, content).  Uses a simple line-based parser
    rather than importing a YAML library (avoiding a new dependency).
    """
    lines = content.split("\n")
    if not lines or lines[0].strip() != "---":
        return None, content

    # Find closing '---'
    end_idx = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end_idx = i
            break

    if end_idx is None:
        return None, content

    fm_lines = lines[1:end_idx]
    body = "\n".join(lines[end_idx + 1:])

    fm: Dict[str, Any] = {}
    current_key = None
    current_list = None
    list_indent = None

    for line in fm_lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        # Check for list continuation
        indent = len(line) - len(line.lstrip())
        if current_list is not None and stripped.startswith("- "):
            current_list.append(stripped[2:].strip())
            continue

        # If we were parsing a list and indentation dropped, close the list
        if current_list is not None and indent <= (list_indent or 0) and not stripped.startswith("- "):
            if current_key is not None:
                fm[current_key] = current_list
            current_list = None

        # Key: value
        if ":" in stripped and not stripped.startswith("- "):
            key, _, val = stripped.partition(":")
            key = key.strip()
            val = val.strip()

            # Store previous list if we had one
            if current_list is not None:
                fm[current_key] = current_list
                current_list = None

            current_key = key

            if val == "" or val.startswith("#"):
                # Could be a list below
                current_list = []
                list_indent = indent + 2
            elif val.lower() in ("true", "yes"):
                fm[key] = True
                current_list = None
            elif val.lower() in ("false", "no"):
                fm[key] = False
                current_list = None
            elif val.startswith("[") and val.endswith("]"):
                # Simple inline list: [a, b, c]
                items = [x.strip().strip("'\"") for x in val[1:-1].split(",")]
                fm[key] = items
                current_list = None
            else:
                # Remove surrounding quotes
                val = val.strip("\"'")
                fm[key] = val
                current_list = None

    # Flush the last list
    if current_list is not None and current_key is not None:
        fm[current_key] = current_list

    return fm, body


def _extract_sections(body: str) -> List[str]:
    """Extract markdown section headings (## or ###) from the body."""
    return re.findall(r"^(#{2,3})\s+(.+)$", body, re.MULTILINE)


def analyze_skill_usage(skill_name: str) -> ContentAnalysisResult:
    """Analyze a single skill: content + usage stats.

    Checks:
      - SKILL.md frontmatter completeness
      - Section coverage
      - Stale / placeholder content markers
      - Platform-specific path assumptions
      - Usage statistics (frequency, success rate, duration)

    Args:
        skill_name: The skill name (directory name under skills/).

    Returns:
        ContentAnalysisResult with all findings.
    """
    # --- Find the skill on disk ---
    skill_md_path = _find_skill_file(skill_name)

    result = ContentAnalysisResult(skill_name=skill_name)

    if not skill_md_path:
        result.suggested_improvements.append(
            f"Skill '{skill_name}' not found anywhere under {SKILLS_BASE}."
        )
        result.urgency_score = 10.0
        return result

    result.path = str(skill_md_path)
    result.category = skill_md_path.parent.parent.name

    # --- Read content ---
    try:
        raw = skill_md_path.read_text(encoding="utf-8")
        lines = raw.split("\n")
        result.total_lines = len(lines)
        result.total_chars = len(raw)
    except (OSError, UnicodeDecodeError) as e:
        result.suggested_improvements.append(f"Cannot read SKILL.md: {e}")
        result.urgency_score = 10.0
        return result

    # --- Parse frontmatter ---
    fm, body = _parse_frontmatter(raw)
    result.body_chars = len(body.strip())

    if fm is not None:
        result.has_frontmatter = True
        result.frontmatter_keys = list(fm.keys())

        # Check required keys
        for key in REQUIRED_FRONTMATTER_KEYS:
            if key not in fm:
                result.missing_required.append(key)

        # Check recommended keys
        for key in RECOMMENDED_FRONTMATTER_KEYS:
            if key not in fm:
                result.missing_recommended.append(key)

        # Check description length
        desc = fm.get("description", "")
        result.description_length = len(desc)
        if len(desc) > MAX_DESCRIPTION_LENGTH:
            result.description_truncated = False  # will be rejected on load
        elif len(desc) > 0:
            # Simulate truncation for system prompt display
            truncated_display = desc[:DESCRIPTION_TRUNCATION_LIMIT]
            if len(desc) > DESCRIPTION_TRUNCATION_LIMIT:
                # Check if the important trigger phrase is preserved
                pass  # qualitative judgment done in _generate_suggestions
    else:
        result.missing_required = list(REQUIRED_FRONTMATTER_KEYS)
        result.missing_recommended = list(RECOMMENDED_FRONTMATTER_KEYS)

    # --- Section analysis ---
    all_sections = _extract_sections(body)
    result.found_sections = [
        f"{marker} {title}" for marker, title in all_sections
    ]
    section_headings = {f"## {t}" for _, t in all_sections}

    for section, _purpose in RECOMMENDED_SECTIONS.items():
        if section not in section_headings:
            result.missing_common_sections.append(section)

    result.has_prerequisites = "## Prerequisites" in section_headings
    result.has_verification = "## Verification" in section_headings
    result.has_troubleshooting = "## Troubleshooting" in section_headings
    result.has_pitfalls = (
        "## Pitfalls" in section_headings or "### Pitfalls" in section_headings
    )

    # --- Substance check ---
    result.is_substantive = result.body_chars >= MIN_SUBSTANTIVE_BODY_CHARS

    # --- Stale content ---
    stale_matches = STALE_PATTERNS.findall(body)
    if stale_matches:
        result.has_stale_content = True
        result.stale_matches = list(set(m.strip() for m in stale_matches))

    # --- Placeholder patterns ---
    placeholder_matches = PLACEHOLDER_PATTERNS.findall(body)
    if placeholder_matches:
        result.has_placeholders = True
        result.placeholder_matches = list(set(m.strip() for m in placeholder_matches))

    # --- Non-Windows paths ---
    path_matches = NON_WINDOWS_PATHS.findall(body)
    if path_matches:
        result.has_non_windows_paths = True
        result.non_windows_paths = list(set(m.strip() for m in path_matches))

    # --- Windows hints ---
    result.has_windows_hints = bool(
        re.search(r"windows|win32|powershell|cmd\.exe|\.exe\b|%USERPROFILE%", body, re.IGNORECASE)
    )

    # --- Usage data from SkillImprover ---
    try:
        store = SkillUsageStore()
        improver = SkillImprover(store)
        usage = improver.get_skill_stats(skill_name)
        if usage:
            result.usage_data = usage
            result.times_used = usage.get("times_used", 0)
            result.success_rate = usage.get("success_rate", 0.0)
            result.avg_duration = usage.get("avg_duration", 0.0)
    except Exception:
        pass  # Usage store may not exist yet

    # --- Generate urgency score and suggestions ---
    _score_and_suggest(result)

    return result


def _find_skill_file(skill_name: str) -> Optional[Path]:
    """Find SKILL.md for a skill by name, searching all categories."""
    if not SKILLS_BASE.exists():
        return None
    # Direct category/skill match
    for entry in SKILLS_BASE.iterdir():
        if not entry.is_dir() or entry.name.startswith("."):
            continue
        skill_dir = entry / skill_name
        if skill_dir.is_dir():
            candidate = skill_dir / "SKILL.md"
            if candidate.exists():
                return candidate
    return None


def _score_and_suggest(result: ContentAnalysisResult) -> None:
    """Compute urgency score and populate suggested_improvements."""
    suggestions: List[str] = []
    score = 0.0

    # --- Frontmatter issues (weight: high) ---
    if not result.has_frontmatter:
        score += 3.0
        suggestions.append(
            "Missing YAML frontmatter (`---` block at the top of SKILL.md). "
            "Required fields: name, description."
        )
    else:
        for key in result.missing_required:
            score += 2.0
            suggestions.append(f"Missing required frontmatter key: `{key}`.")
        for key in result.missing_recommended:
            score += 0.5
            suggestions.append(
                f"Missing recommended frontmatter key: `{key}` "
                f"(adds discoverability and provenance)."
            )

    # Check description
    if result.description_length == 0 and result.has_frontmatter:
        score += 1.0
        suggestions.append("Frontmatter `description:` is empty.")
    elif result.description_length > MAX_DESCRIPTION_LENGTH:
        score += 0.5
        suggestions.append(
            f"Description is {result.description_length} chars "
            f"(max {MAX_DESCRIPTION_LENGTH}). It will be rejected on skill load."
        )
    elif result.description_length > DESCRIPTION_TRUNCATION_LIMIT:
        # Check if the first 57 chars contain a trigger phrase
        pass  # Non-blocking hint

    # --- Missing sections (weight: medium) ---
    for section in result.missing_common_sections:
        score += 0.5
        section_short = section.replace("## ", "").replace("### ", "")
        suggestions.append(
            f"Missing `{section_short}` section — helps the agent "
            f"understand when and how to use this skill."
        )

    if not result.has_verification:
        score += 0.5
        suggestions.append(
            "Missing `## Verification` section — agents need a way to "
            "confirm the skill completed successfully."
        )

    if not result.has_pitfalls:
        score += 0.3
        suggestions.append(
            "Consider adding a `## Pitfalls` section documenting known issues."
        )

    # --- Stale / placeholder content (weight: high) ---
    if result.has_stale_content:
        score += 1.5
        suggestions.append(
            f"Contains stale markers: {', '.join(result.stale_matches[:5])}. "
            f"Review and clean up."
        )

    if result.has_placeholders:
        score += 1.0
        suggestions.append(
            f"Contains placeholder text: {', '.join(result.placeholder_matches[:5])}. "
            f"Replace with actual content."
        )

    # --- Platform assumptions (weight: medium) ---
    if result.has_non_windows_paths and not result.has_windows_hints:
        score += 0.8
        suggestions.append(
            "Contains Unix-specific paths/commands but no Windows alternative. "
            "Add a `## Windows` or `## Cross-Platform` section with "
            "Windows-equivalent commands."
        )

    # --- Substance (weight: low) ---
    if not result.is_substantive and result.has_frontmatter:
        score += 0.5
        suggestions.append(
            f"Body is only {result.body_chars} chars (minimum {MIN_SUBSTANTIVE_BODY_CHARS} "
            f"recommended for a useful skill). Expand the content."
        )

    # --- Usage-based signals (weight: low-to-medium) ---
    if result.times_used >= 3 and result.success_rate < 0.5:
        score += 1.0
        suggestions.append(
            f"Low success rate ({result.success_rate:.0%} after "
            f"{result.times_used} uses). Instructions may be unclear or outdated."
        )

    if result.times_used == 0 and result.is_substantive:
        # Good content but never used — might have poor trigger description
        score += 0.3
        desc_preview = result.usage_data.get("description", "")
        if desc_preview and len(desc_preview) > 60:
            pass  # Can't easily check trigger quality without the description text
    elif result.times_used == 0:
        score += 0.2  # Slight bump for never-used skills

    if result.avg_duration > 30 and result.times_used >= 3:
        score += 0.5
        suggestions.append(
            f"Slow average execution ({result.avg_duration:.1f}s). "
            f"Consider optimization or caching."
        )

    # Cap and round
    result.urgency_score = round(min(score, 10.0), 1)
    result.suggested_improvements = suggestions


# ---------------------------------------------------------------------------
# Suggest improvements
# ---------------------------------------------------------------------------


def suggest_improvements(skill_name: str) -> List[str]:
    """Get human-readable improvement suggestions for a skill.

    Args:
        skill_name: Name of the skill to analyze.

    Returns:
        List of suggestion strings.
    """
    result = analyze_skill_usage(skill_name)
    if not result.suggested_improvements:
        return [f"✓ '{skill_name}' looks healthy — no improvements needed."]
    return result.suggested_improvements


# ---------------------------------------------------------------------------
# Auto-improve (patch SKILL.md with non-destructive fixes)
# ---------------------------------------------------------------------------


def _generate_frontmatter_patch(
    content: str, result: ContentAnalysisResult
) -> Optional[Tuple[str, str, str]]:
    """Generate a patch that adds missing frontmatter.

    Returns (old_string, new_string, description) or None if no patch possible.
    """
    lines = content.split("\n")
    if not result.has_frontmatter:
        # No frontmatter at all — inject one at the top
        name = result.skill_name
        new_fm = (
            f"---\n"
            f"name: {name}\n"
            f"description: \"TODO: Describe when to use this skill.\"\n"
            f"version: 1.0.0\n"
            f"author: OpenAmer Agent\n"
            f"license: MIT\n"
            f"---\n"
        )
        # Find first non-empty line
        first_content = 0
        for i, line in enumerate(lines):
            if line.strip():
                first_content = i
                break
        old = "\n".join(lines[first_content:first_content + 1]) if first_content < len(lines) else ""
        new = new_fm + old
        return (old, new, "Inject missing YAML frontmatter")

    # Check for missing required fields
    for key in result.missing_required:
        return (None, None, None)  # Can't auto-fix missing required fields without values

    return None


def _generate_section_patch(
    content: str, result: ContentAnalysisResult
) -> Optional[Tuple[str, str, str]]:
    """Generate a patch that adds common missing sections at the end."""
    missing = [s for s in result.missing_common_sections if s in RECOMMENDED_SECTIONS]
    if not missing:
        return None

    to_add = []
    for section in missing:
        purpose = RECOMMENDED_SECTIONS.get(section, "")
        to_add.append(f"\n\n{section}\n\n{purpose}")
    if not to_add:
        return None

    # Append to the end of the body (before trailing whitespace)
    body_end = content.rstrip()
    old = body_end
    new = body_end + "".join(to_add) + "\n"
    desc = "Add missing section" + ("s" if len(missing) > 1 else "") + \
        f": {', '.join(m.replace('## ', '').replace('### ', '') for m in missing)}"
    return (old, new, desc)


_PATCHABLE_MISSING = {
    "## Verification",
    "## Troubleshooting",
    "## Pitfalls",
    "### Pitfalls",
}


def auto_improve(skill_name: str, dry_run: bool = True) -> Dict[str, Any]:
    """Apply non-destructive improvements to a skill's SKILL.md.

    Auto-fixes include:
      - Injecting missing YAML frontmatter (if entirely absent)
      - Adding missing common sections (Verification, Troubleshooting)
      - Replacing obvious placeholder text markers

    Args:
        skill_name: Skill to improve.
        dry_run: If True, shows what would change without modifying the file.

    Returns:
        Dict with keys:
          - skill_name
          - patches_applied: list of descriptions
          - dry_run: bool
          - analysis: analysis result dict
    """
    result = analyze_skill_usage(skill_name)
    patches_applied: List[str] = []

    if not result.path:
        return {
            "skill_name": skill_name,
            "patches_applied": [],
            "dry_run": dry_run,
            "error": "Skill not found on disk",
            "analysis": result.to_dict(),
        }

    try:
        original = Path(result.path).read_text(encoding="utf-8")
    except OSError as e:
        return {
            "skill_name": skill_name,
            "patches_applied": [],
            "dry_run": dry_run,
            "error": str(e),
            "analysis": result.to_dict(),
        }

    modified = original
    patches: List[Tuple[str, str, str]] = []  # (old, new, desc)

    # 1. Frontmatter injection (only if entirely missing)
    if not result.has_frontmatter:
        patch = _generate_frontmatter_patch(modified, result)
        if patch:
            patches.append(patch)

    # 2. Add missing sections
    for section in RECOMMENDED_SECTIONS:
        if section in result.missing_common_sections:
            purpose = RECOMMENDED_SECTIONS[section]
            # Append at the end of the content
            append_text = f"\n\n{section}\n\n_TODO: {purpose}_\n"
            patches.append(
                (modified.rstrip(), modified.rstrip() + append_text,
                 f"Add `{section}` section")
            )
            break  # Only add one section per run to keep diffs manageable

    if not patches and not result.has_placeholders:
        return {
            "skill_name": skill_name,
            "patches_applied": [],
            "dry_run": dry_run,
            "message": "No auto-fixable issues found.",
            "analysis": result.to_dict(),
        }

    # Apply placeholder replacement (non-destructive — replaces 'TODO' in body,
    # not in frontmatter)
    if result.has_placeholders and modified:
        for placeholder in list(set(result.placeholder_matches)):
            # Only replace in body, not frontmatter
            if "---" in modified:
                parts = modified.split("---", 2)
                if len(parts) >= 3:
                    # parts[0] = empty or leading content
                    # parts[1] = frontmatter
                    # parts[2] = body
                    body_section = parts[2]
                    count_body = body_section.count(placeholder)
                    if count_body > 0 and count_body <= 3:
                        new_body = body_section.replace(
                            placeholder, f"`{placeholder}` — needs review",
                            1
                        )
                        if new_body != body_section:
                            old_body = body_section
                            new_body = body_section.replace(
                                placeholder,
                                f"`{placeholder}`",
                                1,
                            )
                            desc = f"Flagged placeholder '{placeholder}' with backticks"
                            patches.append(
                                (parts[0] + "---" + parts[1] + "---" + old_body,
                                 parts[0] + "---" + parts[1] + "---" + new_body,
                                 desc)
                            )
                            modified = parts[0] + "---" + parts[1] + "---" + new_body
                            break  # One placeholder fix per run

    if not patches:
        return {
            "skill_name": skill_name,
            "patches_applied": [],
            "dry_run": dry_run,
            "message": "No auto-fixable issues found.",
            "analysis": result.to_dict(),
        }

    # Write patches (only last one, cumulative)
    if not dry_run:
        try:
            Path(result.path).write_text(patches[-1][1], encoding="utf-8")
        except OSError as e:
            return {
                "skill_name": skill_name,
                "patches_applied": [],
                "dry_run": dry_run,
                "error": str(e),
                "analysis": result.to_dict(),
            }

    patches_applied = [p[2] for p in patches]

    return {
        "skill_name": skill_name,
        "patches_applied": patches_applied,
        "dry_run": dry_run,
        "message": f"Would apply {len(patches)} patch(es)" if dry_run
        else f"Applied {len(patches)} patch(es)",
        "analysis": result.to_dict(),
    }


# ---------------------------------------------------------------------------
# Full pipeline — analyze ALL skills
# ---------------------------------------------------------------------------


def run_full_pipeline(
    top_n: int = 10,
    min_urgency: float = 0.0,
    skip_errors: bool = True,
) -> PipelineReport:
    """Analyze every installed skill and identify the most urgent improvements.

    Args:
        top_n: Number of skills to include in the urgent list (default 10).
        min_urgency: Minimum urgency score to include (default 0.0 = all).
        skip_errors: If True, skip skills that can't be read instead of
                     including them with max urgency.

    Returns:
        PipelineReport with full results.
    """
    start = time.time()
    report = PipelineReport()

    all_skills = _discover_all_skills()
    report.total_skills = len(all_skills)

    for skill in all_skills:
        try:
            result = analyze_skill_usage(skill["name"])
            if result.path:
                report.analyzed += 1
                report.results.append(result)
            else:
                if not skip_errors:
                    result.urgency_score = 10.0
                    report.results.append(result)
                report.skipped += 1
        except Exception as e:
            report.errors.append(f"{skill['name']}: {e}")
            report.skipped += 1

    # Sort by urgency (descending), filter by minimum
    report.results.sort(key=lambda r: -r.urgency_score)
    if min_urgency > 0:
        report.results = [r for r in report.results if r.urgency_score >= min_urgency]

    # Top N urgent skills
    report.top_urgent = report.results[:top_n]

    report.duration_seconds = round(time.time() - start, 2)
    return report


# ---------------------------------------------------------------------------
# Convenience: get content analysis for a skill by name
# ---------------------------------------------------------------------------


def get_analysis(skill_name: str) -> dict:
    """Get a full structured analysis dict for a skill.

    This is the main entry point used by CLI handlers.
    """
    result = analyze_skill_usage(skill_name)
    return result.to_dict()


# ---------------------------------------------------------------------------
# CLI handler helpers
# ---------------------------------------------------------------------------

def print_analysis(result: ContentAnalysisResult) -> None:
    """Pretty-print an analysis result to stdout."""
    print(f"\n{'=' * 60}")
    print(f"  🔍  Skill Analysis: {result.skill_name}")
    print(f"  {'─' * 50}")
    print(f"  Category:      {result.category or '(uncategorized)'}")
    print(f"  Path:          {result.path or '(not found)'}")
    print(f"  Lines:         {result.total_lines}  (chars: {result.total_chars})")
    print(f"  Body chars:    {result.body_chars}")
    print(f"  Urgency:       {result.urgency_score}/10")

    print(f"\n  {'📋 Frontmatter':─^50}")
    if result.has_frontmatter:
        print(f"    ✓ Present  ({len(result.frontmatter_keys)} keys)")
        if result.missing_required:
            print(f"    ✗ Missing required: {', '.join(result.missing_required)}")
        if result.missing_recommended:
            print(f"    ⚠ Missing recommended: {', '.join(result.missing_recommended)}")
        desc = ""
        if result.description_length > MAX_DESCRIPTION_LENGTH:
            desc = f" (OVER LIMIT: {result.description_length}/{MAX_DESCRIPTION_LENGTH})"
        elif result.description_length > 0:
            desc = f" ({result.description_length} chars)"
        print(f"    Description:{desc}")
    else:
        print(f"    ✗ Missing entirely")

    print(f"\n  {'📐 Structure':─^50}")
    if result.found_sections:
        shown = result.found_sections[:6]
        for s in shown:
            print(f"    • {s}")
        if len(result.found_sections) > 6:
            print(f"    ... and {len(result.found_sections) - 6} more")
    if result.missing_common_sections:
        for s in result.missing_common_sections:
            print(f"    ✗ Missing: {s}")

    print(f"\n  {'⚡ Quality':─^50}")
    if result.has_stale_content:
        print(f"    ⚠ Stale markers: {', '.join(result.stale_matches[:5])}")
    if result.has_placeholders:
        print(f"    ⚠ Placeholders: {', '.join(result.placeholder_matches[:5])}")
    if result.has_non_windows_paths:
        print(f"    ⚠ Unix-specific paths (no Windows alt): "
              f"{', '.join(result.non_windows_paths[:5])}")
    print(f"    Substance:     {'✓' if result.is_substantive else '✗'} "
          f"({result.body_chars} chars)")

    print(f"\n  {'📊 Usage':─^50}")
    print(f"    Times used:    {result.times_used}")
    print(f"    Success rate:  {result.success_rate:.0%}")
    print(f"    Avg duration:  {result.avg_duration:.1f}s")

    if result.suggested_improvements:
        print(f"\n  {'💡 Suggestions':─^50}")
        for s in result.suggested_improvements:
            print(f"    • {s}")
    else:
        print(f"\n  ✓  No improvements needed.")

    print(f"{'=' * 60}\n")


def print_suggestions(suggestions: List[str], skill_name: str) -> None:
    """Pretty-print suggestions."""
    print(f"\n📈  Improvement suggestions for [bold]{skill_name}[/]:")
    if not suggestions or suggestions == [f"✓ '{skill_name}' looks healthy — no improvements needed."]:
        print(f"  ✓ '{skill_name}' looks healthy — no improvements needed.")
        print()
        return
    for s in suggestions:
        print(f"  • {s}")
    print()


def print_pipeline_report(report: PipelineReport) -> None:
    """Pretty-print a pipeline run report."""
    print(f"\n{'=' * 60}")
    print(f"  🏭  Skills Improvement Pipeline Report")
    print(f"  {'─' * 50}")
    print(f"  Total skills found:  {report.total_skills}")
    print(f"  Analyzed:            {report.analyzed}")
    print(f"  Skipped:             {report.skipped}")
    print(f"  Auto-fixes applied:  {report.auto_fixes_applied}")
    print(f"  Duration:            {report.duration_seconds:.2f}s")
    print()

    if report.errors:
        print(f"  ⚠  Errors ({len(report.errors)}):")
        for err in report.errors[:5]:
            print(f"    • {err}")
        if len(report.errors) > 5:
            print(f"    ... and {len(report.errors) - 5} more")
        print()

    if report.top_urgent:
        print(f"  {'🔥 Top 10 Skills Needing Improvement':─^50}")
        print(f"  {'#':<4} {'Skill':<30} {'Category':<20} {'Urgency':<8} {'Uses':<6} {'Rate':<6}")
        print(f"  {'─' * 74}")
        for i, r in enumerate(report.top_urgent, 1):
            rate_str = f"{r.success_rate:.0%}" if r.success_rate else "-"
            print(f"  {i:<4} {r.skill_name:<30} {r.category:<20} "
                  f"{r.urgency_score:<8.1f} {r.times_used:<6} {rate_str:<6}")
        print()
        for i, r in enumerate(report.top_urgent, 1):
            if r.suggested_improvements:
                top = r.suggested_improvements[0]
                print(f"  {i}. {r.skill_name}: {top[:100]}")
        print()
    else:
        print(f"  ✓ No skills need improvement (all scored {min_urgency:.1f}+).")
        print()

    print(f"{'=' * 60}\n")