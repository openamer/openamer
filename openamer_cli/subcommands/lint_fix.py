"""``openamer lint-fix`` subcommand — run lint-fix cycles on source files.

Extracted pattern: ``openamer_cli/subcommands/<group>.py`` with
``build_lint_fix_parser(subparsers, ...)``.
"""

from __future__ import annotations

from typing import Callable


def build_lint_fix_parser(subparsers, *, cmd_lint_fix: Callable, cmd_lint_fix_watch: Callable) -> None:
    """Attach the ``lint-fix`` subcommand to ``subparsers``."""
    parser = subparsers.add_parser(
        "lint-fix",
        help="Run lint-and-fix cycle on source files",
        description="Run linter (ruff for Python, eslint for JS/TS), "
        "categorize issues, attempt auto-fix, repeat up to N times.",
    )
    parser.add_argument(
        "file",
        help="Path to the source file to lint and fix",
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=3,
        help="Maximum lint-fix iterations (default: 3)",
    )
    parser.add_argument(
        "--watch",
        action="store_true",
        help="Watch directory for file changes and auto-fix",
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=2.0,
        help="Poll interval in seconds for watch mode (default: 2.0)",
    )
    parser.set_defaults(func=cmd_lint_fix)