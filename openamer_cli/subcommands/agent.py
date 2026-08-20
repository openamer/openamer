"""``openamer agent`` subcommand — create, list, show, delete agents.

An agent is a named OpenAmer entity that combines a skill directory,
an optional cron schedule, and a set of skills/tools.
"""

from __future__ import annotations

import sys
from typing import Callable


def _cmd_create(args) -> int:
    """Parse a description and build an agent."""
    from openamer_cli.agent_builder import create_agent_from_description, build_agent

    description = args.description
    if not description:
        print("Error: no description provided.")
        return 2

    spec = create_agent_from_description(description)
    result = build_agent(spec)

    print(f"Agent created: {result['name']}")
    print(f"  Description : {spec.description[:80]}{'...' if len(spec.description) > 80 else ''}")
    print(f"  Goal        : {spec.goal[:80]}{'...' if len(spec.goal) > 80 else ''}")
    if spec.cron_schedule:
        print(f"  Schedule    : {spec.cron_schedule}")
    if spec.skills:
        print(f"  Skills      : {', '.join(spec.skills)}")
    if spec.tools:
        print(f"  Tools       : {', '.join(spec.tools)}")
    cron_id = result.get("cron_job_id")
    if cron_id and not str(cron_id).startswith("error:"):
        print(f"  Cron job    : {cron_id}")
    elif cron_id and str(cron_id).startswith("error:"):
        print(f"  Cron job    : CREATION FAILED ({cron_id})")
    return 0


def _cmd_list(args) -> int:
    """List all created agents."""
    from openamer_cli.agent_builder import list_agents

    agents = list_agents()
    if not agents:
        print("No agents created yet.")
        return 0

    print(f"Agents ({len(agents)}):")
    print()
    for a in agents:
        name = a.get("name", "?")
        desc = a.get("description", "")
        goal = a.get("goal", "")
        schedule = a.get("cron_schedule") or "(no schedule)"
        skills = a.get("skills", [])
        first_line = (desc or goal)[:70]
        print(f"  {name}")
        print(f"    {first_line}")
        print(f"    Schedule: {schedule}  |  Skills: {len(skills)}")
        print()
    return 0


def _cmd_show(args) -> int:
    """Show a single agent's details."""
    from openamer_cli.agent_builder import show_agent

    agent = show_agent(args.name)
    if agent is None:
        print(f"Agent '{args.name}' not found.")
        return 1

    print(f"Name        : {agent.get('name', '?')}")
    print(f"Description : {agent.get('description', '')}")
    print(f"Goal        : {agent.get('goal', '')}")
    print(f"Created at  : {agent.get('created_at', '?')}")
    print(f"Schedule    : {agent.get('cron_schedule') or '(none)'}")
    print(f"Skills      : {', '.join(agent.get('skills', [])) or '(none)'}")
    print(f"Tools       : {', '.join(agent.get('tools', [])) or '(none)'}")
    cron_id = agent.get("cron_job_id")
    if cron_id:
        print(f"Cron job    : {cron_id}")
    return 0


def _cmd_delete(args) -> int:
    """Delete an agent."""
    from openamer_cli.agent_builder import delete_agent

    ok = delete_agent(args.name)
    if ok:
        print(f"Agent '{args.name}' deleted.")
        return 0
    else:
        print(f"Agent '{args.name}' not found.")
        return 1


def _cmd_ui(args) -> int:
    """Start the Agent Builder web UI."""
    from openamer_cli.agent_ui import cmd_agent_ui
    cmd_agent_ui(args)
    return 0


def build_agent_parser(subparsers) -> None:
    """Attach the ``agent`` subcommand tree to ``subparsers``."""
    p = subparsers.add_parser(
        "agent",
        help="Manage autonomous agents (create, list, show, delete, ui)",
        description="Create, list, show, delete OpenAmer agents, or launch the visual drag-drop builder UI.",
    )
    sub = p.add_subparsers(dest="agent_command")

    # agent create <description>
    c = sub.add_parser(
        "create",
        help="Create an agent from a natural-language description",
        description=(
            "Parse a natural-language description and build an agent. "
            "The parser looks for phrases like 'every 2 hours' for schedules, "
            "'using skills X,Y,Z' for skills, and 'with tools X,Y' for tools."
        ),
    )
    c.add_argument(
        "description",
        nargs="+",
        help="Natural-language description of the agent's purpose, schedule, skills, and tools",
    )
    c.set_defaults(func=_cmd_create)

    # agent list
    li = sub.add_parser("list", help="List all created agents")
    li.set_defaults(func=_cmd_list)

    # agent show <name>
    sh = sub.add_parser(
        "show",
        help="Show an agent's details",
        description="Show the full definition of a created agent.",
    )
    sh.add_argument("name", help="Agent name")
    sh.set_defaults(func=_cmd_show)

    # agent delete <name>
    d = sub.add_parser(
        "delete",
        help="Delete an agent and its associated skill directory",
        description="Remove an agent's definition, its skill directory, and its cron job (if any).",
    )
    d.add_argument("name", help="Agent name to delete")
    d.set_defaults(func=_cmd_delete)

    # agent ui
    ui = sub.add_parser(
        "ui",
        help="Launch the visual drag-drop Agent Builder UI",
        description="Start a local web server with a visual drag-drop agent builder interface.",
    )
    ui.add_argument("--port", "-p", type=int, default=8080, help="Port to listen on (default: 8080)")
    ui.set_defaults(func=_cmd_ui)