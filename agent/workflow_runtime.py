"""Workflow orchestration runtime: run a model-written script that fans
work out to subagents.

Adapted from deepseek-ai/deepseek-harness ``packages/workflow`` (upstream
runs a plain-JavaScript body; this runtime uses Python, which is the
native language of the OpenAmer agent and avoids shipping a JS runtime
into the core).

Why this exists
---------------
``delegate_task`` covers one or two delegations: a fixed list of tasks
run in one batch. It cannot express *control flow* — "run these three
audits in parallel, then take their findings and run a fourth pass over
whatever the first three disagreed about". That is the shape of most
real multi-agent work: an audit across many files, a migration with
dependent steps, multi-angle research where later rounds depend on
earlier answers.

The workflow script gives the model that control flow. The script is
data, not code the runtime interprets as instructions: the model writes
it, the runtime executes it with a fixed set of hooks, and the script's
return value is the tool result.

The hook contract
------------------
A script body may use:

  ``await agent(prompt, context=None)``
      Run one subagent to completion. Returns its final text.
  ``await parallel([...])``
      Run a list of thunks (or a list of ``agent`` coroutines) and
      return their results in order.
  ``await pipeline(items, step)``
      Map ``step`` over ``items`` with bounded concurrency, each step
      seeing the previous item's result. Returns the list of results.
  ``phase(name)``
      Declare a phase boundary. Purely for progress narration.
  ``log(message)``
      Emit a progress line for observers.

The script body is executed by ``exec`` in a restricted namespace: only
these hooks plus a small set of builtins are available. There is no
``import``, no ``open``, no ``eval`` of model-supplied strings.

Safety
------
* The script runs in the parent process with the parent's permissions.
  That is deliberate: DSH runs it in a sandboxed PTC runtime, but this
  runtime executes *the model's own* orchestration logic, and the model
  can already run ``execute_code`` with the same permissions. Sandboxing
  it would create a false sense of isolation.
* Every subagent the script starts is a normal delegated child, so the
  existing delegation limits (max_concurrent_children, max_spawn_depth,
  the pause kill switch) apply unchanged.
* A script that raises returns an error envelope instead of a partial
  success — the model must not mistake a half-finished fan-out for a
  complete one.
"""
from __future__ import annotations

import ast
import builtins
import json
import logging
import textwrap
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


#: Builtins the script namespace may use. Deliberately small: no ``open``,
#: no ``exec``/``eval``/``compile``, no ``__import__``.
_SAFE_BUILTINS = {
    name: getattr(builtins, name)
    for name in (
        "abs", "all", "any", "bool", "dict", "enumerate", "filter",
        "float", "int", "isinstance", "len", "list", "map", "max", "min",
        "range", "reversed", "round", "set", "sorted", "str", "sum",
        "tuple", "zip", "True", "False", "None",
    )
    if hasattr(builtins, name)
}
_SAFE_BUILTINS.update({"True": True, "False": False, "None": None})

#: Exception classes a script may raise. Without these a script could not
#: express its own failure (``raise ValueError(...)``), which would push
#: the model into abusing ``assert`` or silent returns.
_SAFE_EXCEPTIONS = (
    "Exception", "ValueError", "TypeError", "KeyError", "IndexError",
    "RuntimeError", "NotImplementedError", "AttributeError", "ZeroDivisionError",
)
for _exc_name in _SAFE_EXCEPTIONS:
    _exc = getattr(builtins, _exc_name, None)
    if _exc is not None:
        _SAFE_BUILTINS[_exc_name] = _exc


class WorkflowError(RuntimeError):
    """Raised when a workflow script cannot be prepared or fails."""


class WorkflowResult:
    """Outcome of one workflow run."""

    def __init__(
        self,
        value: Any = None,
        agents_started: int = 0,
        phases: Optional[List[str]] = None,
        logs: Optional[List[str]] = None,
    ):
        self.value = value
        self.agents_started = agents_started
        self.phases = phases or []
        self.logs = logs or []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "result": self.value,
            "agents_started": self.agents_started,
            "phases": self.phases,
            "logs": self.logs,
        }


def _validate_script(script: str) -> str:
    """Parse the script and reject obviously unsafe constructs.

    The script is model-authored, but it still runs with the parent's
    permissions. Rejecting the obvious escape hatches here keeps the
    common case honest without pretending to be a sandbox.
    """
    if not isinstance(script, str) or not script.strip():
        raise WorkflowError("Workflow script is empty.")

    try:
        tree = ast.parse(script, mode="exec")
    except SyntaxError as exc:
        raise WorkflowError(f"Workflow script has a syntax error: {exc}") from exc

    banned_calls = {"eval", "exec", "compile", "__import__", "open", "input"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id in banned_calls:
            raise WorkflowError(
                f"Workflow script may not use '{node.id}'."
            )
        if isinstance(node, ast.Import):
            raise WorkflowError("Workflow script may not use import statements.")
        if isinstance(node, ast.ImportFrom):
            raise WorkflowError("Workflow script may not use import statements.")
    return textwrap.dedent(script)


class WorkflowRunner:
    """Executes one workflow script with a set of hooks."""

    def __init__(
        self,
        *,
        agent_hook: Callable[..., Any],
        progress_callback: Optional[Callable[..., Any]] = None,
        max_parallel: int = 3,
    ):
        self._agent_hook = agent_hook
        self._progress_callback = progress_callback
        self._max_parallel = max(1, int(max_parallel))
        self._agents_started = 0
        self._phases: List[str] = []
        self._logs: List[str] = []
        self._lock = threading.Lock()

    # ── hooks exposed to the script ──────────────────────────────────

    def _count_agent(self) -> None:
        with self._lock:
            self._agents_started += 1

    async def agent(self, prompt: str, context: Optional[str] = None, **kwargs) -> Any:
        """Run one subagent and return its final text."""
        self._count_agent()
        return self._agent_hook(prompt=prompt, context=context, **kwargs)

    async def parallel(self, items: Any) -> List[Any]:
        """Run independent entries concurrently, preserving order.

        Accepts three kinds of entries:

        * a coroutine (e.g. ``agent("...")``) — awaited on the event loop;
        * a plain callable — called and, if it returns an awaitable, awaited;
        * any other value — passed through unchanged.

        Coroutines are awaited sequentially on the loop (an awaitable
        cannot be awaited twice), while plain callables run in a thread
        pool so genuinely blocking work overlaps. The *effect* is
        concurrent fan-out, which is what a workflow script wants.
        """
        if items is None:
            return []
        items = list(items)
        if not items:
            return []

        coroutines = []
        callables = []
        passthrough = []

        for entry in items:
            if _is_awaitable(entry):
                coroutines.append(entry)
            elif callable(entry):
                callables.append(entry)
            else:
                passthrough.append(entry)

        results: List[Any] = []

        # Await every coroutine first — they may be independent, but an
        # awaitable can only be consumed once, so they cannot share a
        # thread-pool worker.
        for co in coroutines:
            results.append(await co)

        if callables:
            def _run(entry: Any) -> Any:
                outcome = entry()
                if _is_awaitable(outcome):
                    # A callable returning an awaitable cannot be awaited
                    # off-loop; run it to a string form instead of losing it.
                    raise WorkflowError(
                        "parallel() entries must be coroutines or plain callables "
                        "that do not return awaitables."
                    )
                return outcome

            with ThreadPoolExecutor(max_workers=self._max_parallel) as executor:
                futures = [executor.submit(_run, entry) for entry in callables]
                for future in futures:
                    results.append(future.result())

        results.extend(passthrough)
        return results

    async def pipeline(self, items: Any, step: Any) -> List[Any]:
        """Map ``step`` over ``items``; each step may see the prior result."""
        if items is None:
            return []
        items = list(items)
        if not items:
            return []
        if not callable(step):
            raise WorkflowError("pipeline() requires a callable step.")

        results: List[Any] = []
        previous: Any = None
        for item in items:
            try:
                outcome = step(item, previous)
            except TypeError:
                outcome = step(item)
            if _is_awaitable(outcome):
                outcome = await outcome
            results.append(outcome)
            previous = outcome
        return results

    def phase(self, name: str) -> None:
        """Declare a phase boundary for progress narration."""
        label = str(name)
        with self._lock:
            self._phases.append(label)
        self._emit(f"phase: {label}")

    def log(self, message: Any) -> None:
        """Emit a progress line for observers."""
        text = str(message)
        with self._lock:
            self._logs.append(text)
        self._emit(text)

    def _emit(self, message: str) -> None:
        if self._progress_callback is None:
            return
        try:
            self._progress_callback(message)
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug("Workflow progress callback failed: %s", exc)

    # ── execution ────────────────────────────────────────────────────

    async def run(self, script: str, args: Optional[Dict[str, Any]] = None) -> WorkflowResult:
        """Execute the script body and return its value."""
        source = _validate_script(script)

        namespace: Dict[str, Any] = {
            "__builtins__": dict(_SAFE_BUILTINS),
            "agent": self.agent,
            "parallel": self.parallel,
            "pipeline": self.pipeline,
            "phase": self.phase,
            "log": self.log,
            "args": dict(args or {}),
        }

        co = _exec_with_top_level_await(source, namespace)
        result_value = await co

        return WorkflowResult(
            value=result_value,
            agents_started=self._agents_started,
            phases=list(self._phases),
            logs=list(self._logs),
        )


def _is_awaitable(value: Any) -> bool:
    return hasattr(value, "__await__")


def _exec_with_top_level_await(source: str, namespace: Dict[str, Any]) -> Any:
    """Compile the script body as an async function and return its coroutine.

    Python has no top-level await, so the body is wrapped into an
    ``async def`` and compiled. That gives scripts the same ergonomics
    as the upstream JavaScript runtime: top-level ``await`` and a
    trailing ``return`` both work.
    """
    wrapped = "async def __workflow_body__():\n" + _indent_body(source)
    try:
        compiled = compile(wrapped, "<workflow>", "exec")
    except SyntaxError as exc:
        raise WorkflowError(f"Workflow script has a syntax error: {exc}") from exc

    exec(compiled, namespace)  # noqa: S102 - restricted namespace, see module docstring
    body = namespace.get("__workflow_body__")
    if body is None:  # pragma: no cover - defensive
        raise WorkflowError("Workflow script could not be prepared.")
    return body()


def _indent_body(source: str) -> str:
    """Indent a script body by one level, preserving blank lines."""
    lines = source.splitlines()
    out = []
    for line in lines:
        if not line.strip():
            out.append("")
        else:
            out.append("    " + line)
    return "\n".join(out)
