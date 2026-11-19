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
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
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
    # Wall-clock milliseconds the agent took to respond. A float, not an int:
    # truncating to whole milliseconds reports 0 for anything faster than 1 ms
    # (every mocked/fast agent), which makes "the timer ran" indistinguishable
    # from "nothing was measured".
    duration_ms: float = 0.0


# ---------------------------------------------------------------------------
# Agent simulation helpers
# ---------------------------------------------------------------------------


def _openamer_python() -> str:
    """Interpreter for child agent runs: the install's venv, else the current one."""
    home = os.environ.get("OPENAMER_HOME", "")
    candidate = Path(home) / "openamer-agent" / "venv" / "Scripts" / "python.exe"
    if candidate.is_file():
        return str(candidate)
    return sys.executable


def _invoke_agent_real(agent_name: str, task: str, timeout: int) -> str:
    """Run ONE real agent turn and return its answer.

    Spawned as a subprocess (``python -m openamer_cli.main -z <prompt> --yolo``)
    because the in-process delegation API (``tools.delegate_tool.delegate_task``)
    requires a *parent agent context* that the swarm CLI does not have. The
    previous implementation imported a non-existent ``openamer_cli.hitl.delegate_task``,
    swallowed the ImportError, and then returned a canned paragraph for every
    agent -- in 0 ms, with a hardcoded ~66% confidence, which made a swarm run
    look successful while no agent had run at all. That fabricated-findings path
    is gone on purpose.

    Raises RuntimeError when the agent produces nothing, so the caller can report
    an explicit failure instead of inventing a result.
    """
    home = os.environ.get("OPENAMER_HOME") or os.getcwd()
    env = dict(os.environ, OPENAMER_HOME=home, PYTHONIOENCODING="utf-8")
    proc = subprocess.run(
        [
            _openamer_python(), "-m", "openamer_cli.main",
            "-z", f"[{agent_name}] {task}", "--yolo",
        ],
        cwd=home, env=env, capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=timeout,
    )
    out = (proc.stdout or "").strip()
    if out:
        return out
    err = (proc.stderr or "").strip()[-300:]
    raise RuntimeError(
        f"Agent {agent_name!r} lieferte keine Ausgabe (exit {proc.returncode}): {err}"
    )


def _invoke_agent(
    agent_name: str, task: str, timeout: int = 120
) -> SwarmResult:
    """Run one real agent and wrap its output in a ``SwarmResult``.

    A failed agent yields an explicit UNAVAILABLE marker with confidence 0.0 --
    never a plausible-sounding paragraph. A fabricated finding is worse than a
    visible failure, because it survives into the aggregate answer.
    """
    start = time.perf_counter()
    try:
        result_text = _invoke_agent_real(agent_name, task, timeout)
    except Exception as exc:  # noqa: BLE001 - surfacing the failure is the point
        elapsed_ms = round((time.perf_counter() - start) * 1000, 3)
        return SwarmResult(
            agent_name=agent_name,
            result=(
                f"DELEGATION UNAVAILABLE ({type(exc).__name__}: {exc}) - kein Agent "
                f"ist gelaufen. Diese Zeile ist keine Antwort und darf nicht als "
                f"Ergebnis verwendet werden."
            ),
            confidence=0.0,
            duration_ms=elapsed_ms,
        )
    elapsed_ms = round((time.perf_counter() - start) * 1000, 3)
    return SwarmResult(
        agent_name=agent_name,
        result=result_text,
        confidence=_estimate_confidence(result_text),
        duration_ms=elapsed_ms,
    )


def _estimate_confidence(text: str) -> float:
    """Heuristic confidence estimate based on output length and tone.

    Language: the word lists are English AND German on purpose. Measured
    2026-11-19 on a live debate run -- a correct German answer ("91 = 7 x 13,
    also ... ERGEBNIS: NEIN") scored exactly the 0.5 base, because not a single
    English marker matched. For a German-speaking user that makes the reported
    confidence carry no information at all, so the same markers exist in German.
    """
    if not text or len(text) < 20:
        return 0.3
    lowered = text.lower()
    certainty_words = sum(
        lowered.count(w)
        for w in ("recommend", "conclude", "find", "key", "should", "must",
                  "proven", "established", "best practice", "definitely",
                  # German
                  "empfohlen", "schlussfolg", "ergebnis", "bewiesen", "eindeutig",
                  "definitiv", "muss", "sollte", "klar", "sicher")
    )
    hedge_words = sum(
        lowered.count(w)
        for w in ("maybe", "possibly", "perhaps", "might", "could", "seems",
                  "appears", "uncertain", "unclear", "i think",
                  # German
                  "vielleicht", "moeglicherweise", "möglicherweise", "koennte",
                  "könnte", "scheint", "unsicher", "unklar", "vermutlich",
                  "ich denke")
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
    selected = list(agents[: config.max_agents])
    results: list[SwarmResult] = []
    # Real fan-out: the agents run concurrently. The previous version looped over
    # them sequentially, so "parallel" was a label rather than a property.
    with ThreadPoolExecutor(max_workers=max(1, len(selected))) as pool:
        futures = [
            pool.submit(_invoke_agent, agent, task, config.timeout)
            for agent in selected
        ]
        for future in futures:
            results.append(future.result())
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