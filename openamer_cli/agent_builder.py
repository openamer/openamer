"""Agent Builder — create, list, delete, and manage autonomous agents.

An "agent" in OpenAmer is a named system that combines:
  - A SKILL.md loaded at session start (its goal + description)
  - An optional cron schedule (periodic execution)
  - A set of skills to pre-load
  - A set of tools to enable

Agents are stored under ~/.openamer/agents/ as JSON definitions.
Their skills live under ~/.openamer/skills/<agent_name>/ as SKILL.md.
"""

import json
import os
import re
import shutil
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Any, Dict


# =============================================================================
# Constants
# =============================================================================

_OPENAMER_HOME = Path(os.environ.get("OPENAMER_HOME", Path.home() / ".openamer"))
AGENTS_DIR = _OPENAMER_HOME / "agents"
SKILLS_BASE = _OPENAMER_HOME / "skills"


# =============================================================================
# Data model
# =============================================================================

@dataclass
class AgentSpec:
    """Specification for creating an OpenAmer agent."""
    name: str
    description: str = ""
    goal: str = ""
    cron_schedule: Optional[str] = None
    skills: List[str] = field(default_factory=list)
    tools: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "AgentSpec":
        return cls(
            name=d["name"],
            description=d.get("description", ""),
            goal=d.get("goal", ""),
            cron_schedule=d.get("cron_schedule"),
            skills=d.get("skills", []),
            tools=d.get("tools", []),
            created_at=d.get("created_at", datetime.now().isoformat()),
        )


# =============================================================================
# Skill SKILL.md template
# =============================================================================

_SKILL_TEMPLATE = """---
name: {name}
description: "{description}"
generated_by: openamer-agent-builder
generated_at: {created_at}
---

# {name} Agent

{goal}

## Skills

{skills_section}

## Tools

{tools_section}
"""


def _skill_content(spec: AgentSpec) -> str:
    skills_section = "\n".join(
        f"- {s}" for s in spec.skills
    ) if spec.skills else "*(none configured)*"

    tools_section = "\n".join(
        f"- {t}" for t in spec.tools
    ) if spec.tools else "*(none configured)*"

    return _SKILL_TEMPLATE.format(
        name=spec.name,
        description=spec.description or spec.goal[:80] if spec.goal else spec.name,
        goal=spec.goal or spec.description,
        created_at=spec.created_at,
        skills_section=skills_section,
        tools_section=tools_section,
    )


# =============================================================================
# Natural-language parser (keyword-based, no LLM dependency)
# =============================================================================

_SCHEDULE_PATTERNS = [
    # "every N hours" -> "N * * * *"
    (re.compile(r"every\s+(\d+)\s*hours?", re.IGNORECASE),
     lambda m: f"0 */{m.group(1)} * * *"),
    # "every N minutes" -> "*/N * * * *"
    (re.compile(r"every\s+(\d+)\s*min(?:ute)?s?", re.IGNORECASE),
     lambda m: f"*/{m.group(1)} * * * *"),
    # "every N days" -> "0 0 */N * *"
    (re.compile(r"every\s+(\d+)\s*days?", re.IGNORECASE),
     lambda m: f"0 0 */{m.group(1)} * *"),
    # "daily (at H)" -> "0 H * * *"
    (re.compile(r"\bdaily(?: at (\d{1,2})(?::(\d{2}))?)?", re.IGNORECASE),
     lambda m: f"0 {m.group(1) or 9}:00 * * *"),
    # "hourly" -> "0 * * * *"
    (re.compile(r"\bhourly", re.IGNORECASE),
     lambda _: "0 * * * *"),
    # "once" (one-shot, no cron)
    (re.compile(r"\bonce\b", re.IGNORECASE),
     lambda _: None),
]


def _parse_schedule(text: str) -> Optional[str]:
    """Extract a cron expression from natural-language schedule hints."""
    for pattern, builder in _SCHEDULE_PATTERNS:
        m = pattern.search(text)
        if m is not None:
            result = builder(m)
            if result is None:
                return None  # explicit 'once' — no schedule
            return result
    return None


def _extract_name(text: str) -> str:
    """Derive an agent name from the description text.

    Heuristic: take the first 3 meaningful words, lowercase, hyphenated.
    """
    cleaned = re.sub(r"[^\w\s]", "", text)
    words = [w for w in cleaned.split() if w.lower() not in (
        "a", "an", "the", "it", "to", "for", "of", "in", "on", "at",
        "that", "this", "with", "from", "by", "and", "or", "is",
        "be", "are", "was", "were", "been",
    ) and len(w) > 1]
    if not words:
        return "unnamed-agent"
    slug = "-".join(words[:4]).lower()
    # strip trailing punctuation
    slug = slug.rstrip(".,;:")
    return slug[:48]


def _extract_skills(text: str) -> List[str]:
    """Extract skill names from phrases like 'using skills X,Y,Z' or 'with X skill'."""
    skills = []
    m = re.search(r"using skills?[: ]([a-z0-9_, -]+)", text, re.IGNORECASE)
    if m:
        raw = m.group(1)
        skills = [s.strip() for s in re.split(r"[,;]", raw) if s.strip()]
    return skills


def _extract_tools(text: str) -> List[str]:
    """Extract tool names from phrases like 'with tools X,Y,Z'."""
    tools = []
    m = re.search(r"(?:using|with)\s+tools?[: ]([a-z0-9_, -]+)", text, re.IGNORECASE)
    if m:
        raw = m.group(1)
        tools = [t.strip() for t in re.split(r"[,;]", raw) if t.strip()]
    return tools


def create_agent_from_description(description: str) -> AgentSpec:
    """Parse a natural-language description into an AgentSpec and build it.

    This is deliberately simple keyword-based (not LLM-dependent).
    It looks for:
      - "every X hours/days/minutes" → cron schedule
      - "using skills X,Y,Z" → skill list
      - "with tools X,Y,Z" → tool list
      - The first meaningful words → agent name
      - Everything else → description + goal
    """
    name = _extract_name(description)
    cron_schedule = _parse_schedule(description)
    skills = _extract_skills(description)
    tools = _extract_tools(description)

    # Strip the matched phrases from the description to build a clean goal
    goal_text = description
    for phrase_re in [
        r"every\s+\d+\s*(?:hours?|min(?:ute)?s?|days?)[^.,;]*[,.;]?",
        r"\bdaily(?: at \d+(?::\d{2})?)?[.,;]?",
        r"\bhourly[.,;]?",
        r"\bonce[.,;]?",
        r"using\s+skills?[: ][a-z0-9_, -]+[,.;]?",
        r"(?:using|with)\s+tools?[: ][a-z0-9_, -]+[,.;]?",
    ]:
        goal_text = re.sub(phrase_re, "", goal_text, flags=re.IGNORECASE).strip()
    goal_text = re.sub(r"\s+", " ", goal_text).strip()
    goal_text = goal_text.strip(".,;:")

    spec = AgentSpec(
        name=name,
        description=description,
        goal=goal_text or description,
        cron_schedule=cron_schedule,
        skills=skills,
        tools=tools,
    )
    return spec


# =============================================================================
# Build / Create / Delete / List
# =============================================================================

def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _agents_dir() -> Path:
    _ensure_dir(AGENTS_DIR)
    return AGENTS_DIR


def _skill_dir_for(name: str) -> Path:
    return SKILLS_BASE / name


def _agent_def_path(name: str) -> Path:
    return _agents_dir() / f"{name}.json"


def build_agent(spec: AgentSpec) -> dict:
    """Create an agent from its spec.

    Steps:
      1. Create skill directory under ~/.openamer/skills/<name>/
      2. Write SKILL.md from description + goal
      3. Create a cron job if schedule is provided
      4. Write the agent definition JSON
    """
    name = spec.name
    agents_dir = _agents_dir()

    # --- Step 1: Skill directory ---
    skill_dir = _skill_dir_for(name)
    _ensure_dir(skill_dir)

    # --- Step 2: Write SKILL.md ---
    skill_path = skill_dir / "SKILL.md"
    skill_content = _skill_content(spec)
    skill_path.write_text(skill_content, encoding="utf-8")

    # --- Step 3: Cron job (if scheduled) ---
    cron_job_id = None
    if spec.cron_schedule:
        try:
            from cron.jobs import create_job as _create_cron_job
            job = _create_cron_job(
                prompt=spec.goal,
                schedule=spec.cron_schedule,
                name=f"agent-{name}",
                skills=spec.skills or None,
            )
            cron_job_id = job.get("id", job.get("job_id"))
        except Exception as exc:
            # Cron creation is best-effort; don't fail the whole build
            cron_job_id = f"error:{exc}"

    # --- Step 4: Agent definition JSON ---
    agent_def = spec.to_dict()
    agent_def["cron_job_id"] = cron_job_id
    agent_def_path = _agent_def_path(name)

    agent_def_path.write_text(
        json.dumps(agent_def, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    return agent_def


def list_agents() -> List[dict]:
    """List all created agents by reading their JSON definitions."""
    agents_dir = _agents_dir()
    if not agents_dir.exists():
        return []

    agents: List[dict] = []
    for fpath in sorted(agents_dir.iterdir()):
        if fpath.suffix == ".json":
            try:
                data = json.loads(fpath.read_text(encoding="utf-8"))
                agents.append(data)
            except (json.JSONDecodeError, IOError):
                continue
    return agents


def show_agent(name: str) -> Optional[dict]:
    """Show a single agent's definition."""
    path = _agent_def_path(name)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, IOError):
        return None


def delete_agent(name: str) -> bool:
    """Remove an agent's definition JSON and its skill directory.

    If the agent had a cron job, also delete that.

    Returns True if the agent was found and removed, False otherwise.
    """
    found = False

    # Remove agent definition JSON
    def_path = _agent_def_path(name)
    if def_path.exists():
        # Load it first to get cron_job_id
        try:
            agent_data = json.loads(def_path.read_text(encoding="utf-8"))
            cron_job_id = agent_data.get("cron_job_id")
        except (json.JSONDecodeError, IOError):
            cron_job_id = None
        def_path.unlink()
        found = True
    else:
        cron_job_id = None

    # Remove skill directory
    skill_dir = _skill_dir_for(name)
    if skill_dir.exists():
        shutil.rmtree(skill_dir, ignore_errors=True)
        found = True

    # Remove cron job if one was associated
    if cron_job_id and isinstance(cron_job_id, str) and not cron_job_id.startswith("error:"):
        try:
            from cron.jobs import delete_job as _delete_cron_job
            _delete_cron_job(cron_job_id)
        except Exception:
            pass  # Best-effort

    return found