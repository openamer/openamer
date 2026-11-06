"""``openamer repomap`` subcommand — build, inspect, and query codebase maps.

Usage:

    openamer repomap build [PATH]     — build and print the repo map
    openamer repomap context [PATH]   — print a human-readable context summary
    openamer repomap rank [PATH]      — rank files by relevance to a query

PATH defaults to ``.`` (current directory).
"""

from __future__ import annotations

import argparse
import json
import sys


def _cmd_build(args) -> int:
    """Build repo map for *args.path* and print as JSON."""
    from openamer_cli.repomap import build_repo_map

    try:
        result = build_repo_map(args.path)
        json.dump(result, sys.stdout, indent=2, default=str)
        print()
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def _cmd_context(args) -> int:
    """Print a human-readable repo context summary."""
    from openamer_cli.repomap import RepoMap, estimate_tokens, get_repo_context

    try:
        if args.query:
            context = RepoMap(args.path).render_context(args.query, args.budget)
            print(
                f"# Repo context for '{args.query}' "
                f"({estimate_tokens(context)}/{args.budget} tokens)",
                file=sys.stdout,
            )
            print(context)
        else:
            context = get_repo_context(args.path, args.file)
            print(context)
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def _cmd_rank(args) -> int:
    """Rank files by relevance to a query."""
    from openamer_cli.repomap import build_repo_map, rank_files_by_relevance

    try:
        rm = build_repo_map(args.path)
        if args.strategy == "graph":
            from openamer_cli.repomap import RepoMap

            ranked = RepoMap(args.path).rank_files_graph(args.query, rm)
        else:
            ranked = rank_files_by_relevance(args.query, rm)
        if ranked:
            print(f"Top files for '{args.query}' ({args.strategy}):")
            for f, score in ranked[:20]:
                print(f"  {score:6.2f}  {f}")
        else:
            print("No matches found.")
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def build_repomap_parser(subparsers) -> None:
    """Attach the ``repomap`` subcommand tree to ``subparsers``."""
    p = subparsers.add_parser(
        "repomap",
        help="Build and query codebase repo maps",
        description=(
            "Scan a git repository and build a structured map of the codebase, "
            "including files, languages, classes, functions, and dependencies. "
            "Uses git ls-files and stdlib-only parsing; `rank --strategy graph` "
            "and `context --query` use syntax-aware symbol/reference ranking."
        ),
    )
    sub = p.add_subparsers(dest="repomap_command")

    # repomap build [PATH]
    build_p = sub.add_parser(
        "build",
        help="Build repo map and print as JSON",
        description="Scan a git repo and output a complete JSON repo map.",
    )
    build_p.add_argument(
        "path", nargs="?", default=".",
        help="Path to git repo root (default: current directory)",
    )
    build_p.set_defaults(func=_cmd_build)

    # repomap context [PATH] [--file FILE]
    ctx_p = sub.add_parser(
        "context",
        help="Print a human-readable repo context summary",
        description=(
            "Produce a text summary of the repo structure. "
            "Use --file to focus on a specific file's neighbourhood."
        ),
    )
    ctx_p.add_argument(
        "path", nargs="?", default=".",
        help="Path to git repo root (default: current directory)",
    )
    ctx_p.add_argument(
        "--file", "-f", default="",
        help="Focus summary on a specific file (relative path)",
    )
    ctx_p.add_argument(
        "--query", "-q", default="",
        help="Render the highest-ranked definitions for a keyword query",
    )
    ctx_p.add_argument(
        "--budget", type=int, default=120,
        help="Token budget for --query rendering (default: 120)",
    )
    ctx_p.set_defaults(func=_cmd_context)

    # repomap rank [PATH] <query>
    rank_p = sub.add_parser(
        "rank",
        help="Rank files by relevance to a query",
        description=(
            "Rank all files in the repo by relevance to a keyword query "
            "using simple keyword and identifier matching."
        ),
    )
    rank_p.add_argument(
        "path", nargs="?", default=".",
        help="Path to git repo root (default: current directory)",
    )
    rank_p.add_argument("query", help="Keyword query string")
    rank_p.add_argument(
        "--strategy", choices=("keyword", "graph"), default="keyword",
        help=(
            "keyword: path/identifier substring scoring (default). "
            "graph: syntax-aware symbol and reference ranking."
        ),
    )
    rank_p.set_defaults(func=_cmd_rank)