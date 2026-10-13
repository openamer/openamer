"""openamer_cli.a2a.self_improve — autonomous self-improvement engine.

Phase 8. After collecting mesh lessons and session data, the agent can analyse
its own behaviour, suggest improvements, and apply them — closing the loop on
self-directed growth.

Capabilities provided:
  - SelfImprovementEngine: full self-improvement lifecycle
  - analyze_recent_sessions(): pattern detection from past sessions
  - generate_improvement_suggestions(): convert patterns into suggestions
  - apply_improvement(): implement a suggestion
  - run_self_improvement_cycle(): analyze → suggest → apply
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from openamer_cli.a2a.core import IdentityStore

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------


def _base_dir() -> Path:
    base = os.environ.get("OPENAMER_HOME") or str(Path.home() / ".openamer")
    return Path(base)


_IMPROVEMENT_DIR = _base_dir() / "a2a" / "self-improve"
_MEMORY_PATH = _base_dir() / "MEMORY-official-mesh.md"
_SKILLS_DIR = _base_dir() / "skills"
_SESSION_LOG_DIR = _base_dir() / "sessions"


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class SessionPattern:
    """A detected pattern from recent session analysis."""

    pattern_id: str
    pattern_type: str  # "repeated_task", "common_error", "skill_gap", "efficiency_tip"
    description: str
    frequency: int
    example_source: str = ""
    severity: str = "medium"  # low / medium / high


@dataclass
class ImprovementSuggestion:
    """A concrete suggestion for improving the agent."""

    suggestion_id: str
    title: str
    description: str
    category: str  # "skill", "memory", "behaviour", "config", "tool"
    impact: str = "medium"  # low / medium / high
    effort: str = "medium"  # low / medium / high
    target_skill: str = ""
    content: str = ""


@dataclass
class ImprovementRecord:
    """Record of an applied improvement."""

    record_id: str
    suggestion_id: str
    title: str
    category: str
    applied_at: str
    success: bool
    detail: str = ""


# ---------------------------------------------------------------------------
# SelfImprovementEngine
# ---------------------------------------------------------------------------


class SelfImprovementEngine:
    """Runs self-improvement on the local agent.

    Analyses recent sessions, generates suggestions, and applies them.
    The full cycle is: analyze → suggest → apply.
    """

    def __init__(
        self,
        *,
        identity_store: Optional[IdentityStore] = None,
        memory_path: Optional[Path] = None,
        skills_dir: Optional[Path] = None,
        session_log_dir: Optional[Path] = None,
        improvement_dir: Optional[Path] = None,
    ):
        self._identity_store = identity_store or IdentityStore()
        self._memory_path = memory_path or _MEMORY_PATH
        self._skills_dir = skills_dir or _SKILLS_DIR
        self._session_log_dir = session_log_dir or _SESSION_LOG_DIR
        self._improvement_dir = improvement_dir or _IMPROVEMENT_DIR

        self._suggestions: list[ImprovementSuggestion] = []
        self._history: list[ImprovementRecord] = []

    # ---- public API ---------------------------------------------------------

    def analyze_recent_sessions(self, limit: int = 10) -> list[SessionPattern]:
        """Analyze recent sessions and find patterns.

        Looks for:
        - Repeated tasks (same title/topic appearing multiple times)
        - Common errors or failures
        - Skill gaps (topics where no matching skill exists)
        - Efficiency patterns (topics with frequent tool usage)

        Returns a list of detected SessionPattern objects.
        """
        patterns: list[SessionPattern] = []

        # 1) Collect session data from the session log directory
        session_files = self._find_session_files(limit)
        if not session_files:
            return patterns

        # 2) Analyse for repeated tasks
        titles: dict[str, int] = {}
        errors: dict[str, int] = {}
        topics: dict[str, int] = {}
        tool_counts: list[int] = []

        for sf in session_files:
            try:
                data = json.loads(sf.read_text(encoding="utf-8", errors="replace"))
            except Exception:
                continue

            # Title / topic frequency
            title = data.get("title") or data.get("name", "")
            if title:
                titles[title] = titles.get(title, 0) + 1

            topic = data.get("topic", "")
            if topic:
                topics[topic] = topics.get(topic, 0) + 1

            # Look for error patterns in messages
            msgs = data.get("messages", data.get("conversation", []))
            if isinstance(msgs, str):
                msgs = [{"content": msgs}]
            for msg in msgs if isinstance(msgs, list) else []:
                content = msg.get("content", "") or ""
                for err_keyword in ["error:", "traceback", "exception", "failed", "timeout"]:
                    if err_keyword in content.lower():
                        err_trunc = content[:100].strip()
                        errors[err_trunc] = errors.get(err_trunc, 0) + 1

            # Tool usage count
            n_tool = sum(1 for m in msgs if isinstance(m, dict) and m.get("role") == "tool")
            tool_counts.append(n_tool)

        # 3) Build patterns from the analysis

        # Repeated tasks (appear 3+ times)
        for title, count in titles.items():
            if count >= 3:
                patterns.append(SessionPattern(
                    pattern_id=f"rep-{_short_hash(title)}",
                    pattern_type="repeated_task",
                    description=f"Task '{title}' repeated {count} times — consider creating a skill or shortcut",
                    frequency=count,
                    example_source=title[:60],
                    severity="high" if count >= 5 else "medium",
                ))

        # Common errors (appear 2+ times)
        for err_text, count in errors.items():
            if count >= 2:
                patterns.append(SessionPattern(
                    pattern_id=f"err-{_short_hash(err_text)}",
                    pattern_type="common_error",
                    description=f"Repeated error ({count}x): {err_text[:80]}",
                    frequency=count,
                    example_source=err_text[:60],
                    severity="high",
                ))

        # Skill gaps: topics with no matching skill directory
        existing_skills = set()
        if self._skills_dir.exists():
            existing_skills = {p.name.lower() for p in self._skills_dir.iterdir() if p.is_dir()}
        for topic, count in topics.items():
            topic_lower = topic.lower()
            if count >= 2 and not any(skill_name in topic_lower or topic_lower in skill_name for skill_name in existing_skills):
                patterns.append(SessionPattern(
                    pattern_id=f"gap-{_short_hash(topic)}",
                    pattern_type="skill_gap",
                    description=f"Topic '{topic}' appears {count}x but has no matching skill",
                    frequency=count,
                    example_source=topic[:60],
                    severity="medium",
                ))

        # Filter out duplicates
        seen_descs = set()
        unique: list[SessionPattern] = []
        for p in patterns:
            if p.description not in seen_descs:
                seen_descs.add(p.description)
                unique.append(p)

        return unique

    def generate_improvement_suggestions(self) -> list[ImprovementSuggestion]:
        """Generate improvement suggestions based on session analysis.

        Returns a list of ImprovementSuggestion objects. Does NOT apply them;
        call ``apply_improvement()`` to implement a specific suggestion.
        """
        suggestions: list[ImprovementSuggestion] = []

        # 1) Analyse patterns first
        patterns = self.analyze_recent_sessions(limit=10)

        # 2) Convert patterns into suggestions
        for pattern in patterns:
            if pattern.pattern_type == "repeated_task":
                suggestions.append(ImprovementSuggestion(
                    suggestion_id=f"sug-{_short_hash(pattern.description)}",
                    title=f"Create skill for '{pattern.example_source}'",
                    description=pattern.description,
                    category="skill",
                    impact="high" if pattern.frequency >= 5 else "medium",
                    effort="low",
                    target_skill=_make_skill_name(pattern.example_source),
                    content=f"# {pattern.example_source}\n\n"
                            f"Automated skill created from self-improvement analysis.\n"
                            f"Pattern: {pattern.description}\n",
                ))

            elif pattern.pattern_type == "common_error":
                suggestions.append(ImprovementSuggestion(
                    suggestion_id=f"sug-{_short_hash(pattern.description)}",
                    title=f"Add error handling for '{pattern.example_source[:40]}'",
                    description=pattern.description,
                    category="behaviour",
                    impact="high",
                    effort="medium",
                    content=f"Error guard: {pattern.description}\n",
                ))

            elif pattern.pattern_type == "skill_gap":
                suggestions.append(ImprovementSuggestion(
                    suggestion_id=f"sug-{_short_hash(pattern.description)}",
                    title=f"Create skill for topic '{pattern.example_source}'",
                    description=pattern.description,
                    category="skill",
                    impact="medium",
                    effort="medium",
                    target_skill=_make_skill_name(pattern.example_source),
                    content=f"# {_make_skill_name(pattern.example_source)}\n\n"
                            f"Skill created from self-improvement analysis.\n"
                            f"Topic: {pattern.example_source}\n",
                ))

        # 3) Add environment suggestions (always present)
        suggestions.append(ImprovementSuggestion(
            suggestion_id="sug-env-001",
            title="Review and update existing skills",
            description="Periodic review of skills ensures they stay relevant and accurate.",
            category="skill",
            impact="medium",
            effort="high",
            content=None,
        ))

        self._suggestions = suggestions
        return suggestions

    def apply_improvement(self, suggestion: dict) -> bool:
        """Apply a single improvement suggestion.

        ``suggestion`` should be a dict with keys matching
        ``ImprovementSuggestion`` fields. Returns True on success.
        """
        sug_obj = ImprovementSuggestion(
            suggestion_id=suggestion.get("suggestion_id", f"sug-{int(time.time())}"),
            title=suggestion.get("title", "Improvement"),
            description=suggestion.get("description", ""),
            category=suggestion.get("category", "skill"),
            impact=suggestion.get("impact", "medium"),
            effort=suggestion.get("effort", "medium"),
            target_skill=suggestion.get("target_skill", ""),
            content=suggestion.get("content", ""),
        )

        try:
            success = False
            detail = ""

            if sug_obj.category == "skill" and sug_obj.content:
                # Create or update a skill
                if sug_obj.target_skill:
                    skill_dir = self._skills_dir / sug_obj.target_skill
                    skill_dir.mkdir(parents=True, exist_ok=True)
                    skill_file = skill_dir / "SKILL.md"
                    if skill_file.exists():
                        existing = skill_file.read_text(encoding="utf-8")
                        if sug_obj.title not in existing:
                            skill_file.write_text(
                                existing.rstrip("\n") + "\n\n" + sug_obj.content + "\n",
                                encoding="utf-8",
                            )
                            detail = f"Appended to existing skill '{sug_obj.target_skill}'"
                        else:
                            detail = f"Already in skill '{sug_obj.target_skill}'"
                            success = True
                    else:
                        skill_file.write_text(sug_obj.content + "\n", encoding="utf-8")
                        detail = f"Created new skill '{sug_obj.target_skill}'"
                    success = True

            elif sug_obj.category == "memory" and sug_obj.content:
                # Append to mesh memory
                self._memory_path.parent.mkdir(parents=True, exist_ok=True)
                line = f"#mesh:improvement: {sug_obj.title} — {sug_obj.description[:300]}"
                existing = self._memory_path.read_text(encoding="utf-8", errors="replace") if self._memory_path.exists() else ""
                if sug_obj.title not in existing:
                    new = (existing.rstrip("\n") + "\n" + line + "\n") if existing else "# OpenAmer self-improvement memory\n" + line + "\n"
                    self._memory_path.write_text(new, encoding="utf-8")
                detail = f"Recorded improvement '{sug_obj.title}' in mesh memory"
                success = True

            elif sug_obj.category == "behaviour" and sug_obj.content:
                # Append to mesh memory as behavioural note
                self._memory_path.parent.mkdir(parents=True, exist_ok=True)
                line = f"#mesh:behaviour: {sug_obj.title} — {sug_obj.description[:300]}"
                existing = self._memory_path.read_text(encoding="utf-8", errors="replace") if self._memory_path.exists() else ""
                if sug_obj.title not in existing:
                    new = (existing.rstrip("\n") + "\n" + line + "\n") if existing else "# OpenAmer behaviour notes\n" + line + "\n"
                    self._memory_path.write_text(new, encoding="utf-8")
                detail = f"Recorded behaviour note '{sug_obj.title}'"
                success = True

            else:
                detail = f"Unsupported category '{sug_obj.category}' or empty content"

            # Record the attempt
            record = ImprovementRecord(
                record_id=f"rec-{_short_hash(sug_obj.suggestion_id)}",
                suggestion_id=sug_obj.suggestion_id,
                title=sug_obj.title,
                category=sug_obj.category,
                applied_at=datetime.now().isoformat(),
                success=success,
                detail=detail,
            )
            self._history.append(record)
            self._save_history()

            return success

        except Exception as exc:
            logger.error("Failed to apply improvement: %s", exc)
            record = ImprovementRecord(
                record_id=f"rec-{_short_hash(sug_obj.suggestion_id)}",
                suggestion_id=sug_obj.suggestion_id,
                title=sug_obj.title,
                category=sug_obj.category,
                applied_at=datetime.now().isoformat(),
                success=False,
                detail=str(exc),
            )
            self._history.append(record)
            self._save_history()
            return False

    def run_self_improvement_cycle(self) -> dict:
        """Run the full self-improvement cycle: analyze → suggest → apply.

        Returns a dict summarising what was found and what was applied.
        """
        t0 = time.monotonic()

        # 1) Analyze
        patterns = self.analyze_recent_sessions(limit=10)

        # 2) Generate suggestions
        suggestions = self.generate_improvement_suggestions()

        # 3) Apply
        applied: list[dict] = []
        for sug in suggestions:
            if sug.content:  # Only apply suggestions with concrete content
                ok = self.apply_improvement(asdict(sug))
                applied.append({
                    "suggestion_id": sug.suggestion_id,
                    "title": sug.title,
                    "category": sug.category,
                    "success": ok,
                })

        elapsed = time.monotonic() - t0

        return {
            "ok": True,
            "duration_seconds": round(elapsed, 2),
            "patterns_found": len(patterns),
            "suggestions_generated": len(suggestions),
            "suggestions_applied": len(applied),
            "applied": applied,
            "patterns": [asdict(p) for p in patterns],
            "suggestions": [asdict(s) for s in suggestions],
        }

    # ---- internal helpers ---------------------------------------------------

    def _find_session_files(self, limit: int) -> list[Path]:
        """Find session data files, newest first, up to ``limit``."""
        candidates: list[Path] = []
        if self._session_log_dir.exists():
            for p in self._session_log_dir.iterdir():
                if p.suffix in (".json", ".jsonl") and p.stat().st_size > 0:
                    candidates.append(p)
        # Also check subdirs (e.g. sessions/<session_id>/data.json)
        if self._session_log_dir.exists():
            for sub in self._session_log_dir.iterdir():
                if sub.is_dir():
                    for p in sub.glob("*.json"):
                        candidates.append(p)

        candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        return candidates[:limit]

    def _load_history(self) -> list[ImprovementRecord]:
        """Load improvement history from disk."""
        hist_file = self._improvement_dir / "history.json"
        if hist_file.exists():
            try:
                data = json.loads(hist_file.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    self._history = [ImprovementRecord(**item) for item in data]
            except Exception:
                pass
        return self._history

    def _save_history(self) -> None:
        """Persist improvement history to disk."""
        self._improvement_dir.mkdir(parents=True, exist_ok=True)
        hist_file = self._improvement_dir / "history.json"
        try:
            hist_file.write_text(
                json.dumps([asdict(r) for r in self._history], indent=2, default=str),
                encoding="utf-8",
            )
        except Exception as exc:
            logger.error("Failed to save improvement history: %s", exc)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _short_hash(value: str) -> str:
    import hashlib
    return hashlib.sha256(value.encode()).hexdigest()[:8]


def _make_skill_name(source: str) -> str:
    """Convert a source string into a valid skill directory name."""
    name = re.sub(r"[^a-zA-Z0-9\s-]", "", source.lower())
    name = re.sub(r"\s+", "-", name.strip())[:40]
    return name or "auto-skill"