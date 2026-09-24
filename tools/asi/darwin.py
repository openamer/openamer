"""
Darwin Subsystem — evolutionäre Skill-Evolution native integration.

Direct imports from darwin_engine.py — no subprocess for core operations.
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
REPO_DIR = OPENAMER_HOME.parent / "openamer-repo"
SCRIPTS_DIR = OPENAMER_HOME / "scripts"
TRAINING_DIR = OPENAMER_HOME / "scripts" / "training"
for p in [str(SCRIPTS_DIR), str(REPO_DIR / "scripts"), str(TRAINING_DIR)]:
    if p not in sys.path:
        sys.path.insert(0, p)


def _import_darwin():
    import importlib
    return importlib.import_module("darwin_engine")


def _import_publish():
    import importlib
    return importlib.import_module("darwin_publish")


def autopilot() -> Dict[str, Any]:
    """Run one Darwin autopilot cycle.

    Direct import from darwin_engine — no subprocess."""
    mod = _import_darwin()
    try:
        result = mod.start_trial("system", "evolve", job_id="asi-heartbeat")
        return {"success": True, "trial": str(result)[:500] if result else "ok"}
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


def publish() -> Dict[str, Any]:
    """Run Darwin publish cycle.

    Direct import from darwin_publish.main() — no subprocess."""
    try:
        mod = _import_publish()
        mod.main()
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}


def autopatch() -> Dict[str, Any]:
    """Run Darwin autopatch cycle."""
    import subprocess
    try:
        script = SCRIPTS_DIR / "darwin-autopatch-cron.py"
        if script.exists():
            result = subprocess.run(
                [sys.executable, str(script)],
                capture_output=True, text=True, timeout=180,
            )
            return {"success": result.returncode == 0}
        return {"success": False, "error": "darwin-autopatch-cron.py not found"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def grid_sync() -> Dict[str, Any]:
    """Run Darwin Grid sync.

    Direct import from darwin_grid_github.publish() — no subprocess."""
    import importlib
    try:
        mod = importlib.import_module("darwin_grid_github")
        if hasattr(mod, "publish"):
            mod.publish("asi-heartbeat")
            return {"success": True}
        return {"success": False, "error": "no publish() in darwin_grid_github"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def skill_probe() -> Dict[str, Any]:
    """Run Darwin skill probe.
    
    Script has hyphen in name — must use subprocess."""
    import subprocess
    try:
        script = SCRIPTS_DIR / "darwin-probe-cron.py"
        if script.exists():
            result = subprocess.run(
                [sys.executable, str(script)],
                capture_output=True, text=True, timeout=120,
            )
            return {"success": result.returncode == 0}
        return {"success": False, "error": "darwin-probe-cron.py not found"}
    except Exception as e:
        return {"success": False, "error": str(e)}