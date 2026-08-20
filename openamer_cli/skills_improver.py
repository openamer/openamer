"""Self-Improving Skills System for OpenAmer.

Tracks skill usage, identifies improvement opportunities, and
automatically suggests or applies improvements based on usage patterns.
"""
from __future__ import annotations

import json
import os
import time
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class SkillUsageRecord:
    """Tracks usage history for a single skill."""

    skill_name: str
    times_used: int = 0
    last_used: Optional[str] = None  # ISO-8601
    success_rate: float = 0.0  # 0.0 – 1.0
    avg_duration: float = 0.0  # seconds
    user_rating: float = 0.0  # 0.0 – 5.0, 0 = unrated

    # Internal bookkeeping
    _success_count: int = 0
    _fail_count: int = 0
    _total_duration: float = 0.0

    def record_usage(self, success: bool, duration_seconds: float) -> None:
        """Record a single usage event and update derived stats."""
        self.times_used += 1
        self.last_used = datetime.now(timezone.utc).isoformat()

        if success:
            self._success_count += 1
        else:
            self._fail_count += 1

        total_attempts = self._success_count + self._fail_count
        self.success_rate = (
            self._success_count / total_attempts if total_attempts > 0 else 0.0
        )

        self._total_duration += duration_seconds
        self.avg_duration = self._total_duration / self.times_used

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> SkillUsageRecord:
        # Handle both camelCase and snake_case keys for _internal fields
        internal = {
            "_success_count": data.pop("_success_count", 0),
            "_fail_count": data.pop("_fail_count", 0),
            "_total_duration": data.pop("_total_duration", 0.0),
        }
        return cls(**{**data, **internal})


# ---------------------------------------------------------------------------
# Persistent usage store
# ---------------------------------------------------------------------------

_DEFAULT_STORE_PATH = Path(
    os.environ.get(
        "OPENAMER_SKILLS_STORE",
        str(Path.home() / ".openamer" / "skills_usage.json"),
    )
)


class SkillUsageStore:
    """Persistent JSON-backed store for SkillUsageRecord objects."""

    def __init__(self, path: Optional[Path] = None) -> None:
        self._path = path or _DEFAULT_STORE_PATH
        self._data: Dict[str, SkillUsageRecord] = {}
        self._load()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get(self, name: str) -> Optional[SkillUsageRecord]:
        return self._data.get(name)

    def get_or_create(self, name: str) -> SkillUsageRecord:
        if name not in self._data:
            self._data[name] = SkillUsageRecord(skill_name=name)
        return self._data[name]

    def put(self, record: SkillUsageRecord) -> None:
        self._data[record.skill_name] = record

    def all(self) -> List[SkillUsageRecord]:
        return list(self._data.values())

    def names(self) -> List[str]:
        return list(self._data.keys())

    def flush(self) -> None:
        """Write data to disk."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        raw = {
            name: record.to_dict()
            for name, record in self._data.items()
        }
        self._path.write_text(json.dumps(raw, indent=2, default=str), encoding="utf-8")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load(self) -> None:
        if not self._path.exists():
            self._data = {}
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            self._data = {
                name: SkillUsageRecord.from_dict(record)
                for name, record in raw.items()
            }
        except (json.JSONDecodeError, KeyError, ValueError):
            self._data = {}


# ---------------------------------------------------------------------------
# SkillImprover — the main workhorse
# ---------------------------------------------------------------------------

IMPROVEMENT_SUGGESTIONS: Dict[str, List[str]] = {
    "low_success": [
        "Review skill instructions — they may be outdated or ambiguous.",
        "Add more concrete examples to the skill's SKILL.md.",
        "Consider splitting the skill into smaller, focused skills.",
        "Add verification steps so failures are caught early.",
    ],
    "low_usage": [
        "Improve the skill's trigger description so agents recognize when to use it.",
        "Add aliases or alternative trigger patterns to the skill metadata.",
        "Create a simpler quick-start section at the top of SKILL.md.",
    ],
    "high_rating": [
        "This skill performs well; consider promoting it in the skill index.",
        "Add advanced usage examples to unlock even more value.",
        "Extract reusable sub-patterns into standalone helper skills.",
    ],
    "slow_execution": [
        "Optimize shell commands or reduce redundant file reads.",
        "Use caching for expensive lookups or API calls.",
        "Parallelize independent steps where possible.",
    ],
    "volatile": [
        "Skill is used frequently but success rate oscillates — investigate external dependencies.",
        "Add pre-flight checks before main execution.",
        "Consider fallback paths when the primary approach fails.",
    ],
}


class SkillImprover:
    """Tracks skill usage, identifies improvement opportunities, and
    suggests or automatically applies improvements."""

    def __init__(self, store: Optional[SkillUsageStore] = None) -> None:
        self._store = store or SkillUsageStore()

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    def track_skill_usage(
        self,
        skill_name: str,
        success: bool,
        duration_seconds: float,
    ) -> SkillUsageRecord:
        """Log a usage event for the named skill.

        Returns the updated SkillUsageRecord.
        """
        record = self._store.get_or_create(skill_name)
        record.record_usage(success, duration_seconds)
        self._store.put(record)
        self._store.flush()
        return record

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    def get_skill_stats(self, name: str) -> dict:
        """Return usage statistics for a skill.

        Returns a dict with keys: skill_name, times_used, last_used,
        success_rate, avg_duration, user_rating.
        If no data exists yet, returns a zeroed entry with the requested name.
        """
        record = self._store.get(name)
        if record is None:
            return SkillUsageRecord(skill_name=name).to_dict()
        return record.to_dict()

    def list_all_stats(self) -> List[dict]:
        """Return stats for every tracked skill."""
        return [r.to_dict() for r in self._store.all()]

    # ------------------------------------------------------------------
    # Improvement suggestions
    # ------------------------------------------------------------------

    def suggest_improvements(self, name: str) -> list:
        """Suggest improvements for a skill based on usage patterns.

        Returns a list of human-readable recommendation strings.
        """
        record = self._store.get(name)
        if record is None:
            return [f"No usage data for '{name}' — use it first to get suggestions."]

        if record.times_used < 1:
            return [f"No usage data for '{name}' — use it first to get suggestions."]

        suggestions: List[str] = []
        patterns: List[str] = []

        # --- Pattern analysis ---

        # Low success rate
        if record.success_rate < 0.5 and record.times_used >= 3:
            patterns.append("low_success")
            suggestions.append(
                f"⚠️  Low success rate ({record.success_rate:.0%} after "
                f"{record.times_used} uses)."
            )

        # Rarely used
        if record.times_used < 3:
            patterns.append("low_usage")

        # High rating + low usage = hidden gem
        if record.user_rating >= 4.0 and record.times_used < 5:
            suggestions.append(
                f"⭐ Highly rated ({record.user_rating:.1f}/5) but "
                f"only used {record.times_used} times — consider promoting."
            )

        # Slow execution
        if record.avg_duration > 30 and record.times_used >= 3:
            patterns.append("slow_execution")
            suggestions.append(
                f"⏱  Slow average execution ({record.avg_duration:.1f}s)."
            )

        # Volatile: used often but success rate wavers (between 40-70% with enough data)
        if (
            3 <= record.times_used <= 20
            and 0.3 <= record.success_rate <= 0.7
        ):
            patterns.append("volatile")

        # Good performer
        if record.success_rate >= 0.9 and record.times_used >= 5:
            patterns.append("high_rating")

        # --- Attach canned improvement ideas per pattern ---
        for pat in patterns:
            canned = IMPROVEMENT_SUGGESTIONS.get(pat, [])
            suggestions.extend(f"  • {tip}" for tip in canned)

        if not suggestions:
            suggestions.append(
                f"✓ '{name}' looks healthy ({record.times_used} uses, "
                f"{record.success_rate:.0%} success, "
                f"{record.avg_duration:.1f}s avg)."
            )

        return suggestions

    # ------------------------------------------------------------------
    # Auto-improve
    # ------------------------------------------------------------------

    def auto_improve_skills(self) -> List[dict]:
        """Run improvement suggestions automatically.

        For each tracked skill with enough data, returns a structured
        report of what improvements were identified.

        Returns a list of dicts:
            {skill_name, patterns_found, suggestions, auto_applied}
        """
        results: List[dict] = []
        for record in self._store.all():
            if record.times_used < 2:
                continue
            suggestions = self.suggest_improvements(record.skill_name)
            raw = [s for s in suggestions if not s.startswith("✓")]
            results.append({
                "skill_name": record.skill_name,
                "patterns_found": self._detect_patterns(record),
                "suggestions": raw,
                "auto_applied": self._apply_auto_fixes(record),
            })
        return results

    # ------------------------------------------------------------------
    # Rating
    # ------------------------------------------------------------------

    def rate_skill(self, name: str, rating: float) -> Optional[SkillUsageRecord]:
        """Set user rating (0.0–5.0) for a skill. Returns updated record or None."""
        if not 0.0 <= rating <= 5.0:
            raise ValueError("Rating must be between 0.0 and 5.0")
        record = self._store.get(name)
        if record is None:
            return None
        record.user_rating = rating
        self._store.put(record)
        self._store.flush()
        return record

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _detect_patterns(self, record: SkillUsageRecord) -> List[str]:
        patterns: List[str] = []
        if record.success_rate < 0.5 and record.times_used >= 3:
            patterns.append("low_success")
        if record.times_used < 3:
            patterns.append("low_usage")
        if record.avg_duration > 30 and record.times_used >= 3:
            patterns.append("slow_execution")
        if record.user_rating >= 4.0 and record.times_used >= 5:
            patterns.append("high_rating")
        if 3 <= record.times_used <= 20 and 0.3 <= record.success_rate <= 0.7:
            patterns.append("volatile")
        return patterns

    def _apply_auto_fixes(self, record: SkillUsageRecord) -> List[str]:
        """Apply non-destructive auto-fixes. Returns list of applied actions."""
        applied: List[str] = []
        # Currently a placeholder for future automated fixes.
        # Could: rewrite SKILL.md frontmatter, add usage notes, etc.
        if record.success_rate < 0.3 and record.times_used >= 5:
            applied.append(
                f"Flagged '{record.skill_name}' for manual review "
                "(success rate below 30%)."
            )
        return applied