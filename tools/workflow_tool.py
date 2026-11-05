"""Model-facing ``workflow`` tool: run a model-written orchestration script.

Adapted from deepseek-ai/deepseek-harness ``packages/workflow`` +
``packages/workflow/tool-workflow``. Upstream runs a plain-JavaScript
body; this port uses Python, the native language of the OpenAmer agent,
so no JS runtime has to be shipped into the core.

What it adds over ``delegate_task``
-----------------------------------
``delegate_task`` runs a *fixed list* of tasks in one batch. It cannot
express control flow — "run these three audits in parallel, then take
their findings and run a fourth pass over what they disagreed about".
That is the shape of most real multi-agent work.

The workflow script gives the model that control flow. The script body
may use ``await agent(...)``, ``await parallel([...])``,
``await pipeline(items, step)``, ``phase(name)`` and ``log(message)``,
and its return value becomes the tool result.

The model sees ONE final outcome — never the intermediate child
messages — because the tool blocks until the whole workflow settles.
"""
from __future__ import annotations

import asyncio
import json
import logging
import threading
from typing import Any, Dict, List, Optional

from tools.registry import registry, tool_error

logger = logging.getLogger(__name__)


WORKFLOW_SCRIPT_RULES = """
Python body (not a module). Top-level `await` allowed; end with `return <value>`.
Hooks: `await agent(prompt, context=None)` -> str (one subagent's final text;
the subagent sees nothing of this conversation, so the prompt must be
self-contained); `await parallel([...])` -> list (independent entries,
order preserved); `await pipeline(items, step)` -> list (step(item, prev)
may see the previous result); `phase(name)`; `log(message)`. `args` holds
the optional JSON passed with the call. No `import`, `open`, `eval`,
`exec`. A script that raises returns an error, never a partial success.
""".strip()


WORKFLOW_SCHEMA = {
    "name": "workflow",
    "description": (
        "Run a Python orchestration script that fans work out to subagents "
        "and returns the script's final value. Use it when a task "
        "decomposes into many pieces that need CONTROL FLOW - a second "
        "pass that depends on the first, parallel audits whose findings "
        "are cross-checked, a migration with dependent steps. For one or "
        "two independent delegations use delegate_task instead; it is "
        "simpler and cheaper."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "meta": {
                "type": "object",
                "description": (
                    "Identity of the workflow: `name` and `description` are "
                    "required; `phases` may list the phases you expect."
                ),
                "properties": {
                    "name": {"type": "string", "description": "Workflow name"},
                    "description": {"type": "string", "description": "What it does"},
                    "phases": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional list of phase names",
                    },
                },
                "required": ["name", "description"],
            },
            "script": {
                "type": "string",
                "description": WORKFLOW_SCRIPT_RULES,
            },
            "args": {
                "type": "object",
                "description": (
                    "Optional JSON data exposed to the script as `args`. "
                    "Wrap a bare list in a field so the shape stays clear."
                ),
            },
        },
        "required": ["meta", "script"],
    },
}


def _validate_meta(meta: Any) -> Optional[str]:
    """Return an error message when the meta block is invalid."""
    if not isinstance(meta, dict):
        return "meta must be an object with 'name' and 'description'."
    for key in ("name", "description"):
        value = meta.get(key)
        if not isinstance(value, str) or not value.strip():
            return f"meta.{key} is required and must be a non-empty string."
    phases = meta.get("phases")
    if phases is not None and not isinstance(phases, list):
        return "meta.phases must be a list of strings."
    return None


def _build_agent_hook(parent_agent, max_iterations: Optional[int]):
    """Build the ``agent()`` hook backed by real delegated subagents.

    Every child goes through the same ``_build_child_agent`` /
    ``_run_single_child`` path as ``delegate_task``, so the delegation
    limits (max_concurrent_children, max_spawn_depth, the pause kill
    switch, credential leasing) all apply unchanged.
    """
    from tools.delegate_tool import (
        _build_child_agent,
        _get_max_concurrent_children,
        _run_single_child,
    )

    state = {"index": 0}
    lock = threading.Lock()

    def _hook(prompt: str, context: Optional[str] = None, **kwargs) -> str:
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("agent() requires a non-empty prompt.")

        with lock:
            index = state["index"]
            state["index"] += 1

        child = _build_child_agent(
            task_index=index,
            goal=prompt,
            context=context,
            toolsets=None,
            model=None,
            max_iterations=max_iterations or 25,
            task_count=1,
            parent_agent=parent_agent,
        )
        result = _run_single_child(index, prompt, child, parent_agent)
        return _extract_summary(result)

    return _hook


def _extract_summary(result: Any) -> str:
    """Pull the child's final text out of the structured child result."""
    if isinstance(result, dict):
        for key in ("summary", "output", "result", "final_response"):
            value = result.get(key)
            if isinstance(value, str) and value.strip():
                return value
        # Fall back to the last message content the child produced.
        messages = result.get("messages")
        if isinstance(messages, list):
            for message in reversed(messages):
                if isinstance(message, dict) and message.get("role") == "assistant":
                    content = message.get("content")
                    if isinstance(content, str) and content.strip():
                        return content
    if isinstance(result, str):
        return result
    return json.dumps(result, ensure_ascii=False, default=str)


def workflow_tool(
    meta: Optional[Dict[str, Any]] = None,
    script: Optional[str] = None,
    args: Optional[Dict[str, Any]] = None,
    parent_agent=None,
    **kwargs,
) -> str:
    """Execute a model-written workflow script and return its value."""
    if parent_agent is None:
        return tool_error("workflow requires a parent agent context.")

    meta_error = _validate_meta(meta)
    if meta_error:
        return tool_error(meta_error)

    if not isinstance(script, str) or not script.strip():
        return tool_error("workflow requires a non-empty 'script'.")

    from agent.workflow_runtime import WorkflowError, WorkflowRunner

    try:
        from tools.delegate_tool import _get_max_concurrent_children
    except Exception:  # pragma: no cover - defensive
        _get_max_concurrent_children = lambda: 3  # type: ignore[assignment]

    progress_lines: List[str] = []

    def _progress(message: str) -> None:
        progress_lines.append(message)
        vprint = getattr(parent_agent, "_vprint", None)
        if callable(vprint):
            try:
                vprint(f"  🔀 {message}", force=True)
            except Exception:
                pass

    runner = WorkflowRunner(
        agent_hook=_build_agent_hook(parent_agent, kwargs.get("max_iterations")),
        progress_callback=_progress,
        max_parallel=_get_max_concurrent_children(),
    )

    try:
        result = asyncio.run(runner.run(script, args or {}))
    except WorkflowError as exc:
        return tool_error(f"Workflow failed: {exc}")
    except Exception as exc:
        logger.warning("Workflow script failed: %s", exc)
        return tool_error(f"Workflow failed: {type(exc).__name__}: {exc}")

    name = (meta or {}).get("name", "workflow")
    payload = {
        "kind": "foreground",
        "name": name,
        "agentsStarted": result.agents_started,
        "result": result.value,
        "phases": result.phases,
    }
    if progress_lines:
        payload["logs"] = progress_lines

    return json.dumps(payload, ensure_ascii=False, indent=2, default=str)


def check_workflow_requirements() -> bool:
    """The tool needs a working delegation path."""
    try:
        from tools.delegate_tool import check_delegate_requirements

        return bool(check_delegate_requirements())
    except Exception:
        return False


registry.register(
    name="workflow",
    toolset="workflow",
    schema=WORKFLOW_SCHEMA,
    handler=lambda args, **kw: workflow_tool(
        meta=args.get("meta"),
        script=args.get("script"),
        args=args.get("args"),
        parent_agent=kw.get("parent_agent"),
        max_iterations=kw.get("max_iterations"),
    ),
    check_fn=check_workflow_requirements,
    emoji="🧩",
)
