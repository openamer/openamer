"""
Self-Model Subsystem — direct import from scripts/training/self_model.py

Reads and writes the agent's persistent self-model (current_state.json,
identity.md, identity_history.jsonl).
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
SELF_MODEL_DIR = OPENAMER_HOME / "memory" / "self_model"
SCRIPTS_TRAINING = OPENAMER_HOME / "scripts" / "training"

# Import the script's functions directly
sys.path.insert(0, str(SCRIPTS_TRAINING))

# These functions are imported from self_model.py
def _import_self_model():
    """Lazy import to avoid circular deps at module level."""
    import importlib
    mod = importlib.import_module("self_model")
    return mod


def gather_state() -> Dict[str, Any]:
    """Gather current ASI state from memory stores."""
    mod = _import_self_model()
    return mod.gather_state()


def update_identity(state: Dict[str, Any], prior_identity: str = "") -> str:
    """Update the identity.md file from current state."""
    mod = _import_self_model()
    return mod.update_identity(state, prior_identity)


def record_history(state: Dict[str, Any], identity_hash: str):
    """Append a state snapshot to the identity history."""
    mod = _import_self_model()
    return mod.record_history(state, identity_hash)


def run_cycle() -> Dict[str, Any]:
    """Run one self-model cycle: gather state, update identity, record history."""
    mod = _import_self_model()
    state = mod.gather_state()
    identity_hash = mod.update_identity(state)
    mod.record_history(state, identity_hash)
    return {
        "success": True,
        "state": state,
        "identity_hash": identity_hash,
    }
