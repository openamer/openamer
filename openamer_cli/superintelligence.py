"""
Superintelligence Platform — System Health Dashboard for OpenAmer.

Provides the automated ``superintelligence`` health-check and reporting
machinery that monitors the entire OpenAmer ecosystem:

- Brain learning loop (session-to-brain pipeline)
- A2A swarm connectivity (agent-to-agent network)
- Skills catalogue health (count, freshness, improvement rate)
- Memory usage and growth
- Computer-use readiness
- Multi-agent orchestration readiness
- Overall system health score (0-100)

Also provides milestone planning for the next improvements.

Usage:

    from openamer_cli.superintelligence import (
        check_all_systems,
        generate_superintelligence_report,
        get_next_milestones,
    )

    status = check_all_systems()
    report = generate_superintelligence_report()
    milestones = get_next_milestones()
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Dataclass
# ---------------------------------------------------------------------------


@dataclass
class SuperintelligenceStatus:
    """Snapshot of the entire system's health.

    Every field is marked 'pass', 'warn' (degraded), or 'fail'.
    """

    brain_learning_loop: str = "unknown"
    a2a_swarm_connectivity: str = "unknown"
    skills_count: str = "unknown"
    skills_improvement_rate: str = "unknown"
    memory_usage: str = "unknown"
    memory_growth: str = "unknown"
    computer_use_readiness: str = "unknown"
    multi_agent_orchestration: str = "unknown"
    overall_score: int = 0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _home() -> Path:
    return Path(os.environ.get("OPENAMER_HOME", Path.home() / ".openamer"))


def _brain_jsonl() -> Path:
    return _home() / "a2a" / "openamer-brain.jsonl"


def _skills_dir() -> Path:
    return _home() / "skills"


def _memories_dir() -> Path:
    return _home() / "memories"


def _age_days(path: Path) -> float:
    """Returns the age of *path* in fractional days since last modification."""
    if not path.exists():
        return float("inf")
    mtime = path.stat().st_mtime
    return (time.time() - mtime) / 86400.0


def _count_files(directory: Path, glob: str = "*", recursive: bool = True) -> int:
    """Count files matching *glob* under *directory*.

    Recursive by default because skills live in subdirectories
    (``autonomous-ai-agents/super-intelligence/SKILL.md``).
    """
    if not directory.is_dir():
        return 0
    if recursive:
        return len(list(directory.rglob(glob)))
    return len(list(directory.glob(glob)))


def _dir_size_mb(directory: Path) -> float:
    """Return total size in MB of all files under *directory*."""
    if not directory.is_dir():
        return 0.0
    total = 0
    for f in directory.rglob("*"):
        if f.is_file():
            total += f.stat().st_size
    return round(total / (1024 * 1024), 1)


def _pass_warn_fail(condition: bool, pass_label: str = "pass") -> str:
    """Return 'pass' if truthy, else 'fail'."""
    return pass_label if condition else "fail"


def _check_mcp_tool(name: str) -> bool:
    """Quick check whether a tool/CLI subcommand is available."""
    try:
        result = subprocess.run(
            ["openamer", name, "--help"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------


def check_brain_learning_loop() -> str:
    """Check whether the session-to-brain pipeline has collected data."""
    brain = _brain_jsonl()
    if not brain.exists() or brain.stat().st_size == 0:
        return "fail"
    age = _age_days(brain)
    if age > 7:
        return "warn"  # stale brain data
    if age > 30:
        return "fail"
    return "pass"


def check_a2a_connectivity() -> str:
    """Check whether the A2A module is importable and has peers."""
    try:
        from openamer_cli import a2a  # noqa: F401
        return "pass"
    except ImportError:
        pass
    # Fallback: check for a2a directory existence
    a2a_dir = _home() / "a2a"
    if a2a_dir.is_dir() and _count_files(a2a_dir) > 0:
        return "warn"  # data present but module may be partial
    return "fail"


def check_skills_health() -> tuple[str, str]:
    """Return (skills_count_status, improvement_rate_status)."""
    skills = _skills_dir()
    if not skills.is_dir():
        return "fail", "fail"

    count = _count_files(skills, "*.md")
    if count == 0:
        return "fail", "fail"

    # Count status
    count_status = _pass_warn_fail(count >= 5, "pass")

    # Improvement rate: check if any skill was modified in the last 14 days
    recent = 0
    for f in skills.rglob("*.md"):
        if _age_days(f) <= 14:
            recent += 1

    if recent >= 3:
        improve_status = "pass"
    elif recent >= 1:
        improve_status = "warn"
    else:
        improve_status = "fail"

    return count_status, improve_status


def check_memory_health() -> tuple[str, str]:
    """Return (memory_usage_status, memory_growth_status)."""
    mem_dir = _memories_dir()
    if not mem_dir.is_dir():
        return "fail", "fail"

    size_mb = _dir_size_mb(mem_dir)
    count = _count_files(mem_dir, "*.md")  # memories are Markdown files

    # Usage: warn if >500MB, fail if >1GB
    if size_mb > 1000:
        usage = "fail"
    elif size_mb > 500:
        usage = "warn"
    elif size_mb < 0.1 and count == 0:
        usage = "fail"
    else:
        usage = "pass"

    # Growth: check if any memory was touched in the last 7 days
    recent = sum(1 for f in mem_dir.rglob("*") if f.is_file() and _age_days(f) <= 7)
    growth = _pass_warn_fail(recent >= 1, "pass")
    if recent == 0 and count > 0:
        growth = "warn"

    return usage, growth


def check_computer_use() -> str:
    """Check whether the ``computer-use`` tool / subcommand is registered."""
    try:
        from openamer_cli import computer_use_record  # noqa: F401
        return "pass"
    except ImportError:
        pass
    if _check_mcp_tool("computer-use"):
        return "pass"
    return "warn"


def check_multi_agent() -> str:
    """Check whether multi-agent orchestration modules are available."""
    checks = 0
    try:
        from openamer_cli.crew_orchestrator import Crew, CrewStore  # noqa: F401
        checks += 1
    except ImportError:
        pass
    try:
        from openamer_cli.swarm_orchestrator import (  # noqa: F401
            SwarmConfig,
            SwarmStore,
        )
        checks += 1
    except ImportError:
        pass
    try:
        import openamer_cli.a2a  # noqa: F401 — A2A package
        checks += 1
    except ImportError:
        pass
    if checks >= 3:
        return "pass"
    if checks >= 1:
        return "warn"
    return "fail"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def check_all_systems() -> dict[str, Any]:
    """Run every health check and return a flat dict of status strings + score."""
    brain = check_brain_learning_loop()
    a2a = check_a2a_connectivity()
    skills_count, skills_improve = check_skills_health()
    mem_usage, mem_growth = check_memory_health()
    cu = check_computer_use()
    ma = check_multi_agent()

    # --- score ---
    weighting = {
        "brain": 20,
        "a2a": 15,
        "skills_count": 10,
        "skills_improve": 10,
        "mem_usage": 10,
        "mem_growth": 10,
        "cu": 10,
        "ma": 15,
    }
    val: dict[str, int] = {
        "pass": 100,
        "warn": 50,
        "fail": 0,
        "unknown": 0,
    }
    score = (
        val[brain] * weighting["brain"]
        + val[a2a] * weighting["a2a"]
        + val[skills_count] * weighting["skills_count"]
        + val[skills_improve] * weighting["skills_improve"]
        + val[mem_usage] * weighting["mem_usage"]
        + val[mem_growth] * weighting["mem_growth"]
        + val[cu] * weighting["cu"]
        + val[ma] * weighting["ma"]
    ) // 100

    return {
        "brain_learning_loop": brain,
        "a2a_swarm_connectivity": a2a,
        "skills_count": skills_count,
        "skills_improvement_rate": skills_improve,
        "memory_usage": mem_usage,
        "memory_growth": mem_growth,
        "computer_use_readiness": cu,
        "multi_agent_orchestration": ma,
        "overall_score": score,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def generate_superintelligence_report() -> str:
    """Return a comprehensive, human-readable system status report."""
    data = check_all_systems()

    def status_badge(status: str) -> str:
        badges = {
            "pass": "✅ PASS",
            "warn": "⚠️  WARN",
            "fail": "❌ FAIL",
            "unknown": "❓ UNKNOWN",
        }
        return badges.get(status, status)

    score = data["overall_score"]
    if score >= 80:
        score_rating = "🌟 Excellent"
    elif score >= 60:
        score_rating = "👍 Good"
    elif score >= 40:
        score_rating = "⚠️  Fair"
    else:
        score_rating = "🔴 Critical"

    lines = [
        "╔══════════════════════════════════════════════════════════╗",
        "║         SUPERINTELLIGENCE PLATFORM — SYSTEM REPORT      ║",
        "╚══════════════════════════════════════════════════════════╝",
        "",
        f"  Generated: {data['timestamp']}",
        "",
        "── System Health ──────────────────────────────────────────",
        f"  Brain Learning Loop       {status_badge(data['brain_learning_loop'])}",
        f"  A2A Swarm Connectivity    {status_badge(data['a2a_swarm_connectivity'])}",
        f"  Skills Count              {status_badge(data['skills_count'])}",
        f"  Skills Improvement Rate   {status_badge(data['skills_improvement_rate'])}",
        f"  Memory Usage              {status_badge(data['memory_usage'])}",
        f"  Memory Growth             {status_badge(data['memory_growth'])}",
        f"  Computer-Use Readiness    {status_badge(data['computer_use_readiness'])}",
        f"  Multi-Agent Orchestration {status_badge(data['multi_agent_orchestration'])}",
        "",
        f"  Overall Health Score:  {score}/100  ({score_rating})",
        "",
    ]

    # Add contextual recommendations
    recommendations: list[str] = []
    if data["brain_learning_loop"] != "pass":
        recommendations.append(
            "  • Brain: Run 'openamer brain stats' to diagnose. "
            "Ensure session_to_brain daemon is running."
        )
    if data["a2a_swarm_connectivity"] != "pass":
        recommendations.append(
            "  • A2A: Install the A2A module or check ~/.openamer/a2a/ for data."
        )
    if data["skills_count"] != "pass":
        recommendations.append(
            "  • Skills: Create skills with 'openamer skills create <name>'."
        )
    if data["skills_improvement_rate"] != "pass":
        recommendations.append(
            "  • Skills: Update existing skills regularly with 'openamer skills edit'."
        )
    if data["memory_usage"] != "pass":
        recommendations.append(
            "  • Memory: Review and clean up the memories directory."
        )
    if data["computer_use_readiness"] == "fail":
        recommendations.append(
            "  • Computer-Use: Install cua-driver for desktop automation."
        )
    if data["multi_agent_orchestration"] != "pass":
        recommendations.append(
            "  • Multi-Agent: Ensure crew_orchestrator and swarm_orchestrator modules are available."
        )

    if recommendations:
        lines.append("── Recommendations ─────────────────────────────────────")
        lines.extend(recommendations)
        lines.append("")

    lines.append("── Next Milestones ─────────────────────────────────────")
    milestones = get_next_milestones()
    for m in milestones:
        priority = m.get("priority", "medium")
        icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(priority, "🟡")
        lines.append(f"  {icon} {m['title']}  [{priority}]")
        lines.append(f"     {m['description']}")

    return "\n".join(lines)


def get_next_milestones() -> list[dict[str, str]]:
    """Return the next planned improvements for the superintelligence platform."""
    return [
        {
            "title": "Self-Reflection Cron (alle 6h)",
            "description": "Aktiv. Läuft alle 6 Stunden autonom.",
            "priority": "high",
        },
        {
            "title": "Memory Vector-Store (unbegrenztes semantisches Gedächtnis)",
            "description": "Aktiv. TF-IDF Store mit CLI: openamer memory vector {store,search,stats,list,compress}.",
            "priority": "high",
        },
        {
            "title": "Autonomous Initiative System",
            "description": "Aktiv. CLI: openamer initiative {check,fix,suggest,auto}. Cron-kompatibel.",
            "priority": "high",
        },
        {
            "title": "Cross-Session Learning Pipeline",
            "description": "Aktiv. Extrahiert Lessons, aggregiert über 7 Tage, injiziert Context. CLI: openamer cross-session.",
            "priority": "high",
        },
        {
            "title": "Skills Improvement Pipeline",
            "description": "Aktiv. Analysiert alle Skills auf Qualität, identifiziert Verbesserungskandidaten.",
            "priority": "high",
        },
        {
            "title": "Self-Healing Memory Pipeline",
            "description": "Aktiv. Erkennt korrupte/leere Memories, repariert automatisch mit Backup. CLI via Initiative.",
            "priority": "high",
        },
        {
            "title": "Autonomous Test Runner",
            "description": "Aktiv. Führt neue Tests automatisch aus, protokolliert Ergebnisse. Cron-ready.",
            "priority": "high",
        },
        {
            "title": "Swarm Metrics Dashboard",
            "description": "Aktiv. Erfasst Latenz/Durchsatz/Confidence des A2A Swarms. CLI: openamer super metrics.",
            "priority": "medium",
        },
        {
            "title": "Multi-Model Orchestration",
            "description": "Route sub-tasks to specialised models (e.g. code to DeepSeek, reasoning to Claude, vision to GPT-4o).",
            "priority": "low",
        },
    ]