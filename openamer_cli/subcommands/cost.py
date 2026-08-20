"""
``openamer cost`` CLI subcommand — cost dashboard.

Provides ``openamer cost report`` and ``openamer cost stats`` subcommands
for tracking and reporting LLM inference costs.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Callable


def _cmd_cost_report(args: argparse.Namespace) -> None:
    """Handle ``openamer cost report [--days N]``."""
    from openamer_cli.cost_dashboard import print_cost_report

    print_cost_report(days=args.days)


def _cmd_cost_stats(args: argparse.Namespace) -> None:
    """Handle ``openamer cost stats [--days N] [--pretty]``."""
    from openamer_cli.cost_dashboard import get_cost_stats

    stats = get_cost_stats(days=args.days)
    indent = 2 if getattr(args, "pretty", False) else None
    print(json.dumps(stats, indent=indent))


def _cmd_cost_budget(args: argparse.Namespace) -> None:
    """Handle ``openamer cost budget``."""
    from openamer_cli.cost_dashboard import get_budget_status

    budget = get_budget_status()
    print(json.dumps(budget, indent=2))


def build_cost_parser(subparsers) -> None:
    """Attach the ``cost`` subcommand and its sub-subcommands.

    Called from ``openamer_cli/main.py`` where it owns the top-level
    ``cost`` subparser.
    """
    cost_parser = subparsers.add_parser(
        "cost",
        help="Track, report, and budget LLM inference costs",
        description=(
            "Query and display LLM cost data accumulated by the CostTracker. "
            "Supports per-model, per-provider, and per-session breakdowns, "
            "budget vs. spent status, and a pretty-printed terminal report."
        ),
    )
    cost_parser.set_defaults(func=cost_command)
    cost_sub = cost_parser.add_subparsers(dest="cost_action")

    # --- report ---
    report_parser = cost_sub.add_parser(
        "report",
        help="Print a cost report to the terminal",
        description="Pretty-print LLM cost data for the last N days.",
    )
    report_parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="Number of days to include (default: 30)",
    )
    report_parser.set_defaults(_cost_handler=_cmd_cost_report)

    # --- stats ---
    stats_parser = cost_sub.add_parser(
        "stats",
        help="Show cost statistics as JSON",
        description="Output cost breakdowns (by model, provider, session) as JSON.",
    )
    stats_parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="Number of days to include (default: 30)",
    )
    stats_parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print the JSON output",
    )
    stats_parser.set_defaults(_cost_handler=_cmd_cost_stats)

    # --- budget ---
    budget_parser = cost_sub.add_parser(
        "budget",
        help="Show budget vs. spent status",
        description="Display monthly budget, spend, and remaining as JSON.",
    )
    budget_parser.set_defaults(_cost_handler=_cmd_cost_budget)

    # Default: show help when no subcommand given
    cost_parser.set_defaults(_cost_handler=lambda a: cost_parser.print_help())


def cost_command(args: argparse.Namespace) -> None:
    """Dispatch ``openamer cost <subcommand>``.

    Called from ``main.py`` with the parsed namespace. Routes to the
    handler that ``build_cost_parser`` registered via ``set_defaults``.
    """
    handler = getattr(args, "_cost_handler", None)
    if handler is None:
        from openamer_cli.cost_dashboard import print_cost_report

        print_cost_report()
        return
    handler(args)