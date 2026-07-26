"""Resolve OPENAMER_HOME for standalone skill scripts.

Skill scripts may run outside the OpenAmer process (e.g. system Python,
nix env, CI) where ``openamer_constants`` is not importable.  This module
provides the same ``get_openamer_home()`` and ``display_openamer_home()``
contracts as ``openamer_constants`` without requiring it on ``sys.path``.

When ``openamer_constants`` IS available it is used directly so that any
future enhancements (profile resolution, Docker detection, etc.) are
picked up automatically.  The fallback path replicates the core logic
from ``openamer_constants.py`` using only the stdlib.

All scripts under ``google-workspace/scripts/`` should import from here
instead of duplicating the ``OPENAMER_HOME = Path(os.getenv(...))`` pattern.
"""

from __future__ import annotations

import os
from pathlib import Path

try:
    from openamer_constants import display_openamer_home as display_openamer_home
    from openamer_constants import get_openamer_home as get_openamer_home
except (ModuleNotFoundError, ImportError):

    def get_openamer_home() -> Path:
        """Return the OpenAmer home directory (default: ~/.openamer).

        Mirrors ``openamer_constants.get_openamer_home()``."""
        val = os.environ.get("OPENAMER_HOME", "").strip()
        return Path(val) if val else Path.home() / ".openamer"

    def display_openamer_home() -> str:
        """Return a user-friendly ``~/``-shortened display string.

        Mirrors ``openamer_constants.display_openamer_home()``."""
        home = get_openamer_home()
        try:
            return "~/" + str(home.relative_to(Path.home()))
        except ValueError:
            return str(home)
