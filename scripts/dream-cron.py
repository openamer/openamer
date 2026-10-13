#!/usr/bin/env python3
"""Cron entry for nightly dream consolidation (circadian.py dream)."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from circadian import cmd_dream

sys.exit(cmd_dream())
