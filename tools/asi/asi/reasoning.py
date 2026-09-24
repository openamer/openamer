"""
Reasoning Subsystem — direct import from scripts/training/reasoning_loop.py

Recursive reasoning loop: forces depth by iterating question→answer→reflect→refine.
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
SCRIPTS_TRAINING = OPENAMER_HOME / "scripts" / "training"
sys.path.insert(0, str(SCRIPTS_TRAINING))


def _import_reasoning():
    import importlib
    return importlib.import_module("reasoning_loop")


def recursive_ask(question: str, rounds: Optional[int] = None) -> Dict[str, Any]:
    """Run recursive reasoning on a question.

    Returns:
        dict with keys: answer, rounds, history, predictions
    """
    mod = _import_reasoning()
    max_rounds = rounds or getattr(mod, "MAX_ROUNDS", 5)
    return mod.recursive_ask(question, rounds=max_rounds)


def predict(situation: str, k: int = 3) -> List[Dict]:
    """Quick prediction using the reasoning loop's world model."""
    mod = _import_reasoning()
    return mod.predict(situation, k=k)


def graph_stats() -> Dict[str, Any]:
    """Reasoning graph statistics."""
    mod = _import_reasoning()
    return mod.graph_stats()
