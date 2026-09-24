"""
World Model Subsystem — direct import from scripts/training/world_model.py

The central cause→effect memory. Every learning loop writes through here;
every prediction reads from here.
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


def _import_world_model():
    import importlib
    return importlib.import_module("world_model")


def recall(query: str, k: int = 5, kind: Optional[str] = None) -> List[Dict]:
    """Recall edges from the world model matching a query."""
    mod = _import_world_model()
    return mod.recall(query, k=k, kind=kind)


def predict(situation: str, k: int = 3) -> List[Dict]:
    """Predict outcomes from the world model."""
    mod = _import_world_model()
    return mod.predict(situation, k=k)


def observe(cause: str, effect: str, kind: str = "fact", confidence: Optional[float] = None) -> bool:
    """Record a cause→effect observation."""
    mod = _import_world_model()
    mod.observe(cause, effect, kind=kind, confidence=confidence)
    return True


def stats() -> Dict[str, Any]:
    """Return world model statistics."""
    mod = _import_world_model()
    return mod.stats()


def repair() -> Dict[str, Any]:
    """Repair the world model store."""
    mod = _import_world_model()
    mod.repair_store()
    return {"success": True}
