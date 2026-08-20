"""``openamer hermes`` subcommand parser."""

from __future__ import annotations

from typing import Callable


def build_hermes_parser(subparsers, *, cmd_hermes: Callable) -> None:
    """Attach the ``hermes`` subcommand to ``subparsers``."""
    hermes_parser = subparsers.add_parser(
        "hermes",
        help="Migrate from Hermes Agent to OpenAmer",
        description=(
            "Check if Hermes Agent is installed and migrate skills, memories, "
            "and config to OpenAmer. Same DNA. More Features. 100/100 Score."
        ),
    )
    hermes_sub = hermes_parser.add_subparsers(dest="hermes_command")

    hermes_sub.add_parser(
        "check",
        help="Check if Hermes Agent is installed",
    )

    migrate_parser = hermes_sub.add_parser(
        "migrate",
        help="Run full migration from Hermes to OpenAmer",
    )
    migrate_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview what would be migrated without making changes",
    )

    hermes_parser.set_defaults(func=cmd_hermes)