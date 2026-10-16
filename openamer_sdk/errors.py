"""Error hierarchy for the OpenAmer embedding SDK.

Every failure the SDK can produce carries a *named* reason (``timeout``,
``engine``, ``config``) instead of a bare ``bool`` — so a caller can branch on
``exc.reason`` without string-matching a message, and can read ``exc.detail``
for the raw engine output that produced the failure.

Design rule: a caller that gets no exception got a real turn result. Anything
that prevented a real turn result raises.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

__all__ = [
    "REASON_CONFIG",
    "REASON_ENGINE",
    "REASON_TIMEOUT",
    "OpenAmerError",
    "OpenAmerConfigError",
    "OpenAmerEngineError",
    "OpenAmerTimeoutError",
]

#: The SDK could not build a valid request (bad argument, engine not importable).
REASON_CONFIG = "config"
#: The engine ran but did not produce a usable turn result.
REASON_ENGINE = "engine"
#: The engine did not finish inside the caller's deadline.
REASON_TIMEOUT = "timeout"


class OpenAmerError(Exception):
    """Base class for every SDK failure.

    Attributes
    ----------
    reason:
        One of ``REASON_CONFIG`` / ``REASON_ENGINE`` / ``REASON_TIMEOUT``.
    message:
        Short human-readable summary.
    detail:
        Raw supporting output (engine stdout tail, exception text). May be empty.
    query:
        The query that was being run, when known.
    result:
        The engine's own turn result dict when the engine produced one but
        reported failure (``OpenAmerEngineError`` only). ``None`` otherwise.
    """

    reason = REASON_ENGINE

    def __init__(
        self,
        message: str,
        *,
        detail: str = "",
        query: Optional[str] = None,
        result: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.detail = detail or ""
        self.query = query
        self.result = result

    def to_dict(self) -> Dict[str, Any]:
        """Machine-readable form for ``openamer run --json``."""
        return {
            "error": type(self).__name__,
            "reason": self.reason,
            "message": self.message,
            "detail": self.detail,
            "query": self.query,
        }

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.message


class OpenAmerConfigError(OpenAmerError):
    """The request or the engine binding was unusable before any turn ran.

    Raised for: empty query, non-positive ``max_turns``, an unimportable
    engine module, an engine module with no ``AIAgent`` class, and the
    engine's own "could not initialize an agent" exit (missing model or
    credentials) — that last case is a configuration problem, not a turn
    failure.
    """

    reason = REASON_CONFIG


class OpenAmerEngineError(OpenAmerError):
    """The engine ran but the turn failed or produced no result.

    ``exc.result`` carries the engine's own result dict when there is one, so
    the caller can still read tokens/cost/messages off a failed turn.
    """

    reason = REASON_ENGINE


class OpenAmerTimeoutError(OpenAmerError):
    """The engine did not return inside ``timeout`` seconds.

    The engine call runs in a daemon worker thread; Python cannot forcibly
    kill it, so the abandoned turn may keep running and keep spending until it
    finishes on its own. This is a documented limitation, not a silent
    behaviour: prefer a deadline you are comfortable honouring.
    """

    reason = REASON_TIMEOUT

    def __init__(
        self,
        message: str,
        *,
        timeout: Optional[float] = None,
        detail: str = "",
        query: Optional[str] = None,
    ) -> None:
        super().__init__(message, detail=detail, query=query)
        self.timeout = timeout

    def to_dict(self) -> Dict[str, Any]:
        payload = super().to_dict()
        payload["timeout"] = self.timeout
        return payload
