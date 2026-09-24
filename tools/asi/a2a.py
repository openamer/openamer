"""
A2A Subsystem — Agent-to-Agent native integration.

Wraps scripts/a2a_worker.py core functions with direct imports.
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
SCRIPTS_DIR = OPENAMER_HOME / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


def _import_a2a():
    import importlib
    return importlib.import_module("a2a_worker")


def run(repo_path: Optional[str] = None, no_push: bool = False) -> Dict[str, Any]:
    """Run one A2A worker cycle: consume relay tasks, execute, push results."""
    mod = _import_a2a()
    repo = Path(repo_path) if repo_path else OPENAMER_HOME / ".." / "openamer-repo"
    count = mod.run(repo.resolve(), no_push=no_push)
    return {"success": True, "tasks_processed": count}


def brain_collect() -> Dict[str, Any]:
    """Collect recent sessions into the brain dataset."""
    return _run_brain("collect")


def brain_sync() -> Dict[str, Any]:
    """Sync brain data with peer nodes."""
    return _run_brain("sync")


def _run_brain(action: str) -> Dict[str, Any]:
    """Run a brain action via the CLI."""
    import subprocess
    try:
        result = subprocess.run(
            ["openamer", "a2a", "brain", action],
            capture_output=True, text=True, timeout=60,
            env={**__import__("os").environ, "OPENAMER_HOME": str(OPENAMER_HOME)},
        )
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout[-500:],
            "stderr": result.stderr[-200:],
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def peer_query(question: str, max_peers: int = 3) -> Dict[str, Any]:
    """Query A2A peer nodes for an answer."""
    import subprocess
    try:
        result = subprocess.run(
            ["openamer", "a2a", "query", question, "--max", str(max_peers)],
            capture_output=True, text=True, timeout=120,
        )
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout[-1000:],
            "stderr": result.stderr[-200:],
        }
    except Exception as e:
        return {"success": False, "error": str(e)}