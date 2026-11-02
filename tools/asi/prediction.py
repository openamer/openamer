"""
Prediction Validator Subsystem — direct import from scripts/training/predict_validate.py

Closes the loop on world-model predictions: validates, scores, and adjusts confidence.
"""

import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from openamer_constants import get_openamer_home
from tools.asi._training import load_training_module

logger = logging.getLogger(__name__)

OPENAMER_HOME = get_openamer_home()
SCRIPTS_TRAINING = OPENAMER_HOME / "scripts" / "training"


def _import_predict():
    return load_training_module("predict_validate")


def validate_predictions() -> Dict[str, Any]:
    """Run prediction validation cycle."""
    mod = _import_predict()
    return mod.validate_predictions()


def apply_confidence_to_new_predictions() -> float:
    """Return the track-record adjustment factor for NEW predictions.

    Mirrors the real module's function of the same name; the value is what a
    caller should scale a fresh prediction's confidence by.
    """
    mod = _import_predict()
    return mod.apply_confidence_to_new_predictions()


def apply_confidence_adjustments() -> Dict[str, Any]:
    """Apply confidence adjustments based on validation results."""
    mod = _import_predict()
    mod.apply_confidence_to_new_predictions()
    return {"success": True}