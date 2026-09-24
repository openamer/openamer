"""
Swarm Subsystem — Multi-Agent-Koordination native integration.

Wraps scripts/training/swarm_intelligence.py and scripts/autonomous_loop.py
"""

import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

OPENAMER_HOME = Path(
    __import__("os").environ.get(
        "OPENAMER_HOME",
        str(Path.home() / "AppData/Local/openamer-laptop"),
    )
)
TRAINING_DIR = OPENAMER_HOME / "scripts" / "training"
SCRIPTS_DIR = OPENAMER_HOME / "scripts"
if str(TRAINING_DIR) not in sys.path:
    sys.path.insert(0, str(TRAINING_DIR))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


def _import_swarm():
    import importlib
    return importlib.import_module("swarm_intelligence")


def route(task: str) -> Dict[str, Any]:
    """Route a task via swarm intelligence: find the best agent for it."""
    mod = _import_swarm()
    try:
        if hasattr(mod, "route"):
            result = mod.route(task)
            return {"success": True, "result": str(result)[:500]}
        elif hasattr(mod, "main"):
            result = mod.main(["route", task])
            return {"success": True, "result": str(result)[:500]}
        return {"success": False, "error": "No route function found"}
    except Exception as e:
        logger.exception("swarm.route failed")
        return {"success": False, "error": str(e)}


def cycle() -> Dict[str, Any]:
    """Run one full swarm intelligence cycle."""
    mod = _import_swarm()
    try:
        if hasattr(mod, "cycle"):
            result = mod.cycle()
            return {"success": True, "result": str(result)[:500]}
        elif hasattr(mod, "run"):
            result = mod.run()
            return {"success": True, "result": str(result)[:500]}
        # Fallback: call main with --cycle
        import subprocess
        result = subprocess.run(
            [sys.executable, str(TRAINING_DIR / "swarm_intelligence.py"), "--cycle"],
            capture_output=True, text=True, timeout=120,
        )
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout[-500:],
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def autonomous() -> Dict[str, Any]:
    """Run the autonomous loop."""
    try:
        import subprocess
        result = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / ".." / "openamer-repo" / "scripts" / "autonomous_loop.py")],
            capture_output=True, text=True, timeout=180,
        )
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout[-500:],
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def status() -> Dict[str, Any]:
    """Return swarm status."""
    return {"status": "integrated", "module": "tools.asi.swarm"}