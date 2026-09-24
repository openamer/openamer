"""
Darwin Subsystem — evolutionäre Skill-Evolution native integration.

Wraps scripts/darwin_engine.py core functions with direct imports.
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
REPO_DIR = OPENAMER_HOME / ".." / "openamer-repo"
SCRIPTS_DIR = OPENAMER_HOME / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
# Also add repo scripts dir
REPO_SCRIPTS = REPO_DIR / "scripts"
if str(REPO_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(REPO_SCRIPTS))


def _import_darwin():
    import importlib
    return importlib.import_module("darwin_engine")


def autopilot() -> Dict[str, Any]:
    """Run one Darwin autopilot cycle: evolve skills, track fitness."""
    mod = _import_darwin()
    # Darwin engine's main autopilot path
    try:
        # If there's an autopilot function, call it
        if hasattr(mod, "autopilot"):
            result = mod.autopilot()
            return {"success": True, "result": str(result)[:500]}
        # Otherwise run the engine's main flow
        result = mod.start_trial("system", "evolve", job_id="asi-heartbeat")
        return {"success": True, "trial": str(result)[:500]}
    except Exception as e:
        logger.exception("darwin autopilot failed")
        return {"success": False, "error": str(e)}


def start_trial(parent: str, child: str, job_id: Optional[str] = None) -> Dict[str, Any]:
    """Start a Darwin evolution trial."""
    mod = _import_darwin()
    try:
        result = mod.start_trial(parent, child, job_id=job_id)
        return {"success": True, "trial": result}
    except Exception as e:
        return {"success": False, "error": str(e)}


def end_trial(job_id: str, won: bool) -> Dict[str, Any]:
    """End a Darwin trial with outcome."""
    mod = _import_darwin()
    try:
        result = mod.end_trial(job_id, won=won)
        return {"success": True, "result": result}
    except Exception as e:
        return {"success": False, "error": str(e)}


def skill_probe() -> Dict[str, Any]:
    """Run skill probe: measure skill fitness signals."""
    try:
        result = subprocess_run([
            sys.executable, str(SCRIPTS_DIR / "darwin-probe-cron.py")
        ])
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


def publish() -> Dict[str, Any]:
    """Run Darwin publish cycle."""
    try:
        result = subprocess_run([
            sys.executable, str(REPO_SCRIPTS / "darwin_publish.py")
        ])
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


def autopatch() -> Dict[str, Any]:
    """Run Darwin auto-patch cycle."""
    try:
        result = subprocess_run([
            sys.executable, str(SCRIPTS_DIR / "darwin-autopatch-cron.py")
        ])
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


def grid_sync() -> Dict[str, Any]:
    """Run Darwin Grid sync."""
    try:
        result = subprocess_run([
            sys.executable, str(REPO_SCRIPTS / "darwin_grid_github.py"),
            "--push", "--force",
        ])
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


def subprocess_run(cmd: List[str]) -> Dict[str, Any]:
    """Run a subprocess with timeout."""
    import subprocess
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=180,
            env={**__import__("os").environ, "OPENAMER_HOME": str(OPENAMER_HOME)},
        )
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout[-500:],
            "stderr": result.stderr[-200:],
            "exit_code": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Timeout (180s)"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def stats() -> Dict[str, Any]:
    """Return Darwin statistics."""
    mod = _import_darwin()
    return getattr(mod, "stats", lambda: {"status": "unavailable"})()