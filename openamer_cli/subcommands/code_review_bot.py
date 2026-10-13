"""``openamer review-pr`` subcommand — review GitHub PRs programmatically.

Extracted pattern: ``openamer_cli/subcommands/<group>.py`` with
``build_review_pr_parser(subparsers, ...)``.
"""

from __future__ import annotations

from typing import Callable


def build_review_pr_parser(subparsers, *, cmd_review_pr: Callable) -> None:
    """Attach the ``review-pr`` subcommand to ``subparsers``."""
    parser = subparsers.add_parser(
        "review-pr",
        help="Review a GitHub Pull Request",
        description="Fetch a PR diff from GitHub, run pattern-based checks, "
        "and produce a structured code review with inline comments.",
    )
    parser.add_argument(
        "pr_number",
        type=int,
        help="Pull request number to review (e.g. 42)",
    )
    parser.add_argument(
        "--repo",
        required=True,
        help="Repository in owner/name format (e.g. openamer/openamer)",
    )
    parser.add_argument(
        "--token",
        default=None,
        help="GitHub API token (default: GITHUB_TOKEN env var)",
    )
    parser.add_argument(
        "--post",
        action="store_true",
        help="Post review comments to GitHub (requires --token or GITHUB_TOKEN)",
    )
    parser.set_defaults(func=cmd_review_pr)