"""Embedding surface for OpenAmer: one task in, one structured result out.

The competitors all ship this (Claude Code's Agent SDK, Codex's TS SDK,
OpenHands' software-agent-sdk). OpenAmer's engine already existed —
``run_agent.main(...)`` is its programmatic one-task entry point — but there
was no importable package and no non-interactive CLI in front of it.

Both live here: :class:`OpenAmerClient` and ``openamer run`` call
:func:`openamer_sdk.engine.call_engine_main`, which really invokes
``run_agent.main(...)``.

Example
-------
>>> from openamer_sdk import OpenAmerClient
>>> client = OpenAmerClient(max_turns=3, toolsets="web")
>>> result = client.run("summarise today's OpenAmer commits")
>>> result.completed, result.turns, result.cost_usd
(True, 2, 0.0041)
>>> result.text
'...'
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Sequence, Union

from .engine import call_engine_main
from .errors import OpenAmerConfigError

__all__ = ["RunResult", "OpenAmerClient"]

ToolsetsArg = Union[str, Sequence[str], None]


def _normalise_toolsets(value: ToolsetsArg) -> Optional[str]:
    """Accept ``"web,vision"`` or ``["web", "vision"]`` and yield the CSV form.

    ``run_agent.main`` takes a comma-separated string, so the SDK normalises
    once here rather than making every caller remember that.
    """
    if value is None:
        return None
    if isinstance(value, str):
        parts = [p.strip() for p in value.split(",") if p.strip()]
    elif isinstance(value, (list, tuple, set, frozenset)):
        parts = [str(p).strip() for p in value if str(p).strip()]
    else:
        raise OpenAmerConfigError(
            "toolsets must be a comma-separated string or a sequence of names",
            detail=f"got {type(value).__name__}",
        )
    return ",".join(parts) if parts else None


@dataclass(frozen=True)
class RunResult:
    """The outcome of one task, as structured data — not a string.

    ``raw`` is the engine's own turn result dict, kept for callers that need a
    field this dataclass does not surface. It is deliberately excluded from
    :meth:`to_dict` so ``--json`` output is always serialisable.
    """

    #: The model's final answer.
    text: str
    #: Engine API calls spent on this task (``run_agent`` "api_calls").
    turns: int
    #: Estimated spend in USD for this session.
    cost_usd: float
    #: The session the engine logged this turn under.
    session_id: str
    #: True when the engine finished the turn successfully.
    completed: bool
    #: True when the engine reported the turn as failed.
    failed: bool
    #: True when the turn was interrupted (e.g. SIGINT).
    interrupted: bool
    #: Engine error string when the turn failed, else "".
    error: str
    #: Why the engine's loop ended (``turn_exit_reason``).
    turn_exit_reason: str
    model: str = ""
    provider: str = ""
    total_tokens: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    #: Number of messages in the conversation (not the messages themselves).
    message_count: int = 0
    #: The engine's own narration for this turn (captured stdout).
    stdout: str = ""
    #: True when this turn was written under a caller-supplied session id.
    session_continued: bool = False
    raw: Dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    def to_dict(self) -> Dict[str, Any]:
        """JSON-serialisable view — the payload behind ``openamer run --json``."""
        return {
            "text": self.text,
            "turns": self.turns,
            "cost_usd": self.cost_usd,
            "session_id": self.session_id,
            "completed": self.completed,
            "failed": self.failed,
            "interrupted": self.interrupted,
            "error": self.error,
            "turn_exit_reason": self.turn_exit_reason,
            "model": self.model,
            "provider": self.provider,
            "total_tokens": self.total_tokens,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "message_count": self.message_count,
            "session_continued": self.session_continued,
        }

    def to_json(self, *, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)


class OpenAmerClient:
    """Programmatic one-task entry point onto the OpenAmer engine.

    Parameters
    ----------
    model, api_key, base_url:
        Forwarded to ``run_agent.main``. Empty values leave the engine's own
        resolution (``config.yaml`` / ``.env``) in charge — the SDK never
        invents configuration.
    max_turns:
        Default ``max_turns`` for every ``run``. Defaults to 10, matching
        ``run_agent.main``'s own default.
    toolsets / no_toolsets:
        Default ``enabled_toolsets`` / ``disabled_toolsets``.
    timeout:
        Default wall-clock deadline in seconds. ``None`` (default) calls the
        engine inline in the caller's thread, which is the safest path; a
        timeout runs it in a daemon worker thread. See
        :class:`openamer_sdk.errors.OpenAmerTimeoutError`.
    capture_output:
        Capture the engine's stdout instead of letting it print (default True).
        Set False to watch the engine narrate live.
    engine:
        Test/integration seam. When ``None`` (default) the real ``run_agent``
        module is imported lazily on first use.
    """

    def __init__(
        self,
        *,
        model: str = "",
        api_key: Optional[str] = None,
        base_url: str = "",
        max_turns: int = 10,
        toolsets: ToolsetsArg = None,
        no_toolsets: ToolsetsArg = None,
        timeout: Optional[float] = None,
        capture_output: bool = True,
        engine: Any = None,
    ) -> None:
        if not isinstance(max_turns, int) or isinstance(max_turns, bool) or max_turns < 1:
            raise OpenAmerConfigError(
                "max_turns must be a positive integer", detail=f"got {max_turns!r}"
            )
        if timeout is not None and timeout <= 0:
            raise OpenAmerConfigError(
                "timeout must be positive (or None for no deadline)",
                detail=f"got {timeout!r}",
            )
        self.model = model
        self.api_key = api_key
        self.base_url = base_url
        self.max_turns = max_turns
        self.toolsets = _normalise_toolsets(toolsets)
        self.no_toolsets = _normalise_toolsets(no_toolsets)
        self.timeout = timeout
        self.capture_output = capture_output
        self._engine = engine

    # -- public API ---------------------------------------------------------

    def run(
        self,
        query: str,
        *,
        max_turns: Optional[int] = None,
        toolsets: ToolsetsArg = None,
        no_toolsets: ToolsetsArg = None,
        timeout: Optional[float] = None,
    ) -> RunResult:
        """Run one task to completion and return a structured result.

        Raises :class:`openamer_sdk.errors.OpenAmerConfigError`,
        :class:`OpenAmerEngineError` or :class:`OpenAmerTimeoutError` — each
        with a named ``reason``.
        """
        return self._execute(
            query,
            max_turns=max_turns,
            toolsets=toolsets,
            no_toolsets=no_toolsets,
            timeout=timeout,
            session_id=None,
        )

    def resume(
        self,
        session_id: str,
        query: str,
        *,
        max_turns: Optional[int] = None,
        toolsets: ToolsetsArg = None,
        no_toolsets: ToolsetsArg = None,
        timeout: Optional[float] = None,
    ) -> RunResult:
        """Run a follow-up task written under an existing ``session_id``.

        Honest scope — read this before relying on it:

        * What it does: the engine really runs (same ``run_agent.main`` path),
          and ``AIAgent`` is constructed with the given ``session_id``, so the
          turn is logged under that session instead of a fresh one. The
          returned ``session_id`` equals the one you passed
          (``session_continued`` is True).
        * What it does **not** do: it does not replay the earlier conversation
          to the model. ``run_agent.main`` has no conversation-history
          parameter, and ``AIAgent`` treats ``session_id`` as a logging id
          only, so the model starts this turn without the prior context.
          Passing prior context is not available through this entry point.
        """
        if not isinstance(session_id, str) or not session_id.strip():
            raise OpenAmerConfigError(
                "resume() needs a non-empty session_id string",
                detail=f"got {session_id!r}",
                query=query,
            )
        return self._execute(
            query,
            max_turns=max_turns,
            toolsets=toolsets,
            no_toolsets=no_toolsets,
            timeout=timeout,
            session_id=session_id.strip(),
        )

    # -- internals ----------------------------------------------------------

    def _execute(
        self,
        query: str,
        *,
        max_turns: Optional[int],
        toolsets: ToolsetsArg,
        no_toolsets: ToolsetsArg,
        timeout: Optional[float],
        session_id: Optional[str],
    ) -> RunResult:
        if not isinstance(query, str) or not query.strip():
            raise OpenAmerConfigError(
                "query must be a non-empty string", detail=f"got {query!r}"
            )

        effective_max_turns = self.max_turns if max_turns is None else max_turns
        if (
            not isinstance(effective_max_turns, int)
            or isinstance(effective_max_turns, bool)
            or effective_max_turns < 1
        ):
            raise OpenAmerConfigError(
                "max_turns must be a positive integer",
                detail=f"got {effective_max_turns!r}",
                query=query,
            )

        effective_timeout = self.timeout if timeout is None else timeout
        if effective_timeout is not None and effective_timeout <= 0:
            raise OpenAmerConfigError(
                "timeout must be positive (or None for no deadline)",
                detail=f"got {effective_timeout!r}",
                query=query,
            )

        call = call_engine_main(
            query=query,
            model=self.model,
            max_turns=effective_max_turns,
            enabled_toolsets=_normalise_toolsets(toolsets)
            if toolsets is not None
            else self.toolsets,
            disabled_toolsets=_normalise_toolsets(no_toolsets)
            if no_toolsets is not None
            else self.no_toolsets,
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=self.timeout if timeout is None else effective_timeout,
            capture_output=self.capture_output,
            session_id=session_id,
            engine=self._engine,
        )

        return _build_result(call, session_continued=session_id is not None)


def _build_result(call: Any, *, session_continued: bool) -> RunResult:
    """Map the engine's own turn result dict onto :class:`RunResult`."""
    result: Dict[str, Any] = call.result or {}
    agent = call.agent

    session_id = (
        result.get("session_id")
        or getattr(agent, "session_id", "")
        or ""
    )

    messages = result.get("messages") or []

    def _num(key: str) -> float:
        value = result.get(key)
        return float(value) if isinstance(value, (int, float)) else 0.0

    def _int(key: str) -> int:
        value = result.get(key)
        return int(value) if isinstance(value, (int, float)) else 0

    return RunResult(
        text=str(result.get("final_response") or ""),
        turns=_int("api_calls"),
        cost_usd=_num("estimated_cost_usd"),
        session_id=str(session_id),
        completed=bool(result.get("completed")),
        failed=bool(result.get("failed")),
        interrupted=bool(result.get("interrupted")),
        error=str(result.get("error") or ""),
        turn_exit_reason=str(result.get("turn_exit_reason") or ""),
        model=str(result.get("model") or getattr(agent, "model", "") or ""),
        provider=str(result.get("provider") or getattr(agent, "provider", "") or ""),
        total_tokens=_int("total_tokens"),
        input_tokens=_int("input_tokens"),
        output_tokens=_int("output_tokens"),
        message_count=len(messages),
        stdout=call.stdout or "",
        session_continued=session_continued,
        raw=dict(result),
    )


def run(query: str, **kwargs: Any) -> RunResult:
    """One-shot convenience: ``run("do this", max_turns=3)``.

    Accepts the same kwargs as :class:`OpenAmerClient`, minus the per-run
    overrides that have no meaning for a single call.
    """
    client_kwargs = {
        key: kwargs.pop(key)
        for key in (
            "model",
            "api_key",
            "base_url",
            "max_turns",
            "toolsets",
            "no_toolsets",
            "timeout",
            "capture_output",
            "engine",
        )
        if key in kwargs
    }
    if kwargs:
        raise OpenAmerConfigError(
            "run() got unexpected keyword arguments",
            detail=", ".join(sorted(kwargs)),
        )
    return OpenAmerClient(**client_kwargs).run(query)
