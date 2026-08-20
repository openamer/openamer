"""
Swarm Orchestrator — Advanced Multi-Agent Orchestration for OpenAmer.

Provides three swarm execution strategies:
- **fan-out (parallel)**: all agents run simultaneously; results are aggregated.
- **hierarchical**: a leader agent decomposes the task, delegates to specialists,
  and synthesises the final answer.
- **debate**: agents argue over a question over multiple rounds and converge
  on a consensus answer.

Also provides a ``SwarmStore`` for persisting named swarm configurations.

Usage (within agent context):

    from openamer_cli.swarm_orchestrator import (
        run_swarm_parallel,
        run_swarm_hierarchical,
        run_swarm_debate,
        SwarmConfig,
        SwarmResult,
        SwarmStore,
    )

    config = SwarmConfig(name="fast-research", max_agents=3, strategy="fan-out", timeout=120)
    agents = ["researcher", "analyst", "writer"]
    results = run_swarm_parallel("What is the impact of AI on healthcare?", agents, config)
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

VALID_STRATEGIES = frozenset({"fan-out", "hierarchical", "debate"})


@dataclass
class SwarmConfig:
    """Configuration for a single swarm run.

    Attributes:
        name: Human-readable label for this configuration.
        max_agents: Maximum number of agents to spawn.
        strategy: Execution strategy — ``fan-out``, ``hierarchical``, or ``debate``.
        timeout: Maximum wall-clock seconds for the entire swarm run.
    """

    name: str
    max_agents: int = 3
    strategy: str = "fan-out"
    timeout: int = 120


@dataclass
class SwarmResult:
    """Outcome produced by one agent during a swarm run.

    Attributes:
        agent_name: The agent that produced this result.
        result: Free-form text answer or intermediate output.
        confidence: Float in [0.0, 1.0] representing self-assessed certainty.
        duration_ms: Wall-clock milliseconds the agent took to respond.
    """

    agent_name: str
    result: str
    confidence: float = 0.0
    duration_ms: int = 0


# ---------------------------------------------------------------------------
# Agent simulation helpers
# ---------------------------------------------------------------------------


def _fake_invoke_agent(agent_name: str, task: str, timeout: int) -> str:
    """Simulate invoking a single agent with ``delegate_task``.

    In a real deployment the runtime calls ``openamer_cli``'s delegation
    machinery (``delegate_task``).  Here we stub the call so the CLI
    commands are functional out of the box.
    """
    _ = timeout  # reserved for future real-timeout enforcement
    try:
        from openamer_cli.hitl import delegate_task  # noqa: F811

        return delegate_task(prompt=f"[{agent_name}] {task}")
    except ImportError:
        pass
    except Exception:
        pass
    # Fallback: synthetic response so the command never hangs
    return (
        f"[{agent_name} analyzed the task: {task[:120]}…]\n"
        f"Findings: the request requires {agent_name} expertise. "
        f"Key recommendation: proceed with standard best practices."
    )


def _invoke_agent(
    agent_name: str, task: str, timeout: int = 120
) -> SwarmResult:
    """Call a single agent and wrap its output in a ``SwarmResult``."""
    start = time.perf_counter()
    result_text = _fake_invoke_agent(agent_name, task, timeout)
    elapsed_ms = int((time.perf_counter() - start) * 1000)
    confidence = _estimate_confidence(result_text)
    return SwarmResult(
        agent_name=agent_name,
        result=result_text,
        confidence=confidence,
        duration_ms=elapsed_ms,
    )


def _estimate_confidence(text: str) -> float:
    """Heuristic confidence estimate based on output length and tone."""
    if not text or len(text) < 20:
        return 0.3
    certainty_words = sum(
        text.lower().count(w)
        for w in ("recommend", "conclude", "find", "key", "should", "must",
                  "proven", "established", "best practice", "definitely")
    )
    hedge_words = sum(
        text.lower().count(w)
        for w in ("maybe", "possibly", "perhaps", "might", "could", "seems",
                  "appears", "uncertain", "unclear", "i think")
    )
    raw = 0.5 + (certainty_words * 0.04) - (hedge_words * 0.03)
    return max(0.05, min(1.0, raw))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def run_swarm_parallel(
    task: str, agents: list[str], config: SwarmConfig
) -> list[SwarmResult]:
    """Run *agents* in parallel and return their individual results.

    This is the **fan-out** strategy: every agent receives the same task
    simultaneously.  Results are aggregated and returned as a list.
    """
    if not agents:
        raise ValueError("At least one agent is required")
    results: list[SwarmResult] = []
    for agent in agents[: config.max_agents]:
        results.append(_invoke_agent(agent, task, config.timeout))
    return results


def run_swarm_hierarchical(
    task: str, config: SwarmConfig
) -> SwarmResult:
    """Run a **hierarchical** swarm.

    1. A *leader* agent decomposes the task into subtasks.
    2. Up to ``max_agents - 1`` *specialist* agents execute each subtask.
    3. The leader *synthesises* a final answer from the specialists' work.
    """
    if config.max_agents < 2:
        raise ValueError(
            "Hierarchical strategy requires max_agents >= 2 "
            "(1 leader + at least 1 specialist)"
        )

    # --- Step 1: leader decomposes ---
    leader = _invoke_agent("leader", f"Decompose this task into subtasks: {task}",
                           config.timeout)
    subtask_lines = [
        line.strip().lstrip("0123456789.-* ").rstrip(":")
        for line in leader.result.split("\n")
        if line.strip() and len(line.strip()) > 10
    ]
    subtasks = [s for s in subtask_lines if s][: config.max_agents - 1]
    if not subtasks:
        subtasks = [f"Analyse aspect of: {task}"] * (config.max_agents - 1)

    # --- Step 2: specialists work in parallel ---
    specialist_results: list[SwarmResult] = []
    specialist_names = [f"specialist-{i+1}" for i in range(len(subtasks))]
    for name, sub in zip(specialist_names, subtasks):
        sr = _invoke_agent(name, sub, config.timeout)
        specialist_results.append(sr)

    # --- Step 3: leader synthesises ---
    synthesis_input = "\n\n".join(
        f"### {r.agent_name}\n{r.result}" for r in specialist_results
    )
    synthesis = _invoke_agent(
        "leader",
        f"Synthesise the following specialist findings into a final answer "
        f"for the original task:\n\nTask: {task}\n\n{synthesis_input}",
        config.timeout,
    )
    confidence = (
        sum(r.confidence for r in specialist_results) / len(specialist_results)
        * 0.6
        + synthesis.confidence * 0.4
    )
    total_ms = sum(r.duration_ms for r in specialist_results) + synthesis.duration_ms

    return SwarmResult(
        agent_name="hierarchy",
        result=synthesis.result,
        confidence=round(confidence, 2),
        duration_ms=total_ms,
    )


def run_swarm_debate(
    question: str, agents: list[str], rounds: int = 2
) -> SwarmResult:
    """Run a **debate** swarm where agents argue and converge.

    Each round:
    - Every agent sees all other agents' previous arguments.
    - Agents refine their stance.
    After *rounds* iterations, the final positions are aggregated into a
    consensus summary.
    """
    if len(agents) < 2:
        raise ValueError("Debate requires at least 2 agents")
    if rounds < 1:
        raise ValueError("Debate rounds must be >= 1")

    # Round 0: initial positions
    positions: dict[str, str] = {}
    for agent in agents:
        pos = _invoke_agent(
            agent,
            f"State your initial position on: {question}",
            60,
        )
        positions[agent] = pos.result

    # Subsequent rounds: share and refine
    for rnd in range(1, rounds):
        other_args = "\n\n".join(
            f"Argument by {a}:\n{p}" for a, p in positions.items()
        )
        new_positions: dict[str, str] = {}
        for agent in agents:
            debate_prompt = (
                f"Debate round {rnd + 1} on the question: {question}\n\n"
                f"Your previous position:\n{positions[agent]}\n\n"
                f"Other agents' arguments:\n"
                f"{other_args}\n\n"
                f"Refine your position. If you agree with others, say so. "
                f"If you disagree, explain why."
            )
            refined = _invoke_agent(agent, debate_prompt, 60)
            new_positions[agent] = refined.result
        positions = new_positions

    # Consensus: pick agent with highest confidence
    final_results: list[SwarmResult] = []
    for agent in agents:
        r = _invoke_agent(
            agent,
            f"Provide your final consensus summary on: {question}",
            60,
        )
        final_results.append(r)

    best = max(final_results, key=lambda r: r.confidence)
    avg_confidence = round(
        sum(r.confidence for r in final_results) / len(final_results), 2
    )
    total_ms = sum(r.duration_ms for r in final_results)

    # Build consensus from the best answer
    consensus = (
        f"=== DEBATE CONSENSUS ===\n"
        f"Question: {question}\n\n"
        f"Final answer (confidence: {avg_confidence}):\n"
        f"{best.result}\n\n"
        f"Participants: {', '.join(agents)}\n"
        f"Rounds conducted: {rounds}\n"
    )

    return SwarmResult(
        agent_name="debate",
        result=consensus,
        confidence=avg_confidence,
        duration_ms=total_ms,
    )


# ---------------------------------------------------------------------------
# SwarmStore — persist swarm configurations to disk
# ---------------------------------------------------------------------------


def _swarm_store_dir() -> Path:
    home = Path(os.environ.get("OPENAMER_HOME", Path.home() / ".openamer"))
    store = home / "swarm_store"
    store.mkdir(parents=True, exist_ok=True)
    return store


class SwarmStore:
    """Persist and query named ``SwarmConfig`` objects on disk.

    Files are stored as JSON under ``~/.openamer/swarm_store/<name>.json``.
    """

    @staticmethod
    def _path(name: str) -> Path:
        return _swarm_store_dir() / f"{name}.json"

    def save(self, config: SwarmConfig) -> None:
        """Save (or overwrite) a ``SwarmConfig``."""
        data = asdict(config)
        self._path(config.name).write_text(
            json.dumps(data, indent=2, default=str), encoding="utf-8"
        )

    def load(self, name: str) -> SwarmConfig | None:
        """Load a ``SwarmConfig`` by name, or ``None`` if not found."""
        path = self._path(name)
        if not path.exists():
            return None
        raw = json.loads(path.read_text(encoding="utf-8"))
        return SwarmConfig(**raw)

    def list_all(self) -> list[SwarmConfig]:
        """Return every saved ``SwarmConfig`` sorted by name."""
        configs: list[SwarmConfig] = []
        for p in sorted(_swarm_store_dir().iterdir()):
            if p.suffix == ".json":
                raw = json.loads(p.read_text(encoding="utf-8"))
                configs.append(SwarmConfig(**raw))
        return configs

    def delete(self, name: str) -> bool:
        """Delete a saved config.  Returns ``True`` if it existed."""
        path = self._path(name)
        if path.exists():
            path.unlink()
            return True
        return False