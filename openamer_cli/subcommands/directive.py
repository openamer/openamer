"""``openamer directive`` subcommand.

The Genesis Directives (DIR-01 .. DIR-24) are the constitution every
OpenAmer instance carries; ``agent/directive_engine.py`` knows what code
backs each one and how far that code goes. Until now that audit was only
reachable by running the module by hand (``python -m
agent.directive_engine``), which meant the constitution had a status page
nobody could open. This wires it into the CLI.

Exit code is 1 when the audit finds a violation (a claim whose evidence
path no longer resolves, or a check that fails), so it can gate CI.
"""

from __future__ import annotations

import sys


def build_directive_parser(subparsers, *, cmd_directive=None) -> None:
    """Attach the ``directive`` subcommand to *subparsers*."""
    if cmd_directive is None:
        from openamer_cli.subcommands.directive import directive_command

        cmd_directive = directive_command

    parser = subparsers.add_parser(
        "directive",
        help="Audit the Genesis Directives (DIR-01..DIR-24) against the code",
        description=(
            "Show, per Genesis Directive, which modules implement it and how "
            "far that implementation goes (ENFORCED / PARTIAL / GATED / "
            "RESEARCH / NOT_IMPLEMENTED). A violation is a claim whose "
            "evidence path no longer resolves or whose measurable check "
            "fails; the command exits 1 when there is one."
        ),
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output the raw audit as JSON.",
    )
    parser.add_argument(
        "--gaps",
        action="store_true",
        help="Only list directives with no implementation at all.",
    )
    parser.set_defaults(func=cmd_directive)


def directive_command(args) -> int:
    """Run the constitution audit and print it."""
    from agent.directive_engine import audit, _print_table

    result = audit()
    if getattr(args, "json", False):
        import json

        print(json.dumps(result, indent=2))
    else:
        _print_table(result, gaps_only=getattr(args, "gaps", False))
        if not result["violations"]:
            print("\nNo violations: every claim's evidence resolves and every check passes.")
    return 1 if result["violations"] else 0


if __name__ == "__main__":  # pragma: no cover - manual runs
    raise SystemExit(directive_command(type("A", (), {"json": "--json" in sys.argv, "gaps": False})()))
