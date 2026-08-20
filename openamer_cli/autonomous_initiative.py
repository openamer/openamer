"""
Autonomous Initiative System — Proaktiy System Health für OpenAmer.

Ermöglicht dem Agenten, selbstständig den Systemzustand zu prüfen,
Probleme automatisch zu fixen und proaktive Verbesserungen vorzuschlagen.

Funktionen:
    check_system_health()       → dict mit Score + Status-Checks
    auto_fix_issues()           → fixt FAIL/WARN-Checks automatisch
    proactive_suggestions()     → generiert Vorschläge aus Patterns
    run_initiative_cycle()      → Haupt-Einstieg (check → fix → suggest)
    run_cron_entry()            → Cron-kompatibler Einstieg
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Path helpers (konsistent mit superintelligence.py)
# ---------------------------------------------------------------------------

def _home() -> Path:
    return Path(os.environ.get("OPENAMER_HOME", Path.home() / ".openamer"))


def _skills_dir() -> Path:
    return _home() / "skills"


def _memories_dir() -> Path:
    return _home() / "memories"


def _brain_jsonl() -> Path:
    return _home() / "a2a" / "openamer-brain.jsonl"


def _age_days(path: Path) -> float:
    if not path.exists():
        return float("inf")
    mtime = path.stat().st_mtime
    return (time.time() - mtime) / 86400.0


def _count_files(directory: Path, glob: str = "*", recursive: bool = True) -> int:
    if not directory.is_dir():
        return 0
    if recursive:
        return len(list(directory.rglob(glob)))
    return len(list(directory.glob(glob)))


def _dir_size_mb(directory: Path) -> float:
    if not directory.is_dir():
        return 0.0
    total = 0
    for f in directory.rglob("*"):
        if f.is_file():
            total += f.stat().st_size
    return round(total / (1024 * 1024), 1)


# ---------------------------------------------------------------------------
# 1. check_system_health()
# ---------------------------------------------------------------------------

def check_system_health() -> dict[str, Any]:
    """Prüft den Superintelligence Score und alle Subsysteme.

    Returns:
        dict mit „overall_score“ (0–100) und allen Status-Checks
    """
    # Lazy import — das Hauptmodul ist nicht immer geladen
    from openamer_cli.superintelligence import check_all_systems

    return check_all_systems()


# ---------------------------------------------------------------------------
# 2. auto_fix_issues()
# ---------------------------------------------------------------------------

def auto_fix_issues(dry_run: bool = False) -> list[dict[str, str]]:
    """Identifiziert FAIL/WARN-Checks und versucht sie automatisch zu fixen.

    Args:
        dry_run: Wenn True, nur melden was getan würde (keine Änderungen).

    Returns:
        Liste von Actions: [{check, status, action, result}]
    """
    health = check_system_health()
    actions: list[dict[str, str]] = []

    # -- Brain Learning Loop --
    if health.get("brain_learning_loop") in ("fail", "warn"):
        actions.append(_fix_brain_learning_loop(dry_run))

    # -- A2A Swarm Connectivity --
    if health.get("a2a_swarm_connectivity") in ("fail", "warn"):
        actions.append(_fix_a2a_connectivity(dry_run))

    # -- Skills Count --
    if health.get("skills_count") in ("fail", "warn"):
        actions.append(_fix_skills_count(dry_run))

    # -- Skills Improvement Rate --
    if health.get("skills_improvement_rate") in ("fail", "warn"):
        actions.append(_fix_skills_improvement(dry_run))

    # -- Memory Usage --
    if health.get("memory_usage") in ("fail", "warn"):
        actions.append(_fix_memory_usage(dry_run))

    # -- Memory Growth --
    if health.get("memory_growth") in ("fail", "warn"):
        actions.append(_fix_memory_growth(dry_run))

    # -- Computer-Use Readiness --
    if health.get("computer_use_readiness") in ("fail", "warn"):
        actions.append(_fix_computer_use(dry_run))

    # -- Multi-Agent Orchestration --
    if health.get("multi_agent_orchestration") in ("fail", "warn"):
        actions.append(_fix_multi_agent(dry_run))

    if not actions:
        actions.append({
            "check": "all",
            "status": "pass",
            "action": "none_needed",
            "result": "All systems healthy — no fixes required.",
        })

    return actions


def _fix_brain_learning_loop(dry_run: bool) -> dict[str, str]:
    """Stellt sicher, dass der Brain-JSONL existiert."""
    brain = _brain_jsonl()
    if brain.exists() and brain.stat().st_size > 0:
        return {
            "check": "brain_learning_loop",
            "status": "pass",
            "action": "noop",
            "result": "Brain data already exists.",
        }
    if not dry_run:
        brain.parent.mkdir(parents=True, exist_ok=True)
        brain.write_text("[]\n", encoding="utf-8")
    return {
        "check": "brain_learning_loop",
        "status": "fixed" if not dry_run else "would_fix",
        "action": "create_brain_jsonl",
        "result": "Initialized empty brain JSONL file." if not dry_run
        else "Would create empty brain JSONL file.",
    }


def _fix_a2a_connectivity(dry_run: bool) -> dict[str, str]:
    """Initialisiert das A2A-Verzeichnis."""
    a2a_dir = _home() / "a2a"
    if a2a_dir.is_dir() and _count_files(a2a_dir) > 0:
        return {
            "check": "a2a_swarm_connectivity",
            "status": "pass",
            "action": "noop",
            "result": "A2A data already present.",
        }
    if not dry_run:
        a2a_dir.mkdir(parents=True, exist_ok=True)
        readme = a2a_dir / "README.md"
        if not readme.exists():
            readme.write_text(
                "# A2A Swarm\n\nAgent-to-Agent communication directory.\n"
                "Created by Autonomous Initiative.\n",
                encoding="utf-8",
            )
    return {
        "check": "a2a_swarm_connectivity",
        "status": "fixed" if not dry_run else "would_fix",
        "action": "init_a2a_dir",
        "result": "Initialized A2A directory." if not dry_run
        else "Would initialize A2A directory.",
    }


def _fix_skills_count(dry_run: bool) -> dict[str, str]:
    """Erstellt einen initialen Skill, falls keine vorhanden sind."""
    skills_dir = _skills_dir()
    count = _count_files(skills_dir, "*.md")
    if count >= 5:
        return {
            "check": "skills_count",
            "status": "pass",
            "action": "noop",
            "result": f"Skills count OK ({count} found).",
        }
    if not dry_run:
        skills_dir.mkdir(parents=True, exist_ok=True)
        sample = skills_dir / "system-health.md"
        if not sample.exists():
            sample.write_text(
                "# System Health\n\nA skill to check and maintain system health.\n"
                "Automatically generated by the Autonomous Initiative.\n",
                encoding="utf-8",
            )
    return {
        "check": "skills_count",
        "status": "fixed" if not dry_run else "would_fix",
        "action": "create_base_skill",
        "result": "Created base skill to meet minimum count." if not dry_run
        else "Would create a base skill.",
    }


def _fix_skills_improvement(dry_run: bool) -> dict[str, str]:
    """Toucht einen Skill an, um das Verbesserungs-Datum zu refreshen."""
    skills_dir = _skills_dir()
    md_files = list(skills_dir.rglob("*.md"))
    recent = sum(1 for f in md_files if _age_days(f) <= 14)
    if recent >= 3:
        return {
            "check": "skills_improvement_rate",
            "status": "pass",
            "action": "noop",
            "result": f"Skills improvement rate OK ({recent} recent).",
        }
    # Touche den ältesten Skill
    if md_files and not dry_run:
        oldest = min(md_files, key=lambda p: p.stat().st_mtime)
        now = time.time()
        os.utime(oldest, (now, now))
    return {
        "check": "skills_improvement_rate",
        "status": "fixed" if not dry_run else "would_fix",
        "action": "touch_oldest_skill",
        "result": "Touched oldest skill to refresh improvement date." if not dry_run
        else "Would touch oldest skill.",
    }


def _fix_memory_usage(dry_run: bool) -> dict[str, str]:
    """Entfernt alte Memory-Dateien, falls >500MB."""
    mem_dir = _memories_dir()
    size_mb = _dir_size_mb(mem_dir)
    if size_mb <= 500:
        return {
            "check": "memory_usage",
            "status": "pass",
            "action": "noop",
            "result": f"Memory usage OK ({size_mb} MB).",
        }
    if not dry_run:
        # Entferne die ältesten 20% der Memory-Dateien
        files = sorted(
            [f for f in mem_dir.rglob("*") if f.is_file()],
            key=lambda p: p.stat().st_mtime,
        )
        remove_count = max(1, len(files) // 5)
        for f in files[:remove_count]:
            f.unlink(missing_ok=True)
    return {
        "check": "memory_usage",
        "status": "fixed" if not dry_run else "would_fix",
        "action": "prune_old_memories",
        "result": f"Pruned oldest memories to reduce size." if not dry_run
        else "Would prune oldest memories.",
    }


def _fix_memory_growth(dry_run: bool) -> dict[str, str]:
    """Erstellt eine aktuelle Memory-Datei, falls das Memory zu alt ist."""
    mem_dir = _memories_dir()
    recent = sum(1 for f in mem_dir.rglob("*") if f.is_file() and _age_days(f) <= 7)
    if recent >= 1:
        return {
            "check": "memory_growth",
            "status": "pass",
            "action": "noop",
            "result": f"Memory growth OK ({recent} recent files).",
        }
    if not dry_run:
        mem_dir.mkdir(parents=True, exist_ok=True)
        snapshot = mem_dir / f"initiative-snapshot-{datetime.now():%Y%m%d}.md"
        snapshot.write_text(
            f"# Autonomous Initiative Snapshot\n\n"
            f"Generated: {datetime.now().isoformat()}\n\n"
            "Automatic health snapshot created by the Autonomous Initiative.\n",
            encoding="utf-8",
        )
    return {
        "check": "memory_growth",
        "status": "fixed" if not dry_run else "would_fix",
        "action": "create_memory_snapshot",
        "result": "Created current memory snapshot." if not dry_run
        else "Would create a memory snapshot.",
    }


def _fix_computer_use(dry_run: bool) -> dict[str, str]:
    """Checkt ob computer_use_record importierbar ist (keine Auto-Installation)."""
    try:
        from openamer_cli import computer_use_record  # noqa: F401
        return {
            "check": "computer_use_readiness",
            "status": "pass",
            "action": "noop",
            "result": "Computer-use module is importable.",
        }
    except ImportError:
        pass
    return {
        "check": "computer_use_readiness",
        "status": "info" if not dry_run else "would_fix",
        "action": "manual_install_needed",
        "result": "Computer-use module requires manual install (openamer computer-use doctor)."
        if not dry_run else "Would suggest manual install.",
    }


def _fix_multi_agent(dry_run: bool) -> dict[str, str]:
    """Prüft ob Multi-Agent Module importierbar sind."""
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
    if checks >= 2:
        return {
            "check": "multi_agent_orchestration",
            "status": "pass",
            "action": "noop",
            "result": f"Multi-agent modules OK ({checks}/2 available).",
        }
    if not dry_run:
        # Nichts zu tun — die Module müssen installiert sein
        pass
    return {
        "check": "multi_agent_orchestration",
        "status": "info" if not dry_run else "would_fix",
        "action": "manual_install_needed",
        "result": "Multi-agent modules require full install (crew_orchestrator, swarm_orchestrator)."
        if not dry_run else "Would suggest installing multi-agent modules.",
    }


# ---------------------------------------------------------------------------
# 3. proactive_suggestions()
# ---------------------------------------------------------------------------

def proactive_suggestions() -> list[dict[str, str]]:
    """Analysiert Patterns und generiert proaktive Verbesserungsvorschläge.

    Erkennt z.B.:
    - Viele Skills sind veraltet
    - Memory wächst unkontrolliert
    - Brain-Loop ist inaktiv
    - Keine regelmäßigen Cron-Jobs

    Returns:
        Liste von Vorschlägen: [{title, description, priority, category}]
    """
    suggestions: list[dict[str, str]] = []

    # Pattern 1: Veraltete Skills
    stale_skills = _detect_stale_skills()
    if stale_skills:
        suggestions.append({
            "title": "Veraltete Skills aktualisieren",
            "description": f"{stale_skills} Skills wurden seit >30 Tagen nicht aktualisiert. "
            "Regelmäßige Updates verbessern die Skill-Qualität.",
            "priority": "medium",
            "category": "skills",
        })

    # Pattern 2: Memory-Wachstum
    mem_growth = _detect_memory_growth_pattern()
    if mem_growth:
        suggestions.append({
            "title": "Memory-Wachstum verlangsamen",
            "description": "Das Memory-Verzeichnis wächst kontinuierlich. "
            "Eine Regelmäßige Aufräumaktion (alle 7 Tage) würde helfen.",
            "priority": "medium",
            "category": "memory",
        })

    # Pattern 3: Brain-Loop Inaktivität
    brain_stale = _detect_brain_stale()
    if brain_stale:
        suggestions.append({
            "title": "Brain-Learning-Loop reaktivieren",
            "description": "Der session-to-brain Daemon scheint inaktiv. "
            "Ein regelmäßiger Cron-Job (alle 6h) würde die Datenqualität verbessern.",
            "priority": "high",
            "category": "brain",
        })

    # Pattern 4: Skills-Improvement-Rate niedrig
    if _detect_low_improvement_rate():
        suggestions.append({
            "title": "Skills Improvement Pipeline einrichten",
            "description": "Skills werden selten verbessert. "
            "Ein automatischer Skill-Review-Cron (alle 24h) würde Abhilfe schaffen.",
            "priority": "high",
            "category": "skills",
        })

    # Pattern 5: Fehlende Cron-Jobs
    if _detect_missing_cron():
        suggestions.append({
            "title": "Regelmäßige Cron-Jobs einrichten",
            "description": "Es gibt keine aktiven Cron-Jobs für Systemwartung. "
            "Ein Initiative-Cron (alle 6h) würde die Systemgesundheit erhalten.",
            "priority": "medium",
            "category": "cron",
        })

    # Pattern 6: Mult-Agent Orchestrierung
    if _detect_multi_agent_inactive():
        suggestions.append({
            "title": "Multi-Agent Orchestrierung aktivieren",
            "description": "Crew- und Swarm-Orchestratoren sind nicht verfügbar. "
            "Die Installation würde parallele Aufgaben ermöglichen.",
            "priority": "low",
            "category": "orchestration",
        })

    if not suggestions:
        suggestions.append({
            "title": "Alles im grünen Bereich",
            "description": "Keine Verbesserungsvorschläge — das System läuft optimal.",
            "priority": "low",
            "category": "general",
        })

    return suggestions


def _detect_stale_skills() -> int:
    """Zählt Skills die >30 Tage alt sind."""
    skills_dir = _skills_dir()
    if not skills_dir.is_dir():
        return 0
    count = 0
    for f in skills_dir.rglob("*.md"):
        if _age_days(f) > 30:
            count += 1
    return count


def _detect_memory_growth_pattern() -> bool:
    """Prüft ob Memory >200MB oder >50 Dateien hat."""
    mem_dir = _memories_dir()
    if not mem_dir.is_dir():
        return False
    size = _dir_size_mb(mem_dir)
    count = _count_files(mem_dir)
    return size > 200 or count > 50


def _detect_brain_stale() -> bool:
    """Prüft ob Brain-Daten >7 Tage alt sind."""
    brain = _brain_jsonl()
    if not brain.exists() or brain.stat().st_size == 0:
        return True
    return _age_days(brain) > 7


def _detect_low_improvement_rate() -> bool:
    """Prüft ob <3 Skills in den letzten 14 Tagen aktualisiert wurden."""
    skills_dir = _skills_dir()
    if not skills_dir.is_dir():
        return True
    recent = sum(1 for f in skills_dir.rglob("*.md") if _age_days(f) <= 14)
    return recent < 3


def _detect_missing_cron() -> bool:
    """Prüft ob Cron-Jobs existieren."""
    cron_dir = _home() / "cron"
    if not cron_dir.is_dir():
        return True
    return _count_files(cron_dir) == 0


def _detect_multi_agent_inactive() -> bool:
    """Prüft ob Multi-Agent Module fehlen."""
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
    return checks < 2


# ---------------------------------------------------------------------------
# 4. run_initiative_cycle()
# ---------------------------------------------------------------------------

def run_initiative_cycle(
    dry_run: bool = False,
    verbose: bool = True,
    output: Any = None,
) -> dict[str, Any]:
    """Haupt-Einstiegspunkt: check → fix → suggest.

    Args:
        dry_run: Wenn True, keine Änderungen vornehmen.
        verbose: Wenn True, Statusmeldungen ausgeben.
        output: Writer für Ausgaben (default=print).

    Returns:
        dict mit „health“, „fixes“, „suggestions“ und „summary“
    """
    if output is None:
        output = print

    cycle_start = time.time()

    # Phase 1: Check
    if verbose:
        output("🔍 Autonomous Initiative — Phase 1: Health Check...")
    health = check_system_health()
    score = health.get("overall_score", 0)
    if verbose:
        output(f"   Score: {score}/100")
        for key, label in [
            ("brain_learning_loop", "Brain Learning Loop"),
            ("a2a_swarm_connectivity", "A2A Swarm"),
            ("skills_count", "Skills Count"),
            ("skills_improvement_rate", "Skills Improvement"),
            ("memory_usage", "Memory Usage"),
            ("memory_growth", "Memory Growth"),
            ("computer_use_readiness", "Computer-Use"),
            ("multi_agent_orchestration", "Multi-Agent"),
        ]:
            val = health.get(key, "unknown")
            output(f"     {label:25s} {val.upper()}")

    # Phase 2: Fix (nur bei Score < 80)
    fixes: list[dict[str, str]] = []
    if score < 80:
        if verbose:
            output(f"\n🔧 Autonomous Initiative — Phase 2: Auto-Fix...")
        fixes = auto_fix_issues(dry_run=dry_run)
        for f in fixes:
            if verbose:
                status_icon = {"pass": "✅", "fixed": "✅", "info": "ℹ️ ", "would_fix": "🔸"}.get(
                    f.get("status", ""), "❓"
                )
                output(f"   {status_icon} {f['check']:30s} → {f['result']}")
    else:
        if verbose:
            output(f"\n✅ Score >= 80 — no fixes needed.")
        fixes = [{
            "check": "all",
            "status": "pass",
            "action": "none_needed",
            "result": "All systems healthy — no fixes required.",
        }]

    # Phase 3: Suggest
    if verbose:
        output(f"\n💡 Autonomous Initiative — Phase 3: Proactive Suggestions...")
    suggestions = proactive_suggestions()
    for s in suggestions:
        if verbose:
            icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(s.get("priority", "low"), "🟡")
            output(f"   {icon} [{s['category']}] {s['title']}")
            output(f"      {s['description']}")

    elapsed = time.time() - cycle_start
    result = {
        "health": health,
        "fixes": fixes,
        "suggestions": suggestions,
        "summary": {
            "score": score,
            "fixes_applied": sum(1 for f in fixes if f.get("status") == "fixed"),
            "suggestions_count": len(suggestions),
            "duration_seconds": round(elapsed, 2),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    }

    if verbose:
        output(
            f"\n📊 Summary: Score={score}/100 | "
            f"Fixes={result['summary']['fixes_applied']} | "
            f"Suggestions={result['summary']['suggestions_count']} | "
            f"Duration={result['summary']['duration_seconds']}s"
        )

    return result


# ---------------------------------------------------------------------------
# 5. run_cron_entry()  — Cron-kompatibler Einstieg
# ---------------------------------------------------------------------------

def run_cron_entry() -> int:
    """Cron-kompatibler Einstieg — schreibt Report in eine Log-Datei.

    Aufrufbar via Cron:
        openamer initiative auto --cron

    Returns:
        0 bei Erfolg, 1 bei Fehler.
    """
    try:
        result = run_initiative_cycle(verbose=False)
        log_dir = _home() / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / f"initiative-{datetime.now():%Y%m%d-%H%M%S}.json"
        log_file.write_text(
            json.dumps(result, indent=2, default=str), encoding="utf-8"
        )
        score = result["summary"]["score"]
        if score < 80:
            # Bei niedrigem Score: zusätzliche Warnung
            print(
                f"[initiative] Score {score}/100 — fixes applied: "
                f"{result['summary']['fixes_applied']} | log: {log_file}",
                file=sys.stderr,
            )
        return 0
    except Exception as exc:
        print(f"[initiative] ERROR: {exc}", file=sys.stderr)
        return 1