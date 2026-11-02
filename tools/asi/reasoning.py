"""
Reasoning Subsystem — direct import from scripts/training/reasoning_loop.py

Recursive reasoning loop: forces depth by iterating question→answer→reflect→refine.
"""

import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from openamer_constants import get_openamer_home
from tools.asi._training import load_training_module

logger = logging.getLogger(__name__)

OPENAMER_HOME = get_openamer_home()
SCRIPTS_TRAINING = OPENAMER_HOME / "scripts" / "training"


def _import_reasoning():
    return load_training_module("reasoning_loop")


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
