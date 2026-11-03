"""``openamer eval`` subcommand parser.

Provides benchmark evaluation subcommands.
"""

from __future__ import annotations

from typing import Callable


def build_eval_parser(subparsers, *, cmd_eval: Callable) -> None:
    """Attach the ``eval`` subcommand to ``subparsers``."""
    eval_parser = subparsers.add_parser(
        "eval",
        help="Run benchmarks, compare runs, and view leaderboard",
        description="Evaluation benchmark framework — run suites, compare results, and browse the leaderboard.",
    )
    eval_sub = eval_parser.add_subparsers(dest="eval_action")

    # eval run
    run_parser = eval_sub.add_parser(
        "run",
        help="Run a benchmark suite",
    )
    run_parser.add_argument(
        "suite",
        help="Benchmark suite name or JSON/YAML file path",
    )
    run_parser.add_argument(
        "--model",
        "-m",
        default="",
        help="Model identifier to record in the run (and to request from the provider)",
    )
    run_parser.add_argument(
        "--baseline",
        choices=("agent", "gold"),
        default="agent",
        help=(
            "Run provenance. 'agent' (default) measures a real model/agent "
            "through the configured provider. 'gold' replays each case's "
            "gold_output/expected through the evaluators as an offline harness "
            "check — never a model score, never ranked on the leaderboard."
        ),
    )
    run_parser.add_argument(
        "--max-tokens",
        type=int,
        default=1024,
        help="Max output tokens per model call (default: 1024)",
    )

    # eval compare
    compare_parser = eval_sub.add_parser(
        "compare",
        help="Compare two benchmark runs",
    )
    compare_parser.add_argument(
        "run1",
        help="Path to first benchmark run JSON file",
    )
    compare_parser.add_argument(
        "run2",
        help="Path to second benchmark run JSON file",
    )

    # eval leaderboard
    leaderboard_parser = eval_sub.add_parser(
        "leaderboard",
        help="Show the benchmark leaderboard",
    )

    eval_parser.set_defaults(func=cmd_eval)