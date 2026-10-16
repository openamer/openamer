"""OpenAmer embedding SDK — one task in, one structured result out.

    from openamer_sdk import OpenAmerClient

    result = OpenAmerClient(max_turns=3, toolsets="web").run("summarise the repo")
    print(result.text, result.turns, result.cost_usd, result.session_id)

This is the surface every adjacent agent already ships (Claude Code's Agent
SDK, Codex's TypeScript SDK, OpenHands' software-agent-sdk); OpenAmer had the
engine but no importable package in front of it.

Guarantees:

* ``import openamer_sdk`` touches no network and imports no engine internals —
  ``run_agent`` is imported lazily on the first :meth:`OpenAmerClient.run`.
* Every call really goes through ``run_agent.main(...)`` (see
  :mod:`openamer_sdk.engine`) — there is no second agent loop here.
* Results are structured (:class:`RunResult`), never a bare string, and
  failures carry a named ``reason`` (``timeout`` / ``engine`` / ``config``).
"""

from __future__ import annotations

from .client import OpenAmerClient, RunResult, run
from .errors import (
    REASON_CONFIG,
    REASON_ENGINE,
    REASON_TIMEOUT,
    OpenAmerConfigError,
    OpenAmerEngineError,
    OpenAmerError,
    OpenAmerTimeoutError,
)

__version__ = "0.1.0"

__all__ = [
    "OpenAmerClient",
    "RunResult",
    "run",
    "OpenAmerError",
    "OpenAmerConfigError",
    "OpenAmerEngineError",
    "OpenAmerTimeoutError",
    "REASON_CONFIG",
    "REASON_ENGINE",
    "REASON_TIMEOUT",
    "__version__",
]
