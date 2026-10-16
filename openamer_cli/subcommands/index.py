"""``openamer index`` — build, query, and inspect a persistent codebase index.

Usage::

    openamer index build [--repo PATH] [--json] [--full]
    openamer index query "<terms>" [--repo PATH] [--json] [--limit N]
    openamer index stats [--repo PATH] [--json]

``--repo`` defaults to the current directory. The index is written to
``<repo>/.openamer/index/code-index.json`` — it belongs to the repository, not
to ``OPENAMER_HOME``.

This deliberately does NOT register a model tool: a persistent index is a
capability at the edge (CLI + skill), not core surface that would be paid for
on every API call.
"""

from __future__ import annotations

import argparse
import json
import sys


def _emit(payload: dict) -> None:
    """Print *payload* as indented JSON on stdout."""
    json.dump(payload, sys.stdout, indent=2, default=str)
    print()


def _cmd_build(args) -> int:
    """Build or incrementally refresh the index for ``--repo``."""
    from openamer_cli.code_index import build_index, confidence_notes, index_stats

    try:
        result = build_index(args.repo, incremental=not args.full)
    except Exception as e:  # noqa: BLE001 - CLI boundary, report and exit 1
        print(f"Error: {e}", file=sys.stderr)
        return 1

    if args.json:
        payload = dict(result)
        try:
            payload["confidence"] = confidence_notes(index_stats(args.repo))
        except Exception:  # noqa: BLE001 - stats are advisory only
            payload["confidence"] = []
        _emit(payload)
        return 0

    mode = "full rebuild" if args.full else "incremental"
    print(f"Indexed {result['files_indexed']} file(s) ({mode}) in {result['duration_ms']} ms")
    print(f"  symbols:        {result['symbols']}")
    print(f"  files parsed:   {result['files_parsed']}")
    print(f"  files reused:   {result['files_reused']}")
    if result["skipped_binary"]:
        print(f"  skipped binary: {result['skipped_binary']}")
    if result["skipped_large"]:
        print(f"  skipped large:  {result['skipped_large']}")
    if result["truncated"]:
        print("  WARNING: file cap reached — the index is partial")
    print(f"  index size:     {result['index_bytes']} bytes")
    print(f"  index path:     {result['index_path']}")
    try:
        for note in confidence_notes(index_stats(args.repo)):
            print(f"  note:           {note}")
    except Exception:  # noqa: BLE001 - notes are advisory only
        pass
    return 0


def _cmd_query(args) -> int:
    """Rank indexed files/symbols against the query terms."""
    from openamer_cli.code_index import index_path, query_index

    try:
        if not index_path(args.repo).exists():
            msg = (
                f"No index at {index_path(args.repo)} — "
                f"run `openamer index build --repo {args.repo}` first."
            )
            if args.json:
                _emit({"ok": False, "error": "no_index", "message": msg})
            else:
                print(msg, file=sys.stderr)
            return 1

        result = query_index(args.repo, args.query, limit=args.limit)
    except Exception as e:  # noqa: BLE001 - CLI boundary, report and exit 1
        print(f"Error: {e}", file=sys.stderr)
        return 1

    if args.json:
        _emit(result)
        return 0

    if not result["results"]:
        print(f"No matches for '{args.query}'.")
        return 0

    print(f"Top matches for '{args.query}' ({result['total_matches']} file(s)):")
    for hit in result["results"]:
        print(f"  {hit['score']:7.2f}  {hit['path']}  [{hit['lang']}/{hit['source']}]")
        for sym in hit["matched_symbols"][:3]:
            print(f"            → {sym['kind']} {sym['name']} (line {sym['line']})")
    return 0


def _cmd_stats(args) -> int:
    """Print index statistics for ``--repo``."""
    from openamer_cli.code_index import confidence_notes, index_stats

    try:
        stats = index_stats(args.repo)
    except Exception as e:  # noqa: BLE001 - CLI boundary, report and exit 1
        print(f"Error: {e}", file=sys.stderr)
        return 1

    if args.json:
        payload = dict(stats)
        payload["confidence"] = confidence_notes(stats)
        _emit(payload)
        return 0

    if not stats["exists"]:
        print(f"No index at {stats['index_path']} — run `openamer index build` first.")
        return 1

    print(f"Index: {stats['index_path']}")
    print(f"  version:     {stats.get('version')}")
    print(f"  created:     {stats.get('created')}")
    print(f"  updated:     {stats.get('updated')}")
    print(f"  files:       {stats['files_indexed']}")
    print(f"  symbols:     {stats['symbols']}")
    print(f"  index size:  {stats['index_bytes']} bytes")
    if stats.get("by_language"):
        langs = ", ".join(f"{k}={v}" for k, v in list(stats["by_language"].items())[:10])
        print(f"  languages:   {langs}")
    if stats.get("by_kind"):
        kinds = ", ".join(f"{k}={v}" for k, v in list(stats["by_kind"].items())[:10])
        print(f"  symbol kinds:{kinds}")
    if stats.get("by_source"):
        srcs = ", ".join(f"{k}={v}" for k, v in stats["by_source"].items())
        print(f"  symbol source:{srcs}")
    for note in confidence_notes(stats):
        print(f"  note:        {note}")
    return 0


def build_index_parser(subparsers) -> None:
    """Attach the ``index`` subcommand tree to ``subparsers``."""
    p = subparsers.add_parser(
        "index",
        help="Build, query, and inspect a persistent codebase index",
        description=(
            "Maintain a persistent, symbol-level index of a repository and use "
            "it to find the files and symbols relevant to a question. Python "
            "files are parsed with ast (exact symbols); other languages are "
            "scanned with a regex heuristic (approximate — not a parser). The "
            "index is stored in <repo>/.openamer/index/ and updated "
            "incrementally by mtime+size."
        ),
    )
    sub = p.add_subparsers(dest="index_command")

    # index build
    build_p = sub.add_parser(
        "build",
        help="Build or refresh the index for a repository",
        description=(
            "Scan --repo, extract symbols, and write "
            "<repo>/.openamer/index/code-index.json. Unchanged files are reused "
            "from the previous index and never re-parsed."
        ),
    )
    build_p.add_argument(
        "--repo", default=".",
        help="Repository root (default: current directory)",
    )
    build_p.add_argument(
        "--json", action="store_true",
        help="Emit machine-readable JSON",
    )
    build_p.add_argument(
        "--full", action="store_true",
        help="Ignore the previous index and re-parse every file",
    )
    build_p.set_defaults(func=_cmd_build)

    # index query
    query_p = sub.add_parser(
        "query",
        help="Rank indexed files/symbols against a query",
        description=(
            "Score indexed files and symbols against the query tokens. A file "
            "that DEFINES a matching symbol outranks one merely named after it. "
            "Requires an index — run `openamer index build` first."
        ),
    )
    query_p.add_argument("query", help="Search terms (symbol or path keywords)")
    query_p.add_argument(
        "--repo", default=".",
        help="Repository root (default: current directory)",
    )
    query_p.add_argument(
        "--limit", type=int, default=20,
        help="Maximum number of files to return (default: 20)",
    )
    query_p.add_argument(
        "--json", action="store_true",
        help="Emit machine-readable JSON",
    )
    query_p.set_defaults(func=_cmd_query)

    # index stats
    stats_p = sub.add_parser(
        "stats",
        help="Show statistics for an existing index",
        description="Report file/symbol counts, language mix, and precision notes.",
    )
    stats_p.add_argument(
        "--repo", default=".",
        help="Repository root (default: current directory)",
    )
    stats_p.add_argument(
        "--json", action="store_true",
        help="Emit machine-readable JSON",
    )
    stats_p.set_defaults(func=_cmd_stats)
