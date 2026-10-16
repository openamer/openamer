"""``openamer run`` — non-interactive single-task command.

One task in, one answer out, no REPL and no prompts. This is the CLI half of
the embedding surface; the library half is :mod:`openamer_sdk`. Both go through
:func:`openamer_sdk.engine.call_engine_main`, which really calls
``run_agent.main(...)`` — so ``openamer run`` and
``OpenAmerClient(...).run(...)`` share one code path.

Usage
-----
    openamer run "summarise today's commits"
    openamer run "audit this file" --max-turns 5 --toolsets safe
    openamer run "count the tests" --json

Flag notes
----------
* ``-p`` is deliberately NOT used here: the CLI's pre-parser already binds
  ``-p`` / ``--profile`` to profile selection (``openamer_cli/main.py``), and
  the parser-level tests pin that. Use ``--json`` and ``--max-turns``.
* ``--json`` writes exactly one JSON object to stdout and nothing else, so the
  engine's own narration stays out of the machine-readable stream.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, List, Optional

__all__ = ["build_run_parser"]


def _split_toolsets(raw: Optional[str]) -> Optional[List[str]]:
    """``"web,vision"`` -> ``["web", "vision"]``; ``None``/blank -> ``None``."""
    if raw is None:
        return None
    parts = [part.strip() for part in raw.split(",") if part.strip()]
    return parts or None


def build_run_parser(subparsers: Any) -> None:
    """Attach the ``run`` subcommand to ``subparsers``.

    Handlers live in this module (``_cmd_run``) so ``main.py`` needs only the
    import plus the one call — no handler code in the god-file.
    """
    parser = subparsers.add_parser(
        "run",
        help="Run a single task non-interactively and print the result",
        description=(
            "Run one task through the OpenAmer engine and exit. Non-interactive:\n"
            "no prompts, no REPL. Uses the same entry point as the Python SDK\n"
            "(openamer_sdk.OpenAmerClient), backed by run_agent.main().\n\n"
            "Exit code is 0 when the turn completed, 1 otherwise."
        ),
    )
    parser.add_argument(
        "task",
        help="The task to run, as one argument",
    )
    parser.add_argument(
        "--max-turns",
        type=int,
        default=None,
        dest="max_turns",
        help="Maximum engine API-call iterations (default: engine default, 10)",
    )
    parser.add_argument(
        "--toolsets",
        default=None,
        help='Comma-separated toolsets to enable, e.g. "web,vision"',
    )
    parser.add_argument(
        "--no-toolsets",
        default=None,
        dest="no_toolsets",
        help='Comma-separated toolsets to disable, e.g. "terminal"',
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="Machine-readable output: one JSON object (result, turns, cost)",
    )
    parser.add_argument(
        "--model",
        default="",
        help="Model override (defaults to the configured model)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=None,
        help="Wall-clock deadline in seconds (default: no deadline)",
    )
    parser.set_defaults(func=_cmd_run)


def _cmd_run(args: Any) -> int:
    """Run one task and print the result. Returns the process exit code."""
    # Imported inside the handler: keeps `openamer --help` fast and keeps the
    # SDK out of the CLI's import graph for every other subcommand.
    from openamer_sdk import OpenAmerClient
    from openamer_sdk.errors import OpenAmerError

    as_json = bool(getattr(args, "as_json", False))
    task = getattr(args, "task", "") or ""

    client_kwargs: dict = {"model": getattr(args, "model", "") or ""}
    max_turns = getattr(args, "max_turns", None)
    if max_turns is not None:
        client_kwargs["max_turns"] = max_turns
    toolsets = _split_toolsets(getattr(args, "toolsets", None))
    if toolsets is not None:
        client_kwargs["toolsets"] = toolsets
    no_toolsets = _split_toolsets(getattr(args, "no_toolsets", None))
    if no_toolsets is not None:
        client_kwargs["no_toolsets"] = no_toolsets
    timeout = getattr(args, "timeout", None)
    if timeout is not None:
        client_kwargs["timeout"] = timeout

    try:
        client = OpenAmerClient(**client_kwargs)
        result = client.run(task)
    except OpenAmerError as exc:
        if as_json:
            payload = {"ok": False}
            payload.update(exc.to_dict())
            click_print_json(payload)
        else:
            print(f"❌ openamer run failed ({exc.reason}): {exc}", file=sys.stderr)
            if exc.detail:
                print(f"   engine output tail:\n{exc.detail}", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001 - never traceback at the CLI edge
        if as_json:
            click_print_json(
                {
                    "ok": False,
                    "error": type(exc).__name__,
                    "reason": "engine",
                    "message": str(exc),
                }
            )
        else:
            print(f"❌ openamer run failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    if as_json:
        payload = {"ok": bool(result.completed)}
        payload.update(result.to_dict())
        click_print_json(payload)
    else:
        # The engine's own narration already contains the final response and its
        # summary; print it verbatim so `openamer run` looks like
        # `python run_agent.py` and then add the one-line machine facts.
        if result.stdout:
            print(result.stdout)
        if result.text and result.text not in result.stdout:
            print(result.text)
        print(
            f"\n[run] turns={result.turns} cost_usd={result.cost_usd:.6f} "
            f"session={result.session_id} completed={result.completed}"
        )
        if result.error:
            print(f"[run] engine error: {result.error}", file=sys.stderr)

    return 0 if result.completed else 1


def click_print_json(payload: dict) -> None:
    """Write one JSON object to stdout, and nothing else."""
    json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    sys.stdout.flush()


if __name__ == "__main__":  # pragma: no cover - manual smoke check
    _parser = argparse.ArgumentParser(prog="openamer run")
    _sub = _parser.add_subparsers(dest="command")
    build_run_parser(_sub)
    _args = _parser.parse_args()
    raise SystemExit(_args.func(_args))
