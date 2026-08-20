"""
Skills Improvement Pipeline — automatische Skill-Analyse und Verbesserung.

Durchsucht alle installierten Skills, analysiert sie auf
Vollständigkeit, Aktualität und Nutzung, und verbessert
veraltete/lückenhafte Skills automatisch.
"""

from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

def _home() -> Path:
    return Path(os.environ.get("OPENAMER_HOME", Path.home() / ".openamer"))


def _skills_dir() -> Path:
    return _home() / "skills"


def _age_days(path: Path) -> float:
    if not path.exists():
        return float("inf")
    mtime = path.stat().st_mtime
    return (time.time() - mtime) / 86400.0


# ---------------------------------------------------------------------------
# Analyse
# ---------------------------------------------------------------------------


def analyze_skill(skill_name: str) -> dict[str, Any]:
    """Analysiert einen einzelnen Skill und gibt einen Report zurück."""
    skills_root = _skills_dir()
    # Suche in allen Unterverzeichnissen
    for sk, category in [(skills_root / c / skill_name / "SKILL.md", c)
                         for c in (d.name for d in skills_root.iterdir() if d.is_dir())]:
        pass  # will be populated below

    results: list[dict[str, Any]] = []
    for cat_dir in skills_root.iterdir():
        if not cat_dir.is_dir():
            continue
        skill_dir = cat_dir / skill_name
        skill_file = skill_dir / "SKILL.md"
        if skill_file.exists():
            return _analyze_one(skill_file, skill_name, cat_dir.name)

    # Alternative: durchsuche alle Skills
    for cat_dir in skills_root.iterdir():
        if not cat_dir.is_dir():
            continue
        for sdir in cat_dir.iterdir():
            if not sdir.is_dir():
                continue
            if sdir.name == skill_name:
                sf = sdir / "SKILL.md"
                if sf.exists():
                    return _analyze_one(sf, skill_name, cat_dir.name)

    return {"name": skill_name, "found": False, "error": f"Skill '{skill_name}' not found"}


def _analyze_one(skill_file: Path, name: str, category: str) -> dict[str, Any]:
    """Analysiere eine einzelne SKILL.md Datei."""
    content = skill_file.read_text(encoding="utf-8")
    lines = content.split("\n")
    age_days = _age_days(skill_file)

    # Checks
    has_frontmatter = content.startswith("---")
    has_description = "description:" in content[:500]
    has_steps = any("## " in l for l in lines)
    has_pitfalls = "pitfall" in content.lower() or "warn" in content.lower()
    has_verification = "verif" in content.lower() or "test" in content.lower()
    is_stale = age_days > 60

    issues: list[str] = []
    if not has_frontmatter:
        issues.append("Fehlendes YAML-Frontmatter")
    if not has_description:
        issues.append("Fehlende Beschreibung")
    if not has_steps:
        issues.append("Keine Ausführungsschritte (## Sections)")
    if not has_pitfalls:
        issues.append("Keine Pitfalls/Warnungen")
    if not has_verification:
        issues.append("Keine Verifikationsschritte")
    if is_stale:
        issues.append(f"Veraltet (zuletzt bearbeitet vor {int(age_days)} Tagen)")

    score = max(0, 100 - len(issues) * 16)
    return {
        "name": name,
        "category": category,
        "found": True,
        "age_days": round(age_days, 1),
        "size_bytes": len(content),
        "has_frontmatter": has_frontmatter,
        "has_description": has_description,
        "has_steps": has_steps,
        "has_pitfalls": has_pitfalls,
        "has_verification": has_verification,
        "is_stale": is_stale,
        "issues": issues,
        "quality_score": score,
    }


def run_full_pipeline(min_score: int = 60) -> dict[str, Any]:
    """Analysiert ALLE Skills und gibt die Top-Verbesserungskandidaten zurück."""
    skills_root = _skills_dir()
    if not skills_root.is_dir():
        return {"error": "Skills directory not found", "total": 0, "candidates": []}

    all_skills: list[dict[str, Any]] = []
    for cat_dir in skills_root.iterdir():
        if not cat_dir.is_dir():
            continue
        for sdir in cat_dir.iterdir():
            if not sdir.is_dir():
                continue
            skill_file = sdir / "SKILL.md"
            if not skill_file.exists():
                continue
            analysis = _analyze_one(skill_file, sdir.name, cat_dir.name)
            all_skills.append(analysis)

    # Sortieren nach Quality Score (niedrigste zuerst)
    all_skills.sort(key=lambda s: (s.get("quality_score", 100), s.get("age_days", 0)))

    candidates = [s for s in all_skills if s.get("quality_score", 100) < min_score]

    top_10 = candidates[:10]

    return {
        "total_skills": len(all_skills),
        "candidates_count": len(candidates),
        "top_candidates": top_10,
        "average_score": round(sum(s.get("quality_score", 0) for s in all_skills) / len(all_skills), 1) if all_skills else 0,
    }


def get_stats() -> dict[str, Any]:
    """Zeige Statistiken über alle Skills."""
    result = run_full_pipeline(min_score=0)
    return {
        "total_skills": result["total_skills"],
        "needs_improvement": result["candidates_count"],
        "average_quality_score": result["average_score"],
        "skills_analyzed_at": datetime.now(timezone.utc).isoformat(),
    }