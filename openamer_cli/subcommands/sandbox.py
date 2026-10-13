"""
``openamer sandbox`` subcommand parser.

Sandbox Execution Engine — run untrusted code in an isolated
temporary environment with strict timeouts and automatic cleanup.

Usage
-----
    openamer sandbox run <file>
    openamer sandbox python <code>
    openamer sandbox config
"""

from __future__ import annotations

from typing import Callable


def build_sandbox_parser(subparsers, *, cmd_sandbox: Callable) -> None:
    """Attach the ``sandbox`` subcommand to ``subparsers``."""
    sandbox_parser = subparsers.add_parser(
        "sandbox",
        help="Run code in an isolated sandbox environment",
        description=(
            "Execute Python code or shell commands inside a temporary,\n"
            "isolated directory.  The sandbox directory is created for a\n"
            "single execution and removed immediately afterwards.\n\n"
            "Subcommands:\n"
            "  run <file>       Execute a Python file in the sandbox\n"
            "  python <code>    Execute an inline Python snippet\n"
            "  config           Show the current sandbox configuration\n"
        ),
    )
    sandbox_sub = sandbox_parser.add_subparsers(dest="sandbox_action")

    # ── openamer sandbox run <file> ────────────────────────────────────────
    run_parser = sandbox_sub.add_parser(
        "run",
        help="Execute a Python file in the sandbox",
        description=(
            "Run the given Python file inside a temporary, isolated\n"
            "directory.  The file is copied into the sandbox before\n"
            "execution; the original is never modified.\n\n"
            "Output is capped at 100 KB.  Timeout defaults to 30s.\n"
            "Use --timeout to override."
        ),
    )
    run_parser.add_argument(
        "file",
        help="Path to the Python file to execute",
    )
    run_parser.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="Timeout in seconds (max 60, default 30)",
    )
    run_parser.set_defaults(func=cmd_sandbox)

    # ── openamer sandbox python <code> ─────────────────────────────────────
    python_parser = sandbox_sub.add_parser(
        "python",
        aliases=["py"],
        help="Execute an inline Python snippet",
        description=(
            "Run the provided Python code snippet inside a temporary,\n"
            "isolated directory.  Wrap the code in quotes.\n\n"
            "Output is capped at 100 KB.  Timeout defaults to 30s.\n"
            "Use --timeout to override."
        ),
    )
    python_parser.add_argument(
        "code",
        nargs="+",
        help="Python code snippet(s) to execute (concatenated with spaces)",
    )
    python_parser.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="Timeout in seconds (max 60, default 30)",
    )
    python_parser.set_defaults(func=cmd_sandbox)

    # ── openamer sandbox config ────────────────────────────────────────────
    config_parser = sandbox_sub.add_parser(
        "config",
        help="Show the current sandbox configuration",
        description="Print the active SandboxPolicy settings.",
    )
    config_parser.set_defaults(func=cmd_sandbox)