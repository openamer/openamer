"""User Profile System for OpenAmer.

Learns from session data, builds user profiles with skill affinities,
tool preferences, and behavioral patterns, and surfaces actionable insights.
"""
from __future__ import annotations

import json
import os
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class UserProfile:
    """A learned user profile capturing behavioral patterns and preferences."""

    name: str
    preferences: Dict[str, Any] = field(default_factory=dict)
    skill_affinities: Dict[str, float] = field(default_factory=dict)
    favorite_tools: List[str] = field(default_factory=list)
    session_patterns: Dict[str, Any] = field(default_factory=dict)

    created_at: str = ""
    updated_at: str = ""
    total_sessions_analyzed: int = 0

    def __post_init__(self) -> None:
        now = datetime.now(timezone.utc).isoformat()
        if not self.created_at:
            self.created_at = now
        if not self.updated_at:
            self.updated_at = now

    def merge(self, other: UserProfile) -> None:
        """Merge another profile's data into this one."""
        # Preferences: latest wins for each key
        self.preferences.update(other.preferences)

        # Skill affinities: weighted average
        for skill, weight in other.skill_affinities.items():
            if skill in self.skill_affinities:
                self.skill_affinities[skill] = (
                    self.skill_affinities[skill] + weight
                ) / 2
            else:
                self.skill_affinities[skill] = weight

        # Favorite tools: merge unique
        existing = set(self.favorite_tools)
        for t in other.favorite_tools:
            if t not in existing:
                self.favorite_tools.append(t)
                existing.add(t)

        # Session patterns: latest wins for each key
        self.session_patterns.update(other.session_patterns)

        self.total_sessions_analyzed += other.total_sessions_analyzed
        self.updated_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> UserProfile:
        return cls(**data)


# ---------------------------------------------------------------------------
# Profile persistence
# ---------------------------------------------------------------------------

_DEFAULT_STORE_DIR = Path(
    os.environ.get(
        "OPENAMER_PROFILES_DIR",
        str(Path.home() / ".openamer" / "user_profiles"),
    )
)


class ProfileStore:
    """Save, load, list, and delete user profiles from disk."""

    def __init__(self, store_dir: Optional[Path] = None) -> None:
        self._dir = store_dir or _DEFAULT_STORE_DIR
        self._dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def save(self, profile: UserProfile) -> None:
        """Persist a profile to disk."""
        path = self._profile_path(profile.name)
        path.parent.mkdir(parents=True, exist_ok=True)
        profile.updated_at = datetime.now(timezone.utc).isoformat()
        path.write_text(
            json.dumps(profile.to_dict(), indent=2, default=str),
            encoding="utf-8",
        )

    def load(self, name: str) -> Optional[UserProfile]:
        """Load a profile by name. Returns None if not found."""
        path = self._profile_path(name)
        if not path.exists():
            return None
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            return UserProfile.from_dict(raw)
        except (json.JSONDecodeError, KeyError, ValueError):
            return None

    def list_profiles(self) -> List[str]:
        """Return names of all stored profiles."""
        names: List[str] = []
        for entry in self._dir.iterdir():
            if entry.suffix == ".json":
                name = entry.stem
                if name and not name.startswith("."):
                    names.append(name)
        return sorted(names)

    def delete(self, name: str) -> bool:
        """Delete a profile by name. Returns True if it existed."""
        path = self._profile_path(name)
        if not path.exists():
            return False
        path.unlink()
        return True

    def exists(self, name: str) -> bool:
        return self._profile_path(name).exists()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _profile_path(self, name: str) -> Path:
        return self._dir / f"{name}.json"


# ---------------------------------------------------------------------------
# Session learning engine
# ---------------------------------------------------------------------------

# Tools commonly used together for pattern detection
_TOOL_PAIRS: Dict[str, Set[str]] = {
    "terminal": {"read_file", "write_file", "patch"},
    "read_file": {"write_file", "patch", "search_files"},
    "search_files": {"read_file", "grep"},
    "browser_navigate": {"browser_snapshot", "browser_click", "browser_vision"},
    "write_file": {"patch", "read_file", "terminal"},
}

# Skill-name patterns
_SKILL_PATTERN = re.compile(r"skill[_-]?(\w+)", re.IGNORECASE)


class SessionLearner:
    """Extracts user patterns from session data."""

    @staticmethod
    def learn(profile: UserProfile, session_data: dict) -> UserProfile:
        """Feed session data into a profile. Returns the updated profile."""
        extracted = SessionLearner._extract(session_data)
        profile.merge(extracted)
        profile.total_sessions_analyzed += 1
        return profile

    @staticmethod
    def _extract(session_data: dict) -> UserProfile:
        """Extract a one-shot profile from raw session data."""
        tools = session_data.get("tools_used", []) or []
        skills = session_data.get("skills_used", []) or []
        messages = session_data.get("messages", []) or []
        duration = session_data.get("duration_seconds", 0)
        session_patterns: Dict[str, Any] = {}
        preferences: Dict[str, Any] = {}

        # --- Tool usage analysis ---
        tool_counts = Counter(str(t) for t in tools)
        total_tool_calls = sum(tool_counts.values()) or 1
        sorted_tools = tool_counts.most_common()

        favorite_tools = [t for t, _ in sorted_tools[:5]]

        # Detect tool chains (sequential patterns common in the session)
        tool_chains = SessionLearner._detect_tool_chains(tools)

        # --- Skill affinities ---
        skill_affinities: Dict[str, float] = {}
        for skill in skills:
            name = skill if isinstance(skill, str) else skill.get("name", str(skill))
            weight = 1.0
            if isinstance(skill, dict):
                weight = skill.get("weight", 1.0)
            skill_affinities[name] = weight

        # Also extract skill references from message content
        for msg in messages:
            content = ""
            if isinstance(msg, dict):
                content = msg.get("content", "") or ""
            elif isinstance(msg, str):
                content = msg
            for match in _SKILL_PATTERN.finditer(content):
                skill_name = match.group(1).lower()
                if skill_name not in skill_affinities:
                    skill_affinities[skill_name] = 0.5
                else:
                    skill_affinities[skill_name] += 0.1

        # --- Session patterns ---
        session_patterns = {
            "total_tool_calls": total_tool_calls,
            "tool_diversity": len(tool_counts),
            "favorite_tools": favorite_tools[:3],
            "duration_seconds": duration,
            "tool_chains": tool_chains[:5],
        }

        # --- Preferences ---
        # Detect common terminal languages
        terminal_commands = [
            str(t) for t in tools if "terminal" in str(t).lower()
        ]
        lang_hints = SessionLearner._detect_languages_from_tools(tools)
        if lang_hints:
            preferences["languages"] = lang_hints
        if terminal_commands:
            preferences["terminal_usage"] = len(terminal_commands)

        return UserProfile(
            name="",
            preferences=preferences,
            skill_affinities=skill_affinities,
            favorite_tools=favorite_tools,
            session_patterns=session_patterns,
        )

    @staticmethod
    def _detect_tool_chains(tools: List[str]) -> List[str]:
        """Detect common sequential tool patterns."""
        if len(tools) < 2:
            return []
        chains: List[str] = []
        for i in range(len(tools) - 1):
            a, b = tools[i], tools[i + 1]
            if a in _TOOL_PAIRS and b in _TOOL_PAIRS[a]:
                chain = f"{a} → {b}"
                if chain not in chains:
                    chains.append(chain)
        return chains

    @staticmethod
    def _detect_languages_from_tools(tools: List[str]) -> List[str]:
        lang_map = {
            ".py": "python",
            ".js": "javascript",
            ".ts": "typescript",
            ".rs": "rust",
            ".go": "golang",
            ".java": "java",
            ".cpp": "cpp",
            ".rb": "ruby",
        }
        seen: Set[str] = set()
        for t in tools:
            for ext, lang in lang_map.items():
                if ext in str(t):
                    seen.add(lang)
        return sorted(seen)


# ---------------------------------------------------------------------------
# Insights engine
# ---------------------------------------------------------------------------

class ProfileInsights:
    """Generates human-readable insights from user profiles."""

    def __init__(self, store: ProfileStore) -> None:
        self._store = store

    def get_profile_insights(self) -> List[dict]:
        """Return actionable insights about user behavior across all profiles."""
        insights: List[dict] = []
        for name in self._store.list_profiles():
            profile = self._store.load(name)
            if profile is None:
                continue
            profile_insights = self._analyze_profile(profile)
            insights.extend(profile_insights)
        return insights

    def get_profile_insights_for(self, name: str) -> List[dict]:
        profile = self._store.load(name)
        if profile is None:
            return [{"type": "error", "message": f"Profile '{name}' not found."}]
        return self._analyze_profile(profile)

    # ------------------------------------------------------------------
    # Per-profile analysis
    # ------------------------------------------------------------------

    def _analyze_profile(self, profile: UserProfile) -> List[dict]:
        insights: List[dict] = []
        sp = profile.session_patterns or {}

        # --- Usage maturity ---
        if profile.total_sessions_analyzed == 0:
            insights.append({
                "type": "info",
                "message": "No sessions analyzed yet — start using OpenAmer to build your profile.",
            })
            return insights

        insights.append({
            "type": "usage",
            "message": f"Analyzed {profile.total_sessions_analyzed} session(s).",
        })

        # --- Tool diversity ---
        tool_diversity = sp.get("tool_diversity", 0)
        if tool_diversity >= 10:
            insights.append({
                "type": "power_user",
                "message": f"You use {tool_diversity} different tools — you're a power user!",
            })
        elif tool_diversity <= 3:
            insights.append({
                "type": "suggestion",
                "message": "You use only a few tools — try the browser or terminal for new capabilities.",
            })

        # --- Tool chains ---
        chains = sp.get("tool_chains", [])
        if chains:
            insights.append({
                "type": "pattern",
                "message": f"Common workflow: {chains[0]}",
            })

        # --- Skill affinities ---
        if profile.skill_affinities:
            top_skills = sorted(
                profile.skill_affinities.items(),
                key=lambda x: -x[1],
            )[:3]
            skill_str = ", ".join(f"{s}" for s, _ in top_skills)
            insights.append({
                "type": "affinity",
                "message": f"Top skill affinities: {skill_str}",
            })

        # --- Favorite tools ---
        if profile.favorite_tools:
            tools_str = ", ".join(profile.favorite_tools[:5])
            insights.append({
                "type": "tools",
                "message": f"Favorite tools: {tools_str}",
            })

        # --- Time-based ---
        duration = sp.get("duration_seconds", 0)
        if duration > 0:
            mins = duration / 60
            if mins > 30:
                insights.append({
                    "type": "session_length",
                    "message": f"Long sessions (avg {mins:.0f} min) — consider breaks between focused work.",
                })

        # --- Languages ---
        langs = profile.preferences.get("languages", [])
        if langs:
            insights.append({
                "type": "languages",
                "message": f"Preferred languages: {', '.join(langs)}",
            })

        return insights


# ---------------------------------------------------------------------------
# Convenience: learn_from_session (standalone function)
# ---------------------------------------------------------------------------

def learn_from_session(session_data: dict) -> Dict[str, Any]:
    """Extract patterns from a single session and return as a profile dict.

    This is the high-level API intended for external callers.
    """
    learner = SessionLearner()
    profile = learner._extract(session_data)
    return profile.to_dict()


def get_profile_insights() -> List[dict]:
    """Return insights about user behavior. Convenience wrapper."""
    store = ProfileStore()
    engine = ProfileInsights(store)
    return engine.get_profile_insights()