"""``openamer crew`` subcommand parser.

Manage and run crew-based multi-agent teams. Follows the pattern in
``openamer_cli/subcommands/cron.py`` and ``skills.py``.
"""

from __future__ import annotations

import argparse
from typing import Callable


def build_crew_parser(subparsers, *, cmd_crew: Callable) -> None:
    """Attach the ``crew`` subcommand (and sub-actions) to ``subparsers``."""
    crew_parser = subparsers.add_parser(
        "crew",
        help="Manage and run multi-agent crews (CrewAI-style orchestration)",
        description=(
            "Define 'crews' with multiple agents that have different roles "
            "(researcher, writer, analyst, coder, reviewer) and they "
            "collaborate on a task."
        ),
    )
    crew_subparsers = crew_parser.add_subparsers(dest="crew_command")

    # crew create
    crew_create = crew_subparsers.add_parser(
        "create",
        help="Create a new crew definition",
        description="Define a crew with one or more member agents.",
    )
    crew_create.add_argument(
        "name",
        help="Unique name for the crew (used to reference it later)",
    )
    crew_create.add_argument(
        "--members",
        "-m",
        required=True,
        help=(
            "Comma-separated list of roles. Each entry can be just a role "
            "(e.g. 'researcher') or 'name:role' for a custom name. "
            "Valid roles: researcher, writer, analyst, coder, reviewer"
        ),
    )
    crew_create.add_argument(
        "--task",
        default="",
        help="Default task description for this crew",
    )
    crew_create.add_argument(
        "--output-format",
        default="markdown",
        choices=["markdown", "json", "text"],
        help="Output format for crew results (default: markdown)",
    )
    crew_create.add_argument(
        "--goal",
        action="append",
        default=[],
        dest="goals",
        help=(
            "Goal for a member, specified as 'role: goal text'. "
            "Repeat for multiple members."
        ),
    )
    crew_create.add_argument(
        "--backstory",
        action="append",
        default=[],
        dest="backstories",
        help=(
            "Backstory for a member, specified as 'role: backstory text'. "
            "Repeat for multiple members."
        ),
    )

    # crew list
    crew_subparsers.add_parser(
        "list",
        aliases=["ls"],
        help="List all saved crew definitions",
    )

    # crew show
    crew_show = crew_subparsers.add_parser(
        "show",
        help="Show crew details",
    )
    crew_show.add_argument("name", help="Name of the crew to show")

    # crew run
    crew_run = crew_subparsers.add_parser(
        "run",
        help="Run a crew on a task",
        description=(
            "Executes the crew workflow. In sequential mode, results are "
            "piped from one member to the next (researcher -> writer -> "
            "analyst -> coder -> reviewer). In parallel mode, independent "
            "members run simultaneously."
        ),
    )
    crew_run.add_argument(
        "name",
        help="Name of the crew to run",
    )
    crew_run.add_argument(
        "task",
        nargs="?",
        default="",
        help="Task description to execute (optional — uses crew's default task)",
    )
    crew_run.add_argument(
        "--sequential",
        action="store_true",
        default=True,
        dest="sequential",
        help="Run members sequentially (default)",
    )
    crew_run.add_argument(
        "--parallel",
        action="store_true",
        dest="parallel",
        help="Run independent members in parallel",
    )

    # crew delete
    crew_delete = crew_subparsers.add_parser(
        "delete",
        aliases=["rm"],
        help="Delete a crew definition",
    )
    crew_delete.add_argument("name", help="Name of the crew to delete")

    crew_parser.set_defaults(func=cmd_crew)


# ---------------------------------------------------------------------------
# Handler
# ---------------------------------------------------------------------------


def crew_command(args: argparse.Namespace) -> int:
    """Dispatch ``openamer crew <subcommand>``."""
    from openamer_cli.crew_orchestrator import Crew, CrewMember, CrewStore

    store = CrewStore()
    sub = getattr(args, "crew_command", None)

    if sub in (None, ""):
        print(
            "usage: openamer crew <subcommand>\n"
            "\n"
            "subcommands:\n"
            "  create   Define a new crew\n"
            "  list     List all saved crews\n"
            "  show     Show crew details\n"
            "  run      Execute a crew workflow\n"
            "  delete   Remove a crew definition\n"
            "\n"
            "Run `openamer crew <subcommand> -h` for details.",
            file=sys.stderr,
        )
        return 1

    if sub == "create":
        return _cmd_create(args, store)
    elif sub == "list":
        return _cmd_list(args, store)
    elif sub == "show":
        return _cmd_show(args, store)
    elif sub == "run":
        return _cmd_run(args, store)
    elif sub in ("delete", "rm"):
        return _cmd_delete(args, store)

    print(f"Unknown crew subcommand: {sub}", file=sys.stderr)
    return 1


def _parse_member_spec(members_str: str) -> list[tuple[str, str]]:
    """Parse --members value into list of (name, role) tuples.

    Supports:
      'researcher' -> ('researcher', 'researcher')
      'Alice:researcher' -> ('Alice', 'researcher')
      'researcher,writer,bob:analyst' -> multiple entries
    """
    entries: list[tuple[str, str]] = []
    for part in members_str.split(","):
        part = part.strip()
        if not part:
            continue
        if ":" in part:
            name, role = part.split(":", 1)
            entries.append((name.strip(), role.strip()))
        else:
            entries.append((part.strip(), part.strip()))
    return entries


def _parse_role_meta(
    meta_list: list[str],
    prefix: str,
) -> dict[str, str]:
    """Parse --goal or --backstory entries like 'role: value' into a dict."""
    result: dict[str, str] = {}
    for entry in meta_list:
        if ":" in entry:
            role, _, value = entry.partition(":")
            result[role.strip()] = value.strip()
    return result


import sys  # noqa: E402 (imported here for the subcommand dispatch above)


def _cmd_create(args, store: CrewStore) -> int:
    """Handle ``openamer crew create <name> --members ...``."""
    name = args.name
    members_spec = _parse_member_spec(args.members)
    goals = _parse_role_meta(getattr(args, "goals", []), "goal")
    backstories = _parse_role_meta(getattr(args, "backstories", []), "backstory")

    members = []
    for m_name, m_role in members_spec:
        member = CrewMember(
            name=m_name,
            role=m_role,
            goal=goals.get(m_role, f"Complete {m_role} tasks effectively"),
            backstory=backstories.get(m_role, ""),
        )
        members.append(member)

    crew = Crew(
        name=name,
        members=members,
        task=getattr(args, "task", ""),
        output_format=getattr(args, "output_format", "markdown"),
    )
    path = store.save(crew)
    print(f"✓ Crew {name!r} created with {len(members)} member(s)")
    print(f"  File: {path}")
    return 0


def _cmd_list(args, store: CrewStore) -> int:
    """Handle ``openamer crew list``."""
    names = store.list()
    if not names:
        print("No crews defined. Use `openamer crew create <name> --members ...` to add one.")
        return 0

    print(f"Crews ({len(names)}):")
    for name in names:
        try:
            crew = store.load(name)
            roles = ", ".join(m.role.title() for m in crew.members)
            print(f"  • {name}  ({roles})")
        except Exception:
            print(f"  • {name}  (⚠ could not load)")
    return 0


def _cmd_show(args, store: CrewStore) -> int:
    """Handle ``openamer crew show <name>``."""
    try:
        crew = store.load(args.name)
    except FileNotFoundError:
        print(f"✗ Crew {args.name!r} not found.", file=sys.stderr)
        return 1

    print(f"Crew: {crew.name}")
    print(f"  Output format: {crew.output_format}")
    print(f"  Default task: {crew.task or '(none)'}")
    print(f"  Members ({len(crew.members)}):")
    for m in crew.members:
        print(f"    • {m.name}  —  {m.role.title()}")
        if m.goal:
            print(f"      Goal: {m.goal}")
        if m.backstory:
            print(f"      Backstory: {m.backstory}")
    return 0


def _cmd_run(args, store: CrewStore) -> int:
    """Handle ``openamer crew run <name> [task]``."""
    name = args.name
    task = args.task or ""

    try:
        crew = store.load(name)
    except FileNotFoundError:
        print(f"✗ Crew {name!r} not found.", file=sys.stderr)
        return 1

    if not task:
        task = crew.task
    if not task:
        print("✗ No task provided and crew has no default task.", file=sys.stderr)
        return 1

    # Show what we're about to run
    roles = ", ".join(m.role.title() for m in crew.members)
    mode = "parallel" if getattr(args, "parallel", False) else "sequential"
    print(f"🚀 Running crew {name!r} ({roles}) — {mode} mode")
    print(f"   Task: {task[:120]}{'...' if len(task) > 120 else ''}")
    print()

    # Execute — no parent_agent, so we use subprocess oneshot
    from openamer_cli.crew_orchestrator import run_crew

    try:
        result = run_crew(name, task, mode=mode)
        print(result)
        print()
        print("✓ Crew run complete.")
        return 0
    except Exception as e:
        print(f"✗ Crew run failed: {e}", file=sys.stderr)
        return 1


def _cmd_delete(args, store: CrewStore) -> int:
    """Handle ``openamer crew delete <name>``."""
    deleted = store.delete(args.name)
    if deleted:
        print(f"✓ Crew {args.name!r} deleted.")
        return 0
    print(f"✗ Crew {args.name!r} not found.", file=sys.stderr)
    return 1