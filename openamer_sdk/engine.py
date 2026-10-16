"""Real bridge between the SDK and ``run_agent.main(...)``.

This module does **not** re-implement an agent loop. It calls
``run_agent.main(...)`` — the same entry point ``python run_agent.py`` uses —
and observes the turn through two seams that the real code already provides:

1. ``run_agent.main`` builds ``AIAgent`` and calls
   ``agent.run_conversation(query)``. We temporarily bind the module-level
   ``AIAgent`` name to a recording proxy, so *main's own construction path*
   runs, the real ``AIAgent`` is really instantiated, and the result dict that
   ``main`` computes and then discards is captured.
2. ``main`` prints its whole report to stdout. We can capture that stream so a
   ``--json`` caller gets clean machine-readable output.

Both seams are removed in a ``finally``; the process-wide
``run_agent.AIAgent`` binding is restored even when the turn raises.

Why a proxy instead of parsing stdout: ``main`` returns ``None`` and its report
is prose. The result dict behind it (``final_response``, ``api_calls``,
``estimated_cost_usd``, token counters, ``completed``/``failed``) is the
engine's own structured truth, so the SDK reads that instead of scraping text.
"""

from __future__ import annotations

import contextlib
import importlib
import io
import threading
from typing import Any, Dict, Optional

from .errors import (
    OpenAmerConfigError,
    OpenAmerError,
    OpenAmerEngineError,
    OpenAmerTimeoutError,
)

__all__ = ["ENGINE_MODULE", "EngineCall", "call_engine_main"]

#: The module that holds the real one-task entry point and the agent class.
ENGINE_MODULE = "run_agent"

#: ``run_agent.main`` prints this and returns when the agent could not be built.
_INIT_FAILURE_MARKER = "Failed to initialize agent"


def _load_engine() -> Any:
    """Import and return the real engine module.

    Lazy on purpose: ``import openamer_sdk`` stays cheap and free of the
    engine's own import graph, and no network is touched at import time.
    """
    try:
        return importlib.import_module(ENGINE_MODULE)
    except Exception as exc:  # ModuleNotFoundError, ImportError, anything broken
        raise OpenAmerConfigError(
            "The OpenAmer engine module could not be imported",
            detail=f"{type(exc).__name__}: {exc}",
        ) from exc


class EngineCall:
    """What the instrumented call to ``run_agent.main`` observed."""

    def __init__(self) -> None:
        #: The turn result dict ``main`` got from ``run_conversation`` (its own
        #: truth — ``main`` throws it away).
        self.result: Optional[Dict[str, Any]] = None
        #: The real ``AIAgent`` instance main constructed.
        self.agent: Any = None
        #: The exact kwargs handed to ``run_agent.main``.
        self.main_kwargs: Dict[str, Any] = {}
        #: True once ``run_agent.main`` was actually entered.
        self.main_called = False
        #: Exception raised out of ``run_agent.main`` (worker-thread path only).
        self.error: Optional[BaseException] = None
        #: Everything ``main`` printed, when stdout capture was requested.
        self.stdout: str = ""


def _build_recorder(real_agent_cls: Any, capture: EngineCall, session_id: Optional[str]):
    """Return a class that stands in for ``run_agent.AIAgent`` for one call.

    The proxy instantiates the *real* class (captured before the swap, so there
    is no self-recursion) and records the turn result. Everything else is
    delegated, so ``main`` can keep using the agent as usual.
    """

    class _RecordingAgent:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self.__dict__["_real"] = None
            if session_id:
                # AIAgent accepts ``session_id`` and uses it for logging; it does
                # NOT replay prior turns. See ``resume`` in ``client``.
                kwargs.setdefault("session_id", session_id)
            real = real_agent_cls(*args, **kwargs)
            self.__dict__["_real"] = real
            capture.agent = real

        def run_conversation(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
            result = self.__dict__["_real"].run_conversation(*args, **kwargs)
            capture.result = result
            return result

        def __getattr__(self, name: str) -> Any:
            real = self.__dict__.get("_real")
            if real is None:
                raise AttributeError(name)
            return getattr(real, name)

    return _RecordingAgent


def _run_engine(module: Any, kwargs: Dict[str, Any], capture: EngineCall, timeout: Optional[float]) -> None:
    """Call ``module.main(**kwargs)``, inline or in a bounded worker thread."""
    capture.main_called = True
    if timeout is None:
        # Default path: call in the caller's own thread — exactly what
        # ``python run_agent.py`` does, no thread-affinity surprises.
        module.main(**kwargs)
        return

    done = threading.Event()

    def _work() -> None:
        try:
            module.main(**kwargs)
        except BaseException as exc:  # noqa: BLE001 - re-raised on the caller
            capture.error = exc
        finally:
            done.set()

    worker = threading.Thread(target=_work, name="openamer-sdk-engine", daemon=True)
    worker.start()
    if not done.wait(timeout):
        raise OpenAmerTimeoutError(
            f"The engine did not finish within {timeout}s",
            timeout=timeout,
            detail=(capture.stdout or "")[-2000:],
            query=kwargs.get("query"),
        )
    if capture.error is not None:
        raise capture.error


def call_engine_main(
    *,
    query: str,
    model: str = "",
    max_turns: Optional[int] = None,
    enabled_toolsets: Optional[str] = None,
    disabled_toolsets: Optional[str] = None,
    api_key: Optional[str] = None,
    base_url: str = "",
    timeout: Optional[float] = None,
    capture_output: bool = True,
    session_id: Optional[str] = None,
    extra_main_kwargs: Optional[Dict[str, Any]] = None,
    engine: Any = None,
) -> EngineCall:
    """Run one task by really calling ``run_agent.main(...)``.

    Returns the :class:`EngineCall` observation. Raises only on failure to
    produce a turn result:

    * :class:`OpenAmerConfigError` — engine not importable / not usable, or the
      engine's own init failure (main printed "Failed to initialize agent" and
      returned without a turn).
    * :class:`OpenAmerEngineError` — a turn ran but failed, or the engine
      returned without publishing any result dict.
    * :class:`OpenAmerTimeoutError` — ``timeout`` expired first.
    """
    module = engine if engine is not None else _load_engine()

    main_fn = getattr(module, "main", None)
    if not callable(main_fn):
        raise OpenAmerConfigError(
            "The OpenAmer engine module exposes no callable ``main``",
            detail=f"module={getattr(module, '__name__', module)!r}",
            query=query,
        )
    real_agent_cls = getattr(module, "AIAgent", None)
    if real_agent_cls is None:
        raise OpenAmerConfigError(
            "The OpenAmer engine module exposes no ``AIAgent`` class",
            detail=f"module={getattr(module, '__name__', module)!r}",
            query=query,
        )

    kwargs: Dict[str, Any] = {"query": query}
    if model:
        kwargs["model"] = model
    if max_turns is not None:
        kwargs["max_turns"] = max_turns
    if enabled_toolsets:
        kwargs["enabled_toolsets"] = enabled_toolsets
    if disabled_toolsets:
        kwargs["disabled_toolsets"] = disabled_toolsets
    if api_key:
        kwargs["api_key"] = api_key
    if base_url:
        kwargs["base_url"] = base_url
    if extra_main_kwargs:
        kwargs.update(extra_main_kwargs)

    capture = EngineCall()
    capture.main_kwargs = dict(kwargs)

    buffer = io.StringIO() if capture_output else None
    module.AIAgent = _build_recorder(real_agent_cls, capture, session_id)
    try:
        if buffer is None:
            _run_engine(module, kwargs, capture, timeout)
        else:
            # ``main`` narrates heavily (banner, tool log, summary). Redirect so
            # an embedding caller's stdout stays clean; the text is still
            # available as ``EngineCall.stdout``.
            with contextlib.redirect_stdout(buffer):
                _run_engine(module, kwargs, capture, timeout)
    except OpenAmerError:
        # Ours already carry a name (timeout / config / engine); never re-wrap.
        raise
    except Exception as exc:  # noqa: BLE001 -- translated into a named error below
        # The inline path runs ``main`` in this thread, so an engine failure
        # arrives here as a raw exception; the threaded path records it on
        # ``capture`` itself. Either way record it, so an embedding caller gets
        # the SDK's named error instead of whatever the engine happened to raise.
        capture.error = exc
    finally:
        module.AIAgent = real_agent_cls

    if buffer is not None:
        capture.stdout = buffer.getvalue()

    _raise_on_failure(capture, query=query)
    return capture


def _raise_on_failure(capture: EngineCall, *, query: str) -> None:
    """Translate an observation into the SDK's named failure, or return."""
    if capture.error is not None:
        raise OpenAmerEngineError(
            f"Engine raised {type(capture.error).__name__}: {capture.error}",
            detail=(capture.stdout or "")[-2000:],
            query=query,
        )

    result = capture.result
    if result is None:
        stdout_tail = (capture.stdout or "")[-2000:]
        if _INIT_FAILURE_MARKER in (capture.stdout or ""):
            raise OpenAmerConfigError(
                "The engine could not initialize an agent (check model and credentials)",
                detail=stdout_tail,
                query=query,
            )
        raise OpenAmerEngineError(
            "The engine returned without running a turn or publishing a result",
            detail=stdout_tail,
            query=query,
        )

    if result.get("failed"):
        raise OpenAmerEngineError(
            str(result.get("error") or "The engine reported a failed turn"),
            detail=(capture.stdout or "")[-2000:],
            query=query,
            result=result,
        )
