"""
Crew Orchestrator — Multi-Agent Orchestration for OpenAmer.

CrewAI-style role-based agent teams. Users define "crews" with multiple agents
that have different roles (researcher, writer, analyst) and they collaborate
on a task.

Usage (within agent context):
    from openamer_cli.crew_orchestrator import run_crew, CrewStore, Crew, CrewMember

    crew = Crew(
        name="research-writer",
        members=[
            CrewMember(name="Alice", role="researcher", goal="Find facts", backstory=""),
            CrewMember(name="Bob", role="writer", goal="Write report", backstory=""),
        ],
        task="default",
        output_format="markdown",
    )
    store = CrewStore()
    store.save(crew)
    result = run_crew("research-writer", "Research quantum computing")
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

VALID_ROLES = frozenset({"researcher", "writer", "analyst", "coder", "reviewer"})


@dataclass
class CrewMember:
    """A single agent in a crew."""

    name: str
    role: str  # researcher | writer | analyst | coder | reviewer
    goal: str = ""
    backstory: str = ""

    def __post_init__(self):
        if self.role not in VALID_ROLES:
            raise ValueError(
                f"Invalid role {self.role!r}. Must be one of {sorted(VALID_ROLES)}"
            )


@dataclass
class Crew:
    """A crew definition — a team of agents working on a task."""

    name: str
    members: List[CrewMember] = field(default_factory=list)
    task: str = ""
    output_format: str = "markdown"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "members": [asdict(m) for m in self.members],
            "task": self.task,
            "output_format": self.output_format,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Crew":
        members = [CrewMember(**m) for m in data.get("members", [])]
        return cls(
            name=data.get("name", ""),
            members=members,
            task=data.get("task", ""),
            output_format=data.get("output_format", "markdown"),
        )


# ---------------------------------------------------------------------------
# CrewStore — JSON persistence under OPENAMER_HOME/crews/
# ---------------------------------------------------------------------------


def _openamer_home() -> Path:
    """Resolve OPENAMER_HOME, falling back to the default platform path."""
    env = os.environ.get("OPENAMER_HOME") or ""
    if env:
        return Path(env)
    # Default: ~/.openamer on Linux/macOS, %LOCALAPPDATA%/openamer-laptop on Windows
    if sys.platform == "win32":
        return Path(os.environ.get("LOCALAPPDATA", "")) / "openamer-laptop"
    return Path.home() / ".openamer"


CREWS_DIR = _openamer_home() / "crews"


class CrewStore:
    """Save/load/list/delete crew definitions as JSON files."""

    def __init__(self, crews_dir: Optional[Path] = None):
        self._crews_dir = crews_dir or CREWS_DIR
        self._crews_dir.mkdir(parents=True, exist_ok=True)

    def save(self, crew: Crew) -> Path:
        """Persist a crew to a JSON file. Returns the file path."""
        path = self._path_for(crew.name)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(crew.to_dict(), f, indent=2, ensure_ascii=False)
        return path

    def load(self, name: str) -> Crew:
        """Load a crew by name. Raises FileNotFoundError if missing."""
        path = self._path_for(name)
        if not path.exists():
            raise FileNotFoundError(f"Crew {name!r} not found at {path}")
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return Crew.from_dict(data)

    def list(self) -> List[str]:
        """Return sorted list of crew names."""
        names = []
        for p in self._crews_dir.glob("*.json"):
            names.append(p.stem)
        return sorted(names)

    def delete(self, name: str) -> bool:
        """Delete a crew definition. Returns True if deleted, False if not found."""
        path = self._path_for(name)
        if path.exists():
            path.unlink()
            return True
        return False

    def _path_for(self, name: str) -> Path:
        """Return the JSON file path for a crew name."""
        # Sanitize name for filesystem
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in name)
        return self._crews_dir / f"{safe}.json"


# ---------------------------------------------------------------------------
# Run helpers — build prompts for each role
# ---------------------------------------------------------------------------

_ROLE_SYSTEM_PROMPTS: Dict[str, str] = {
    "researcher": (
        "You are a thorough researcher. Your job is to gather facts, data, "
        "and insights on the given topic. Be comprehensive and cite sources "
        "where possible."
    ),
    "writer": (
        "You are a skilled writer. Your job is to take research findings and "
        "craft clear, well-structured, and engaging content. Adapt your style "
        "to the audience and format specified."
    ),
    "analyst": (
        "You are a sharp analyst. Your job is to examine the provided content, "
        "identify patterns, strengths, weaknesses, and key insights. Provide "
        "actionable recommendations."
    ),
    "coder": (
        "You are an experienced software engineer. Your job is to write clean, "
        "well-documented, and efficient code. Follow best practices for the "
        "language and framework specified."
    ),
    "reviewer": (
        "You are a meticulous code/content reviewer. Your job is to examine "
        "the provided work for issues, bugs, style problems, and areas for "
        "improvement. Provide specific, actionable feedback."
    ),
}


def _build_member_prompt(member: CrewMember, task: str, previous_output: Optional[str] = None) -> str:
    """Build a full prompt for a single crew member."""
    system = _ROLE_SYSTEM_PROMPTS.get(member.role, f"You are a {member.role}.")
    prompt_parts = [
        f"# Role: {member.role.title()}",
        f"## Goal",
        member.goal or f"Complete your role as {member.role} for the given task.",
    ]
    if member.backstory:
        prompt_parts.append(f"## Backstory\n{member.backstory}")
    prompt_parts.append(f"## System Prompt\n{system}")
    prompt_parts.append(f"## Task\n{task}")
    if previous_output:
        prompt_parts.append(f"## Previous Context\n{previous_output}")
    prompt_parts.append(
        f"\nPlease complete your role as {member.role}. "
        f"Return your work in {member.role}-specific output format."
    )
    return "\n\n".join(prompt_parts)


def _delegate_task_via_subprocess(goal: str, context: str, max_iterations: int = 10) -> str:
    """Execute a task by spawning a one-shot agent subprocess.

    Used when running from the CLI without an active agent session.
    Calls ``openamer -z <prompt>``.
    """
    prompt = f"{context}\n\n{goal}"
    try:
        result = subprocess.run(
            [sys.executable, "-m", "openamer_cli", "-z", prompt],
            capture_output=True,
            text=True,
            timeout=300,
        )
        output = result.stdout.strip()
        if not output and result.stderr:
            output = result.stderr.strip()
        return output or f"[No output from sub-agent for: {goal[:60]}...]"
    except subprocess.TimeoutExpired:
        return f"[Timeout: sub-agent exceeded 300s for: {goal[:60]}...]"
    except Exception as e:
        return f"[Error running sub-agent: {e}]"


# ---------------------------------------------------------------------------
# Run crew — main orchestrator
# ---------------------------------------------------------------------------


def run_crew(
    crew_name: str,
    task: str,
    *,
    mode: str = "sequential",
    parent_agent: Any = None,
    max_iterations: int = 10,
) -> str:
    """Execute a crew workflow.

    Parameters
    ----------
    crew_name : str
        Name of the crew to run (must exist in CrewStore).
    task : str
        The task description to execute.
    mode : str
        "sequential" (default) or "parallel".
    parent_agent : optional
        If provided, uses delegate_task for sub-agent creation.
        Otherwise uses subprocess-based execution.
    max_iterations : int
        Max iterations for each sub-agent.

    Returns
    -------
    str
        The final output from the crew pipeline.
    """
    store = CrewStore()
    crew = store.load(crew_name)

    if mode == "parallel":
        return run_crew_parallel(crew, task, parent_agent=parent_agent, max_iterations=max_iterations)
    else:
        return run_crew_sequential(crew, task, parent_agent=parent_agent, max_iterations=max_iterations)


def run_crew_sequential(
    crew: Crew,
    task: str,
    *,
    parent_agent: Any = None,
    max_iterations: int = 10,
) -> str:
    """Run crew members one by one, piping each output as context to the next.

    The canonical order is: researcher -> writer -> analyst -> coder -> reviewer.
    Missing roles are skipped.
    """
    order = ["researcher", "writer", "analyst", "coder", "reviewer"]
    members_by_role: Dict[str, CrewMember] = {m.role: m for m in crew.members}

    current_context = task
    results: List[str] = []

    for role in order:
        member = members_by_role.get(role)
        if member is None:
            continue

        prompt = _build_member_prompt(member, task, previous_output=current_context)
        result = _run_single_member(member, prompt, parent_agent=parent_agent, max_iterations=max_iterations)
        results.append(result)
        current_context = result

    return _format_crew_output(crew, task, results)


def run_crew_parallel(
    crew: Crew,
    task: str,
    *,
    parent_agent: Any = None,
    max_iterations: int = 10,
) -> str:
    """Run independent crew members in parallel, then aggregate results.

    Researcher, coder, and analyst are run in parallel (they're independent).
    Writer runs after researcher (needs research output).
    Reviewer runs last (reviews everything).
    """
    independent_roles = ["researcher", "analyst", "coder"]
    dependent_roles = ["writer", "reviewer"]

    members_by_role: Dict[str, CrewMember] = {m.role: m for m in crew.members}

    # Phase 1: run independent members in parallel
    import concurrent.futures

    phase1_results: Dict[str, str] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(independent_roles)) as executor:
        futures = {}
        for role in independent_roles:
            member = members_by_role.get(role)
            if member is None:
                continue
            prompt = _build_member_prompt(member, task)
            futures[executor.submit(_run_single_member, member, prompt, parent_agent, max_iterations)] = role

        for future in concurrent.futures.as_completed(futures):
            role = futures[future]
            phase1_results[role] = future.result()

    # Phase 2: combine results for writer
    combined_context = task
    if phase1_results:
        combined_context += "\n\n## Research & Analysis Input\n"
        for role, result in phase1_results.items():
            combined_context += f"\n### {role.title()}\n{result}\n"

    # Run writer if present
    writer_member = members_by_role.get("writer")
    writer_output = ""
    if writer_member:
        writer_prompt = _build_member_prompt(writer_member, task, previous_output=combined_context)
        writer_output = _run_single_member(writer_member, writer_prompt, parent_agent, max_iterations)

    # Phase 3: review
    reviewer_member = members_by_role.get("reviewer")
    reviewer_output = ""
    if reviewer_member:
        review_context = writer_output or combined_context
        reviewer_prompt = _build_member_prompt(reviewer_member, task, previous_output=review_context)
        reviewer_output = _run_single_member(reviewer_member, reviewer_prompt, parent_agent, max_iterations)

    all_results = list(phase1_results.values())
    if writer_output:
        all_results.append(writer_output)
    if reviewer_output:
        all_results.append(reviewer_output)

    return _format_crew_output(crew, task, all_results)


def _run_single_member(
    member: CrewMember,
    prompt: str,
    *,
    parent_agent: Any = None,
    max_iterations: int = 10,
) -> str:
    """Execute a single crew member's task.

    Uses ``delegate_task`` when ``parent_agent`` is available (agent context).
    Falls back to subprocess oneshot for CLI context.
    """
    if parent_agent is not None:
        return _run_via_delegate_task(member, prompt, parent_agent, max_iterations)
    return _delegate_task_via_subprocess(
        goal=f"{member.role.title()}: {member.goal or member.role}",
        context=prompt,
        max_iterations=max_iterations,
    )


def _run_via_delegate_task(
    member: CrewMember,
    prompt: str,
    parent_agent: Any,
    max_iterations: int,
) -> str:
    """Run a crew member using the agent's delegate_task tool.

    The delegate_task function (tools.delegate_tool.delegate_task) requires
    a ``parent_agent`` which is the currently running agent instance.
    """
    try:
        from tools.delegate_tool import delegate_task as _delegate

        result_json = _delegate(
            goal=f"{member.role.title()}: {member.goal or member.role}",
            context=prompt,
            role="leaf",
            max_iterations=max_iterations,
            parent_agent=parent_agent,
        )
        result = json.loads(result_json)
        if isinstance(result, dict):
            # Extract the actual content from delegate_task response
            tasks = result.get("tasks") or result.get("results") or []
            if tasks:
                outputs = []
                for t in tasks:
                    content = t.get("result") or t.get("content") or t.get("output") or json.dumps(t)
                    outputs.append(str(content))
                return "\n\n---\n\n".join(outputs)
            content = result.get("result") or result.get("content") or result.get("output") or result.get("error") or ""
            return str(content)
        return str(result)
    except Exception as e:
        return f"[delegate_task failed: {e}]"


def _format_crew_output(crew: Crew, task: str, results: List[str]) -> str:
    """Format the final output of a crew run."""
    lines = [
        f"# Crew: {crew.name}",
        f"**Task:** {task}",
        f"**Format:** {crew.output_format}",
        "",
        "---",
        "",
    ]

    members_by_role: Dict[str, CrewMember] = {m.role: m for m in crew.members}
    for i, role in enumerate(["researcher", "writer", "analyst", "coder", "reviewer"]):
        member = members_by_role.get(role)
        if member is None:
            continue
        lines.append(f"## {role.title()}: {member.name}")
        lines.append("")
        if i < len(results):
            lines.append(results[i])
        else:
            lines.append("*(no output)*")
        lines.append("")

    lines.append("---")
    lines.append("*Crew orchestration complete.*")
    return "\n".join(lines)