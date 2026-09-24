"""
ASI Subsystems — in-process imports from training scripts.

Each subsystem wraps a scripts/training/*.py module, importing its core
functions directly (no subprocess). The scripts still work standalone
for cron/legacy use, but the ASI Core calls them natively.
"""

from . import self_model  # noqa: F401
from . import world_model  # noqa: F401
from . import reasoning  # noqa: F401
from . import prediction  # noqa: F401
from . import improvement  # noqa: F401
