"""CLI integration for the Self-Improving Skills System.

Provides handler functions for `openamer skills stats`, `openamer skills improve`,
and user profile commands.  These are wired into the existing argparse parsers.
"""
from __future__ import annotations

import argparse
import json
from typing import Any, Dict, List, Optional

from openamer_cli.skills_improver import SkillImprover, SkillImproverError
from openamer_cli.profile_system import (
    ProfileStore,
    ProfileInsights,
    UserProfile,
    SessionLearner,
    learn_from_session,
    get_profile_insights as ps_get_profile_insights,
)


# ---------------------------------------------------------------------------
# Skills stats / improve handlers
# ---------------------------------------------------------------------------

def handle_skills_stats(args: argparse.Namespace) -> None:
    """Handler for `openamer skills stats [name]`."""
    improver = SkillImprover()
    name = getattr(args, "name", None)

    if name:
        stats = improver.get_skill_stats(name)
        _print_skill_stats(stats)
    else:
        all_stats = improver.list_all_stats()
        if not all_stats:
            print("No skill usage data recorded yet.")
            return
        print(f"\n{'Skill':<30} {'Uses':<8} {'Success':<10} {'Avg (s)':<10} {'Rating':<8}")
        print(f"{'─' * 66}")
        for s in sorted(all_stats, key=lambda x: -x["times_used"]):
            rate = s.get("user_rating", 0) or 0
            print(
                f"{s['skill_name']:<30} {s['times_used']:<8} "
                f"{s['success_rate']:.0%}        {s['avg_duration']:<10.1f} "
                f"{rate:<8.1f}"
            )
        print()


def handle_skills_improve(args: argparse.Namespace) -> None:
    """Handler for `openamer skills improve [name]`."""
    improver = SkillImprover()
    name = getattr(args, "name", None)

    if name:
        suggestions = improver.suggest_improvements(name)
        print(f"\n📈  Improvement suggestions for [bold]{name}[/]:")
        for s in suggestions:
            print(f"  {s}")
        print()
    else:
        results = improver.auto_improve_skills()
        if not results:
            print("No skills with enough usage data to analyze.")
            return
        for r in results:
            sn = r["skill_name"]
            patterns = r["patterns_found"]
            suggs = r["suggestions"]
            print(f"\n📈  {sn}")
            if patterns:
                print(f"  Patterns: {', '.join(patterns)}")
            if suggs:
                for s in suggs:
                    print(f"  {s}")
            else:
                print("  ✓ No issues found.")
            applied = r["auto_applied"]
            if applied:
                for a in applied:
                    print(f"  ✅ {a}")
        print()


# ---------------------------------------------------------------------------
# Profile show / insights handlers
# ---------------------------------------------------------------------------

def handle_profile_user_show(args: argparse.Namespace) -> None:
    """Handler for `openamer profile user show [name]`."""
    store = ProfileStore()
    name = getattr(args, "name", None) or "default"

    profile = store.load(name)
    if profile is None:
        print(f"No user profile found for '{name}'. Use OpenAmer to build one.")
        return

    print(f"\n📊  User Profile: {profile.name}")
    print(f"  Sessions analyzed: {profile.total_sessions_analyzed}")
    print(f"  Created: {profile.created_at}")
    print(f"  Updated: {profile.updated_at}")
    print()

    if profile.skill_affinities:
        print("  Skill Affinities:")
        for skill, weight in sorted(
            profile.skill_affinities.items(),
            key=lambda x: -x[1],
        )[:8]:
            bar = "█" * int(weight * 10) + "░" * (10 - int(weight * 10))
            print(f"    {skill:<20} {bar} {weight:.1f}")

    if profile.favorite_tools:
        print(f"\n  Favorite Tools: {', '.join(profile.favorite_tools[:8])}")

    if profile.preferences:
        print("\n  Preferences:")
        for k, v in profile.preferences.items():
            print(f"    {k}: {v}")

    sp = profile.session_patterns or {}
    if sp:
        print("\n  Session Patterns:")
        for k, v in sp.items():
            print(f"    {k}: {v}")
    print()


def handle_profile_user_insights(args: argparse.Namespace) -> None:
    """Handler for `openamer profile user insights [name]`."""
    name = getattr(args, "name", None)
    store = ProfileStore()
    engine = ProfileInsights(store)

    if name:
        insights = engine.get_profile_insights_for(name)
    else:
        insights = ps_get_profile_insights()

    if not insights:
        print("No insights available yet.")
        return

    print("\n🔍  User Behavioral Insights")
    print(f"{'─' * 50}")
    for ins in insights:
        icon = {
            "info": "ℹ️",
            "usage": "📊",
            "power_user": "⚡",
            "suggestion": "💡",
            "pattern": "🔄",
            "affinity": "❤️",
            "tools": "🛠️",
            "session_length": "⏱️",
            "languages": "💻",
            "error": "❌",
        }.get(ins.get("type", ""), "•")
        print(f"  {icon} {ins.get('message', '')}")
    print()


# ---------------------------------------------------------------------------
# Parser builders (called from subcommands/skills.py and subcommands/profile.py)
# ---------------------------------------------------------------------------

def build_skills_stats_parser(subparsers) -> argparse.ArgumentParser:
    """Add the ``stats`` sub-action to the skills parser."""
    parser = subparsers.add_parser(
        "stats",
        help="Show skill usage statistics",
        description="Display usage statistics for all skills or a specific skill.",
    )
    parser.add_argument(
        "name",
        nargs="?",
        default=None,
        help="Skill name to show stats for (default: all skills)",
    )
    parser.set_defaults(func=handle_skills_stats)
    return parser


def build_skills_improve_parser(subparsers) -> argparse.ArgumentParser:
    """Add the ``improve`` sub-action to the skills parser."""
    parser = subparsers.add_parser(
        "improve",
        help="Suggest skill improvements",
        description=(
            "Analyze skill usage patterns and suggest improvements. "
            "Provide a skill name for targeted suggestions, or omit to "
            "auto-improve all skills with enough data."
        ),
    )
    parser.add_argument(
        "name",
        nargs="?",
        default=None,
        help="Skill name to analyze (default: analyze all skills)",
    )
    parser.set_defaults(func=handle_skills_improve)
    return parser


def build_profile_user_parser(subparsers) -> argparse.ArgumentParser:
    """Add the ``user`` sub-action to the profile parser.

    Contains sub-actions ``show`` and ``insights``.
    """
    parser = subparsers.add_parser(
        "user",
        help="User behavioral profile — show stats and insights",
        description=(
            "Manage your behavioral user profile: skill affinities, "
            "tool preferences, session patterns, and behavioral insights."
        ),
    )
    user_subparsers = parser.add_subparsers(dest="profile_user_action")

    # user show
    show_parser = user_subparsers.add_parser(
        "show",
        help="Show user behavioral profile",
    )
    show_parser.add_argument(
        "name",
        nargs="?",
        default=None,
        help="Profile name (default: 'default')",
    )
    show_parser.set_defaults(func=handle_profile_user_show)

    # user insights
    insights_parser = user_subparsers.add_parser(
        "insights",
        help="Show behavioral insights",
    )
    insights_parser.add_argument(
        "name",
        nargs="?",
        default=None,
        help="Profile name (default: all profiles)",
    )
    insights_parser.set_defaults(func=handle_profile_user_insights)

    return parser


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _print_skill_stats(stats: dict) -> None:
    """Pretty-print a single skill's stats."""
    print(f"\n📊  Skill Stats: {stats.get('skill_name', '?')}")
    print(f"{'─' * 40}")
    print(f"  Times used:     {stats.get('times_used', 0)}")
    print(f"  Last used:      {stats.get('last_used', 'never')}")
    print(f"  Success rate:   {stats.get('success_rate', 0):.1%}")
    print(f"  Avg duration:   {stats.get('avg_duration', 0):.1f}s")
    print(f"  User rating:    {stats.get('user_rating', 0):.1f} / 5.0")
    print()