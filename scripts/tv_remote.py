#!/usr/bin/env python3
"""Standalone entry point for the Philips TV remote.

The implementation lives in ``openamer_cli/tv.py``. ``openamer tv`` and this
script both use ``add_tv_subcommands`` from there, so the two surfaces cannot
drift apart. Kept as a script because cron jobs and one-off shells should not
have to go through the full CLI import.

Usage:
    python scripts/tv_remote.py info
    python scripts/tv_remote.py key volup
    python scripts/tv_remote.py open https://openamer.com/tv.html
"""

import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from openamer_cli.tv import main  # noqa: E402  (after sys.path setup)

if __name__ == "__main__":
    sys.exit(main())
