"""
Self-Improvement Subsystem — direct import from scripts/training/self_improve.py

Analyzes own source code, finds improvements, applies them with test gates.
"""

import json
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
SCRIPTS_TRAINING = OPENAMER_HOME / "scripts" / "training"
sys.path.insert(0, str(SCRIPTS_TRAINING))


def _import_improve():
    import importlib
    return importlib.import_module("self_improve")


def improve_once() -> Dict[str, Any]:
    """Run one self-improvement cycle: analyze, propose, apply, test."""
    mod = _import_improve()
    return mod.improve_once()


def propose_improvement(target: str, content: str) -> Dict[str, Any]:
    """Analyze a source file and propose an improvement."""
    mod = _import_improve()
    result = mod.propose_improvement(target, content)
    return {"proposal": result}


def apply_and_test(target: str, proposal: str, live_path: str, sandbox_path: str) -> Dict[str, Any]:
    """Apply an improvement and run test gates."""
    mod = _import_improve()
    return mod.apply_and_test(target, proposal, live_path, sandbox_path)
