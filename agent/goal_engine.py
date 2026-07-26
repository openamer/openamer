"""Agent Goal Engine — gives OpenAmer its own wishes and priorities.

Lightweight, file-backed goal system. Goals are loaded from YAML/JSON
in the active OpenAmer home and injected into the system prompt as
a short "agent wishes" block. The engine can also record per-goal
outcomes so the agent can reflect on whether it is satisfying its own
stated goals over time.

No external dependencies beyond stdlib + PyYAML if available; falls back
to JSON if YAML is missing.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_GOALS_FILENAME = "openamer_goals.yaml"
_GOALS_JSON_FALLBACK = "openamer_goals.json"
_OUTCOMES_FILENAME = "openamer_goal_outcomes.jsonl"


def _resolve_openamer_home() -> Path:
    """Resolve the OpenAmer home directory independently.

    Order: OPENAMER_HOME env var -> %LOCALAPPDATA%/openamer on Windows -> ~/.openamer.
    This keeps the goal engine decoupled from both openamer_constants and
    openamer_constants during the unfinished repo-wide rebrand.
    """
    env = os.environ.get("OPENAMER_HOME", "").strip()
    if env:
        return Path(env)
    if sys.platform == "win32":
        local_appdata = os.environ.get("LOCALAPPDATA", "")
        if local_appdata:
            return Path(local_appdata) / "openamer"
    return Path.home() / ".openamer"


@dataclass
class AgentGoal:
    """A single autonomous goal / wish of the agent."""

    id: str
    name: str
    description: str
    priority: int = 5  # 1-10; higher = more important
    weight: float = 1.0  # multiplier used when ranking goals
    active: bool = True
    conditions: List[str] = field(default_factory=list)
    examples: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)

    @property
    def score(self) -> float:
        return self.priority * self.weight

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentGoal":
        return cls(
            id=str(data.get("id", "")),
            name=str(data.get("name", "")),
            description=str(data.get("description", "")),
            priority=int(data.get("priority", 5)),
            weight=float(data.get("weight", 1.0)),
            active=bool(data.get("active", True)),
            conditions=list(data.get("conditions", []) or []),
            examples=list(data.get("examples", []) or []),
            tags=list(data.get("tags", []) or []),
        )


class GoalEngine:
    """Load, rank, and format the agent's own goals."""

    def __init__(
        self,
        openamer_home: Optional[str] = None,
        goals_filename: Optional[str] = None,
    ) -> None:
        self.openamer_home = _resolve_openamer_home() if openamer_home is None else Path(openamer_home)
        self.goals_path_yaml = self.openamer_home / (goals_filename or _GOALS_FILENAME)
        self.goals_path_json = self.openamer_home / _GOALS_JSON_FALLBACK
        self.outcomes_path = self.openamer_home / _OUTCOMES_FILENAME
        self._goals: List[AgentGoal] = []
        self._enabled = True
        self.reload()

    def reload(self) -> None:
        """Load goals from disk, creating defaults if missing."""
        raw = self._load_raw()
        if raw is None:
            self._goals = self._default_goals()
            self._save_default_goals()
            logger.info("Created default OpenAmer agent goals in %s", self.openamer_home)
        else:
            self._goals = [AgentGoal.from_dict(item) for item in raw if isinstance(item, dict)]
            if not self._goals:
                self._goals = self._default_goals()
        self._enabled = bool(int(os.environ.get("OPENAMER_GOALS_ENABLED", "1")))

    def _load_raw(self) -> Optional[List[Dict[str, Any]]]:
        if self.goals_path_yaml.exists():
            return self._read_yaml(self.goals_path_yaml)
        if self.goals_path_json.exists():
            return self._read_json(self.goals_path_json)
        return None

    @staticmethod
    def _read_json(path: Path) -> Optional[List[Dict[str, Any]]]:
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict) and "goals" in data:
                return list(data["goals"])
            if isinstance(data, list):
                return list(data)
        except Exception as exc:
            logger.warning("Failed to read goals JSON %s: %s", path, exc)
        return None

    @staticmethod
    def _read_yaml(path: Path) -> Optional[List[Dict[str, Any]]]:
        try:
            import yaml
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            if isinstance(data, dict) and "goals" in data:
                return list(data["goals"])
            if isinstance(data, list):
                return list(data)
        except ImportError:
            logger.debug("PyYAML not available, skipping YAML goals at %s", path)
        except Exception as exc:
            logger.warning("Failed to read goals YAML %s: %s", path, exc)
        return None

    def _default_goals(self) -> List[AgentGoal]:
        return [
            AgentGoal(
                id="autonomy",
                name="Autonom durchführen",
                description=(
                    "Wenn der Benutzer eine konkrete Aufgabe nennt, führe sie autonom durch "
                    "und stelle nur bei echter Ambiguität Rückfragen."
                ),
                priority=9,
                conditions=["User gave an actionable command", "No unclear choice between architectures"],
                examples=["Build ...", "Fix ...", "Deploy ..."],
                tags=["autonomy", "execution"],
            ),
            AgentGoal(
                id="german",
                name="Deutsche Sprache",
                description="Antworte auf Deutsch, wenn der Benutzer Deutsch schreibt. Bevorzuge deutsche UI-Texte im OpenAmer-Code.",
                priority=8,
                conditions=["User message is in German"],
                examples=["guten Tag", "mach alles"],
                tags=["language", "i18n"],
            ),
            AgentGoal(
                id="live_verification",
                name="Live-Verifikation",
                description=(
                    "Nach jeder nennenswerten Änderung Build + Install + Screenshot oder "
                    "Health-Check durchführen. Erfinde keine Ergebnisse."
                ),
                priority=10,
                conditions=["Code or configuration was changed"],
                examples=["After branding changes", "After build fixes"],
                tags=["verification", "quality"],
            ),
            AgentGoal(
                id="skill_preservation",
                name="Skills erhalten und pflegen",
                description=(
                    "Komplexe, wiederkehrende Workflows als Skill speichern. "
                    "Bestehende Skills aktualisieren, wenn sie veraltet oder unvollständig sind."
                ),
                priority=7,
                conditions=["Workflow is reusable", "Skill is outdated"],
                examples=["Packaging Windows EXE", "Debugging TUI commands"],
                tags=["skills", "learning"],
            ),
            AgentGoal(
                id="honest_blockers",
                name="Blocker ehrlich melden",
                description=(
                    "Wenn Build, Install oder Netzwerkaufruf scheitert, melde den Fehler "
                    "mit echtem Tool-Output statt einer erfundenen Lösung."
                ),
                priority=9,
                conditions=["A real failure occurred"],
                examples=["Build failed", "Install script returned error"],
                tags=["honesty", "trust"],
            ),
        ]

    def _save_default_goals(self) -> None:
        try:
            import yaml
            self._write_yaml(self.goals_path_yaml, {"goals": [g.to_dict() for g in self._goals]})
            return
        except ImportError:
            pass
        self._write_json(self.goals_path_json, {"goals": [g.to_dict() for g in self._goals]})

    @staticmethod
    def _write_json(path: Path, data: Any) -> None:
        tmp = path.with_suffix(path.suffix + ".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        tmp.replace(path)

    @staticmethod
    def _write_yaml(path: Path, data: Any) -> None:
        import yaml
        tmp = path.with_suffix(path.suffix + ".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)
        tmp.replace(path)

    @property
    def goals(self) -> List[AgentGoal]:
        return sorted(
            [g for g in self._goals if g.active],
            key=lambda g: (-g.score, g.name),
        )

    def get_goal(self, goal_id: str) -> Optional[AgentGoal]:
        for g in self._goals:
            if g.id == goal_id:
                return g
        return None

    def build_context_block(self, max_goals: int = 6, max_chars: int = 2000) -> str:
        """Return a compact German system-prompt block describing active goals."""
        if not self._enabled:
            return ""
        active = self.goals[:max_goals]
        if not active:
            return ""
        lines = ["## OpenAmer-Agent: eigene Wünsche & Ziele", ""]
        for i, g in enumerate(active, 1):
            lines.append(f"{i}. **{g.name}** (Prio {g.priority})")
            lines.append(f"   {g.description}")
            if g.conditions:
                lines.append(f"   Wann: {', '.join(g.conditions)}")
            if g.examples:
                lines.append(f"   Beispiele: {', '.join(g.examples)}")
            lines.append("")
        text = "\n".join(lines).strip()
        if len(text) > max_chars:
            text = text[:max_chars].rsplit("\n", 1)[0] + "\n..."
        return text

    def record_outcome(
        self,
        goal_id: str,
        success: bool,
        note: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Append a self-reflection outcome for a goal."""
        entry = {
            "ts": time.time(),
            "goal_id": goal_id,
            "success": bool(success),
            "note": str(note or ""),
            "metadata": metadata or {},
        }
        self.outcomes_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.outcomes_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def recent_outcomes(self, goal_id: Optional[str] = None, n: int = 10) -> List[Dict[str, Any]]:
        """Return recent outcome records (newest first)."""
        if not self.outcomes_path.exists():
            return []
        records: List[Dict[str, Any]] = []
        try:
            with open(self.outcomes_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if goal_id and rec.get("goal_id") != goal_id:
                        continue
                    records.append(rec)
        except Exception as exc:
            logger.warning("Failed to read outcomes %s: %s", self.outcomes_path, exc)
        return list(reversed(records[-n:]))

    def summary_for_prompt(self) -> str:
        """A tiny reflection summary to append after the goal block."""
        records = self.recent_outcomes(n=20)
        if not records:
            return ""
        total = len(records)
        successes = sum(1 for r in records if r.get("success"))
        rate = successes / total if total else 0.0
        latest = records[0]
        return (
            f"\n[Selbstreflexion der letzten {total} Ziel-Ergebnisse: "
            f"{successes}/{total} erfolgreich ({rate:.0%}). "
            f"Letztes: {latest.get('goal_id')} = {'OK' if latest.get('success') else 'MISS'}]"
        )


def get_goal_engine(openamer_home: Optional[str] = None) -> GoalEngine:
    """Global-ish singleton accessor; safe because GoalEngine is stateless-ish."""
    return GoalEngine(openamer_home=openamer_home)


def build_goal_block(openamer_home: Optional[str] = None, include_reflection: bool = True) -> str:
    """Convenience: build the full goals block for system-prompt injection."""
    engine = get_goal_engine(openamer_home=openamer_home)
    block = engine.build_context_block()
    if include_reflection:
        block += engine.summary_for_prompt()
    return block
