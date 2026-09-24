"""
Swarm Subsystem — Multi-Agent-Koordination native integration.

Direct imports from swarm_intelligence.py and autonomous_loop.py — no subprocess.
"""

import logging
import sys
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

OPENAMER_HOME = Path(
    __import__("os").environ.get(
        "OPENAMER_HOME",
        str(Path.home() / "AppData/Local/openamer-laptop"),
    )
)
TRAINING_DIR = OPENAMER_HOME / "scripts" / "training"
SCRIPTS_DIR = OPENAMER_HOME / "scripts"
REPO_SCRIPTS = OPENAMER_HOME.parent / "openamer-repo" / "scripts"
for p in [str(TRAINING_DIR), str(SCRIPTS_DIR), str(REPO_SCRIPTS)]:
    if p not in sys.path:
        sys.path.insert(0, p)


def _import_swarm():
    import importlib
    return importlib.import_module("swarm_intelligence")


def _import_autonomous():
    import importlib
    return importlib.import_module("autonomous_loop")


def route(task: str) -> Dict[str, Any]:
    """Route a task via swarm intelligence.

    Direct import from swarm_intelligence — no subprocess."""
    mod = _import_swarm()
    try:
        if hasattr(mod, "route"):
            result = mod.route(task)
            return {"success": True, "result": str(result)[:500]}
        return {"success": False, "error": "no route() in swarm_intelligence"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def cycle() -> Dict[str, Any]:
    """Run one full swarm intelligence cycle.

    Direct import from swarm_intelligence — no subprocess."""
    mod = _import_swarm()
    try:
        if hasattr(mod, "cycle"):
            result = mod.cycle()
            return {"success": True, "result": str(result)[:500]}
        if hasattr(mod, "run"):
            result = mod.run()
            return {"success": True, "result": str(result)[:500]}
        return {"success": False, "error": "no cycle() or run() in swarm_intelligence"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def autonomous() -> Dict[str, Any]:
    """Run the autonomous loop.

    Direct import from autonomous_loop — no subprocess."""
    try:
        mod = _import_autonomous()
        results = []
        if hasattr(mod, "generate_tasks_from_gaps"):
            tasks = mod.generate_tasks_from_gaps()
            results.append({"tasks_generated": len(tasks)})
        if hasattr(mod, "execute_assigned_tasks"):
            executed = mod.execute_assigned_tasks()
            results.append({"tasks_executed": len(executed)})
        return {"success": True, "results": results}
    except Exception as e:
        return {"success": False, "error": str(e)}