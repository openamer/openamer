#!/usr/bin/env python3
"""Cron entry for nightly dream consolidation (circadian.py dream)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import importlib.util
spec = importlib.util.spec_from_file_location("circadian", Path(__file__).parent / "circadian.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
sys.exit(m.cmd_dream())
