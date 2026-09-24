"""
Prediction Validator Subsystem — direct import from scripts/training/predict_validate.py

Closes the loop on world-model predictions: validates, scores, and adjusts confidence.
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


def _import_predict():
    import importlib
    return importlib.import_module("predict_validate")


def validate_predictions() -> Dict[str, Any]:
    """Run prediction validation cycle."""
    mod = _import_predict()
    return mod.validate_predictions()


def apply_confidence_adjustments() -> Dict[str, Any]:
    """Apply confidence adjustments based on validation results."""
    mod = _import_predict()
    mod.apply_confidence_to_new_predictions()
    return {"success": True}