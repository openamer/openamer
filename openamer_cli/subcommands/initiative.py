"""``openamer initiative`` subcommand parser.

Autonomous Initiative System — proaktive System-Checks und Auto-Fixes.

Provides:
  - ``openamer initiative check``   — health check (Score >= 80?)
  - ``openamer initiative fix``     — auto-fix detected problems
  - ``openamer initiative suggest`` — proactive improvement suggestions
  - ``openamer initiative auto``    — full cycle (check → fix → suggest)
"""

from __future__ import annotations

import sys


def build_initiative_parser(subparsers, *, cmd_initiative=None) -> None:
    """Attach the ``initiative`` subcommand (and sub-actions) to *subparsers*."""
    if cmd_initiative is None:
        from openamer_cli.subcommands.initiative import initiative_command

        cmd_initiative = initiative_command

    initiative_parser = subparsers.add_parser(
        "initiative",
        help="Autonomous system health checks and auto-fixes",
        description=(
            "Proactive system health monitoring for OpenAmer. "
            "Check system health, auto-fix detected problems, "
            "get proactive suggestions for improvement. "
            "The ``auto`` command runs the full cycle (check → fix → suggest)."
        ),
    )
    initiative_subparsers = initiative_parser.add_subparsers(dest="initiative_command")

    # initiative check
    p_check = initiative_subparsers.add_parser(
        "check",
        help="Check system health (Score >= 80?)",
        description="Run all system health checks and report the overall score.",
    )
    p_check.add_argument(
        "--json",
        action="store_true",
        help="Output raw JSON instead of formatted report.",
    )

    # initiative fix
    p_fix = initiative_subparsers.add_parser(
        "fix",
        help="Auto-fix detected problems",
        description="Identify FAIL/WARN checks and fix them automatically.",
    )
    p_fix.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be fixed without making changes.",
    )

    # initiative suggest
    p_suggest = initiative_subparsers.add_parser(
        "suggest",
        help="Show proactive suggestions",
        description="Analyze patterns and suggest improvements.",
    )

    # initiative auto
    p_auto = initiative_subparsers.add_parser(
        "auto",
        help="Run full cycle (check → fix → suggest)",
        description="Execute the complete autonomous initiative cycle: "
        "health check, auto-fix problems, and proactive suggestions.",
    )
    p_auto.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be fixed without making changes.",
    )
    p_auto.add_argument(
        "--cron",
        action="store_true",
        help="Cron mode: write report to log file, minimal stdout.",
    )

    initiative_parser.set_defaults(func=cmd_initiative)


# ---------------------------------------------------------------------------
# Handler
# ---------------------------------------------------------------------------


def initiative_command(args) -> int:
    """Dispatch ``openamer initiative <subcommand>``."""
    sub = getattr(args, "initiative_command", None)

    if sub in (None, ""):
        print(
            "usage: openamer initiative <subcommand>\n"
            "\n"
            "subcommands:\n"
            "  check     Check system health (Score >= 80?)\n"
            "  fix       Auto-fix detected problems\n"
            "  suggest   Show proactive suggestions\n"
            "  auto      Run full cycle (check → fix → suggest)\n"
            "\n"
            "Run `openamer initiative <subcommand> -h` for details.",
            file=sys.stderr,
        )
        return 1

    if sub == "check":
        return _cmd_check(args)
    elif sub == "fix":
        return _cmd_fix(args)
    elif sub == "suggest":
        return _cmd_suggest()
    elif sub == "auto":
        return _cmd_auto(args)

    print(f"Unknown initiative subcommand: {sub}", file=sys.stderr)
    return 1


# ---------------------------------------------------------------------------
# Sub-handlers
# ---------------------------------------------------------------------------


def _cmd_check(args) -> int:
    """Run health check and display results."""
    from openamer_cli.autonomous_initiative import check_system_health

    health = check_system_health()

    if getattr(args, "json", False):
        import json
        print(json.dumps(health, indent=2, default=str))
        return 0

    score = health.get("overall_score", 0)
    if score >= 80:
        rating = "🌟 PASS"
    else:
        rating = "⚠️  DEGRADED"

    print("╔══════════════════════════════════════════════╗")
    print("║     AUTONOMOUS INITIATIVE — HEALTH CHECK     ║")
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
        val = health.get(key, "unknown")
        badge = {"pass": "✅", "warn": "⚠️", "fail": "❌", "unknown": "❓"}.get(val, "❓")
        print(f"  {badge}  {label:30s}  {val.upper()}")

    print()
    print(f"  Overall Score:  {score}/100  ({rating})")
    print(f"  Timestamp: {health.get('timestamp', 'N/A')}")
    print()
    print(f"  Required: Score >= 80  →  {'✅ PASS' if score >= 80 else '❌ FAIL'}")
    return 0 if score >= 80 else 1


def _cmd_fix(args) -> int:
    """Auto-fix detected problems."""
    from openamer_cli.autonomous_initiative import auto_fix_issues

    dry_run = getattr(args, "dry_run", False)

    print("╔══════════════════════════════════════════════╗")
    print("║      AUTONOMOUS INITIATIVE — AUTO-FIX        ║")
    print("╚══════════════════════════════════════════════╝")
    print()
    if dry_run:
        print("  🔸 DRY RUN — no changes will be made")
        print()

    fixes = auto_fix_issues(dry_run=dry_run)

    applied = 0
    for f in fixes:
        status = f.get("status", "")
        status_icon = {
            "pass": "✅",
            "fixed": "✅",
            "info": "ℹ️ ",
            "would_fix": "🔸",
            "none_needed": "✅",
        }.get(status, "❓")
        check_name = f.get("check", "unknown")
        result = f.get("result", "")
        print(f"  {status_icon}  {check_name:30s}  {result}")
        if status == "fixed":
            applied += 1

    print()
    print(f"  📊 Actions: {applied} fix(es) applied, "
          f"{len(fixes) - applied} check(s) already healthy")
    return 0


def _cmd_suggest() -> int:
    """Generate and display proactive suggestions."""
    from openamer_cli.autonomous_initiative import proactive_suggestions

    suggestions = proactive_suggestions()

    print("╔══════════════════════════════════════════════╗")
    print("║   AUTONOMOUS INITIATIVE — PROACTIVE IDEAS    ║")
    print("╚══════════════════════════════════════════════╝")
    print()

    for i, s in enumerate(suggestions, start=1):
        priority = s.get("priority", "low")
        icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(priority, "🟡")
        category = s.get("category", "general")
        title = s.get("title", "Untitled")
        desc = s.get("description", "")
        print(f"  {i:2d}. {icon}  [{category.upper()}] {title}")
        print(f"      Priority: {priority.upper()}")
        print(f"      {desc}")
        print()

    print(f"  💡 {len(suggestions)} suggestion(s) generated")
    return 0


def _cmd_auto(args) -> int:
    """Run full initiative cycle."""
    from openamer_cli.autonomous_initiative import run_initiative_cycle, run_cron_entry

    cron_mode = getattr(args, "cron", False)
    dry_run = getattr(args, "dry_run", False)

    if cron_mode:
        return run_cron_entry()

    result = run_initiative_cycle(dry_run=dry_run, verbose=True)
    return 0 if result["summary"]["score"] >= 80 else 1