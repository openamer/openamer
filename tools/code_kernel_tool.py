#!/usr/bin/env python3
"""``code_kernel`` — run Python cells in a session-persistent interpreter.

WHY THIS TOOL EXISTS
    ``execute_code`` starts a fresh interpreter per call, so anything a task
    computes in one call is gone in the next and every turn pays to re-import and
    re-load. This tool keeps one child alive per session and execs one cell per
    call, so a variable, import or loaded model survives between cells.

WHAT IT DOES NOT DO
    It does not widen the sandbox. A cell runs through the SAME envelope as a
    one-shot ``execute_code`` call — the project's own env scrubber, interpreter
    and cwd resolution, generated ``openamer_tools`` module, and the project's
    process-group kill path. Only the process LIFETIME changes. See
    ``tools/code_kernel.py`` for the mechanism and the failure model.

CALLER CONTRACT
    - ``reset=true`` tears this session's kernel down first, so a fresh process
      picks up a changed env or an edited module. Env is frozen at spawn: a
      variable exported later is invisible until reset.
    - A cell that exceeds ``timeout`` has the kernel stopped and its state lost,
      deliberately — a Python frame cannot be interrupted in place safely. The
      error says so rather than pretending the state can be resumed.
    - The result names the kernel (``owner:mode:generation``), so which process
      answered is never a guess.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

from tools.registry import registry

logger = logging.getLogger(__name__)

CODE_KERNEL_SCHEMA: Dict[str, Any] = {
    "name": "code_kernel",
    "description": (
        "Run Python in a SESSION-PERSISTENT interpreter, so variables, imports and "
        "loaded data survive between calls.\n\n"
        "Use this instead of running the same setup twice: a model, a loaded "
        "DataFrame or an expensive import is paid for once and reused in later "
        "cells. Use plain per-call execution when a one-off snippet is all you "
        "need and no state has to carry over.\n\n"
        "**Cells share one namespace.** ``x = 1`` in one cell is visible in the "
        "next. An error in a cell is reported and the kernel stays alive, so the "
        "state is still there afterwards.\n\n"
        "**Environment is frozen at spawn.** A variable exported after the kernel "
        "started is NOT visible inside it. Pass ``reset=true`` to discard the "
        "kernel and get a fresh process that picks the change up.\n\n"
        "**Timeouts lose state on purpose.** A cell may run for at most "
        "``timeout`` seconds (default 60). A cell that exceeds it has its process "
        "tree killed and the kernel dropped; the next call starts clean. Long work "
        "belongs in a cell that writes its progress somewhere durable.\n\n"
        "**Sandboxed like every other code path** — the same environment "
        "scrubbing, interpreter and working-directory resolution, tool whitelist "
        "and secret redaction as the standard code execution path. Only the "
        "process lifetime differs."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": "Python source for one cell. Its globals persist into the next cell.",
            },
            "reset": {
                "type": "boolean",
                "description": (
                    "Discard this session's kernel first and start a fresh "
                    "interpreter (use after changing environment variables or an "
                    "imported module). Default false."
                ),
            },
            "timeout": {
                "type": "number",
                "description": "Max seconds for this cell (default 60, max 1800).",
            },
        },
        "required": ["code"],
    },
}


def code_kernel(code: str, task_id: Optional[str] = None, reset: bool = False,
                timeout: Optional[float] = None) -> str:
    """Handler: run one cell and return a JSON string, like every other tool."""
    from tools.code_kernel import KernelError, _DEFAULT_CELL_TIMEOUT, run_in_kernel

    if not code or not code.strip():
        return json.dumps({"success": False, "error": "code is empty"})
    try:
        result = run_in_kernel(
            code,
            task_id=task_id,
            timeout=float(timeout) if timeout else _DEFAULT_CELL_TIMEOUT,
            reset=bool(reset),
        )
    except KernelError as exc:
        # Reported verbatim: a kernel failure is the caller's information, not an
        # internal detail to be swallowed.
        return json.dumps({"success": False, "error": str(exc), "kernel_lost": True})
    except Exception as exc:
        logger.debug("code_kernel failed", exc_info=True)
        return json.dumps({"success": False, "error": f"{type(exc).__name__}: {exc}"})
    return json.dumps(result, ensure_ascii=False)


registry.register(
    name="code_kernel",
    toolset="code_execution",
    schema=CODE_KERNEL_SCHEMA,
    handler=lambda args, **kw: code_kernel(
        code=args.get("code", ""),
        task_id=kw.get("task_id"),
        reset=bool(args.get("reset", False)),
        timeout=args.get("timeout"),
    ),
    check_fn=lambda: True,
    emoji="🔁",
    max_result_size_chars=100_000,
)
