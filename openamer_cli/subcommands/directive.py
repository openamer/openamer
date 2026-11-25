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
    parser.add_argument(
        "--history",
        action="store_true",
        help="Print the version chain of the constitution (DIR-16) and verify its hashes.",
    )
    parser.add_argument(
        "--cycle",
        action="store_true",
        help="Run one DIR-16 evaluation cycle now (propose, gate, apply, verify).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="With --cycle: propose but write nothing.",
    )
    parser.set_defaults(func=cmd_directive)


def _print_history() -> int:
    from agent import directive_constitution as const

    const.ensure_genesis()
    records = const.history()
    if not records:
        print("No constitution versions yet.")
        return 0
    for row in records:
        tail = f"  <- {row['proposal_id']}" if row.get("proposal_id") else ""
        print(
            f"v{row['version']:04d}  {row['action']:<8} {row['hash']}  "
            f"parent={row['parent_hash']:<12} {row['created_at']}{tail}"
        )
        print(f"        {row['reason']}")
    problems = const.verify_chain()
    if problems:
        print("\nCHAIN BROKEN:")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print(f"\nChain intact: {len(records)} version(s), every hash and parent link verified.")
    return 0


def _run_cycle(dry_run: bool) -> int:
    from agent.directive_legislation import run_cycle

    report = run_cycle(auto_apply=not dry_run)
    print(
        f"DIR-16 cycle: {len(report.issues)} issue(s), {len(report.proposals)} proposal(s), "
        f"{len(report.applied)} applied, {len(report.rejected)} rejected, "
        f"v{report.version_before:04d} -> v{report.version_after:04d}"
    )
    for issue in report.issues:
        print(f"  [{issue.kind}] {issue.directive_id}: {issue.detail}")
    for item in report.applied:
        print(f"  applied {item['proposal_id']} -> v{item['version']:04d} ({item['hash']})")
    for item in report.rejected:
        print(f"  rejected {item['proposal_id']}: {'; '.join(item['problems'])}")
    if report.chain_problems:
        print("  CHAIN PROBLEMS:")
        for problem in report.chain_problems:
            print(f"    - {problem}")
        return 1
    return 0


def directive_command(args) -> int:
    """Run the constitution audit and print it."""
    if getattr(args, "history", False):
        return _print_history()
    if getattr(args, "cycle", False):
        return _run_cycle(getattr(args, "dry_run", False))

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
