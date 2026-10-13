"""``openamer tree`` subcommand — inspect execution trees.

Usage:

    openamer tree show <id>          — print the execution tree as ASCII
    openamer tree export <id>        — export the tree as JSON
    openamer tree stats <id>         — show timing/performance stats
"""

from __future__ import annotations

import json
import sys

from openamer_cli.execution_tree import ExecutionTree


def _cmd_show(args) -> int:
    """Print an execution tree as ASCII."""
    tree = _load_tree()
    output = tree.print_tree(tree_id=args.id)
    print(output)
    return 0


def _cmd_export(args) -> int:
    """Export an execution tree as JSON."""
    tree = _load_tree()
    exported = tree.export_json(tree_id=args.id)
    json.dump(exported, sys.stdout, indent=2, default=str)
    print()
    return 0


def _cmd_stats(args) -> int:
    """Show timing and performance stats for a tree."""
    tree = _load_tree()
    stats = tree.get_stats(tree_id=args.id)
    if stats["total_nodes"] == 0:
        print("No nodes found in the specified tree.")
        return 0

    print(f"{'Stat':<25} {'Value':>12}")
    print("-" * 40)
    print(f"{'Total nodes':<25} {stats['total_nodes']:>12}")
    print(f"{'Completed':<25} {stats['completed']:>12}")
    print(f"{'Failed':<25} {stats['failed']:>12}")
    print(f"{'Pending':<25} {stats['pending']:>12}")
    print(f"{'Total duration (ms)':<25} {stats['total_duration_ms']:>12.2f}")
    print(f"{'Avg duration (ms)':<25} {stats['avg_duration_ms']:>12.2f}")

    if stats["by_type"]:
        print()
        print("By type:")
        for t, data in stats["by_type"].items():
            print(f"  {t:<20} count={data['count']} total_ms={data['total_duration_ms']:.2f}")

    if stats["longest_node"]:
        ln = stats["longest_node"]
        print()
        print(f"Longest node: {ln['id']} ({ln['type']}) — {ln['duration_ms']:.0f}ms")

    return 0


def _load_tree() -> ExecutionTree:
    """Create a demo execution tree for CLI testing."""
    # In production this would load from a persisted session store;
    # for now we return empty so the user can build one programmatically.
    return ExecutionTree()


def build_tree_parser(subparsers) -> None:
    """Attach the ``tree`` subcommand tree to ``subparsers``."""
    p = subparsers.add_parser(
        "tree",
        help="Inspect execution trees with timing and stats",
        description=(
            "Display and analyze execution trees.  Execution trees record "
            "the hierarchy of LLM calls, tool calls, results, conditions, "
            "and branches during a run, with timing information."
        ),
    )
    sub = p.add_subparsers(dest="tree_command")

    # tree show <id>
    show_p = sub.add_parser(
        "show",
        help="Print an execution tree as ASCII",
        description="Render an execution tree with timing and status symbols.",
    )
    show_p.add_argument("id", help="Tree root node ID")
    show_p.set_defaults(func=_cmd_show)

    # tree export <id>
    export_p = sub.add_parser(
        "export",
        help="Export an execution tree as JSON",
        description="Export the tree structure as JSON for web UI consumption.",
    )
    export_p.add_argument("id", help="Tree root node ID")
    export_p.set_defaults(func=_cmd_export)

    # tree stats <id>
    stats_p = sub.add_parser(
        "stats",
        help="Show timing and performance stats",
        description="Display execution statistics including durations and counts by type.",
    )
    stats_p.add_argument("id", help="Tree root node ID")
    stats_p.set_defaults(func=_cmd_stats)