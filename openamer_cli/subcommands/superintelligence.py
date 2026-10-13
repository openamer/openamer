"""``openamer super`` subcommand parser.

Monitor the superintelligence platform health. Follows the same pattern as
``openamer_cli/subcommands/status.py``.

Provides:
  - ``openamer super status``   — show system health status (compact)
  - ``openamer super report``   — generate comprehensive report
  - ``openamer super milestones`` — show next planned milestones
"""

from __future__ import annotations

import sys


def build_super_parser(subparsers, *, cmd_super=None) -> None:
    """Attach the ``super`` subcommand (and sub-actions) to *subparsers*."""
    if cmd_super is None:
        from openamer_cli.subcommands.superintelligence import super_command
        cmd_super = super_command
    super_parser = subparsers.add_parser(
        "super",
        help="Superintelligence platform health dashboard",
        description=(
            "Monitor and report on the superintelligence platform: "
            "brain learning loop, A2A connectivity, skills, memory, "
            "computer-use readiness, and multi-agent orchestration."
        ),
    )
    super_subparsers = super_parser.add_subparsers(dest="super_command")

    # super status
    super_subparsers.add_parser(
        "status",
        help="Show superintelligence system health (compact)",
        description="Display a quick snapshot of every subsystem's health.",
    )

    # super report
    super_subparsers.add_parser(
        "report",
        help="Generate a comprehensive superintelligence report",
        description="Full system report with recommendations and milestones.",
    )

    # super milestones
    super_subparsers.add_parser(
        "milestones",
        help="Show next planned superintelligence milestones",
        description="List upcoming improvements for the platform.",
    )

    super_parser.set_defaults(func=cmd_super)


# ---------------------------------------------------------------------------
# Handler
# ---------------------------------------------------------------------------


def super_command(args) -> int:
    """Dispatch ``openamer super <subcommand>``."""
    sub = getattr(args, "super_command", None)

    if sub in (None, ""):
        print(
            "usage: openamer super <subcommand>\n"
            "\n"
            "subcommands:\n"
            "  status      Show system health (compact)\n"
            "  report      Generate comprehensive superintelligence report\n"
            "  milestones  Show next planned improvements\n"
            "\n"
            "Run `openamer super <subcommand> -h` for details.",
            file=sys.stderr,
        )
        return 1

    if sub == "status":
        return _cmd_status()
    elif sub == "report":
        return _cmd_report()
    elif sub == "milestones":
        return _cmd_milestones()

    print(f"Unknown super subcommand: {sub}", file=sys.stderr)
    return 1


# ---------------------------------------------------------------------------
# Sub-handlers
# ---------------------------------------------------------------------------


def _badge(s: str) -> str:
    badges = {
        "pass": "✅",
        "warn": "⚠️",
        "fail": "❌",
        "unknown": "❓",
    }
    return badges.get(s, "❓")


def _cmd_status() -> int:
    """Show compact superintelligence status."""
    from openamer_cli.superintelligence import check_all_systems

    data = check_all_systems()

    print("╔══════════════════════════════════════════════╗")
    print("║       SUPERINTELLIGENCE — SYSTEM STATUS      ║")
    print("╚══════════════════════════════════════════════╝")
    print()
    for key, label in [
        ("brain_learning_loop", "Brain Learning Loop"),
        ("a2a_swarm_connectivity", "A2A Swarm Connectivity"),
        ("skills_count", "Skills Count"),
        ("skills_improvement_rate", "Skills Improvement Rate"),
        ("memory_usage", "Memory Usage"),
        ("memory_growth", "Memory Growth"),
        ("computer_use_readiness", "Computer-Use Readiness"),
        ("multi_agent_orchestration", "Multi-Agent Orchestration"),
    ]:
        val = data.get(key, "unknown")
        print(f"  {_badge(val)}  {label:30s}  {val.upper()}")

    print()
    score = data.get("overall_score", 0)
    if score >= 80:
        rating = "🌟 Excellent"
    elif score >= 60:
        rating = "👍 Good"
    elif score >= 40:
        rating = "⚠️  Fair"
    else:
        rating = "🔴 Critical"
    print(f"  Overall Health Score:  {score}/100  ({rating})")
    print()
    print(f"  Timestamp: {data.get('timestamp', 'N/A')}")
    return 0


def _cmd_report() -> int:
    """Generate comprehensive superintelligence report."""
    from openamer_cli.superintelligence import generate_superintelligence_report

    report = generate_superintelligence_report()
    print(report)
    return 0


def _cmd_milestones() -> int:
    """Show next planned milestones."""
    from openamer_cli.superintelligence import get_next_milestones

    milestones = get_next_milestones()
    print("╔══════════════════════════════════════════════╗")
    print("║     SUPERINTELLIGENCE — NEXT  MILESTONES     ║")
    print("╚══════════════════════════════════════════════╝")
    print()
    for i, m in enumerate(milestones, start=1):
        priority = m.get("priority", "medium")
        icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(priority, "🟡")
        print(f"  {i:2d}. {icon}  {m['title']}")
        print(f"      Priority: {priority.upper()}")
        print(f"      {m['description']}")
        print()
    return 0