"""``openamer swarm`` subcommand parser.

Manage and run swarm-based multi-agent orchestrations. Follows the same
pattern as ``openamer_cli/subcommands/crew.py``.

Provides:
  - ``openamer swarm run <task> --agents <n> --strategy <mode>``
  - ``openamer swarm create <name> --agents <n> --strategy <mode>``
  - ``openamer swarm list``
  - ``openamer swarm show <name>``
  - ``openamer swarm delete <name>``
"""

from __future__ import annotations

import sys


def build_swarm_parser(subparsers, *, cmd_swarm=None) -> None:
    """Attach the ``swarm`` subcommand (and sub-actions) to *subparsers*."""
    if cmd_swarm is None:
        from openamer_cli.subcommands.swarm import swarm_command
        cmd_swarm = swarm_command
    swarm_parser = subparsers.add_parser(
        "swarm",
        help="Run and manage multi-agent swarms",
        description=(
            "Orchestrate multiple agents with different strategies: "
            "parallel (fan-out), hierarchical, or debate."
        ),
    )
    swarm_subparsers = swarm_parser.add_subparsers(dest="swarm_command")

    # swarm run
    swarm_run = swarm_subparsers.add_parser(
        "run",
        help="Execute a swarm on a task",
        description="Run agents using the specified strategy.",
    )
    swarm_run.add_argument("task", help="Task description to execute")
    swarm_run.add_argument(
        "--agents",
        type=int,
        default=3,
        help="Number of agents to deploy (default: 3)",
    )
    swarm_run.add_argument(
        "--strategy",
        default="parallel",
        choices=["parallel", "hierarchical", "debate"],
        help="Execution strategy (default: parallel)",
    )
    swarm_run.add_argument(
        "--rounds",
        type=int,
        default=2,
        help="Number of debate rounds (debate strategy only, default: 2)",
    )
    swarm_run.add_argument(
        "--timeout",
        type=int,
        default=120,
        help="Max seconds per agent (default: 120)",
    )

    # swarm create
    swarm_create = swarm_subparsers.add_parser(
        "create",
        help="Save a new swarm configuration",
        description="Define a named swarm config for reuse.",
    )
    swarm_create.add_argument("name", help="Unique name for this configuration")
    swarm_create.add_argument(
        "--agents",
        type=int,
        default=3,
        help="Number of agents (default: 3)",
    )
    swarm_create.add_argument(
        "--strategy",
        default="parallel",
        choices=["parallel", "hierarchical", "debate"],
        help="Execution strategy (default: parallel)",
    )
    swarm_create.add_argument(
        "--timeout",
        type=int,
        default=120,
        help="Max seconds per agent (default: 120)",
    )

    # swarm list
    swarm_subparsers.add_parser(
        "list",
        aliases=["ls"],
        help="List all saved swarm configurations",
    )

    # swarm show
    swarm_show = swarm_subparsers.add_parser(
        "show",
        help="Show a saved swarm configuration",
    )
    swarm_show.add_argument("name", help="Name of the config to show")

    # swarm delete
    swarm_delete = swarm_subparsers.add_parser(
        "delete",
        aliases=["rm"],
        help="Delete a saved swarm configuration",
    )
    swarm_delete.add_argument("name", help="Name of the config to delete")

    swarm_parser.set_defaults(func=cmd_swarm)


# ---------------------------------------------------------------------------
# Handler
# ---------------------------------------------------------------------------


def swarm_command(args) -> int:
    """Dispatch ``openamer swarm <subcommand>``."""
    from openamer_cli.swarm_orchestrator import (
        SwarmConfig,
        SwarmStore,
        run_swarm_debate,
        run_swarm_hierarchical,
        run_swarm_parallel,
    )

    store = SwarmStore()
    sub = getattr(args, "swarm_command", None)

    if sub in (None, ""):
        print(
            "usage: openamer swarm <subcommand>\n"
            "\n"
            "subcommands:\n"
            "  run     Execute a swarm on a task\n"
            "  create  Save a new swarm configuration\n"
            "  list    List all saved swarm configurations\n"
            "  show    Show a saved swarm configuration\n"
            "  delete  Delete a saved swarm configuration\n"
            "\n"
            "Run `openamer swarm <subcommand> -h` for details.",
            file=sys.stderr,
        )
        return 1

    if sub == "run":
        return _cmd_run(args)
    elif sub == "create":
        return _cmd_create(args, store)
    elif sub in ("list", "ls"):
        return _cmd_list(store)
    elif sub == "show":
        return _cmd_show(args, store)
    elif sub in ("delete", "rm"):
        return _cmd_delete(args, store)

    print(f"Unknown swarm subcommand: {sub}", file=sys.stderr)
    return 1


# ---------------------------------------------------------------------------
# Sub-handlers
# ---------------------------------------------------------------------------


def _cmd_run(args) -> int:
    """Execute a swarm on a task."""
    from openamer_cli.swarm_orchestrator import (
        SwarmConfig,
        run_swarm_debate,
        run_swarm_hierarchical,
        run_swarm_parallel,
    )

    strategy = args.strategy
    config = SwarmConfig(
        name="cli-run",
        max_agents=args.agents,
        strategy={
            "parallel": "fan-out",
            "hierarchical": "hierarchical",
            "debate": "debate",
        }.get(strategy, "fan-out"),
        timeout=args.timeout,
    )

    agent_names = [f"agent-{i+1}" for i in range(args.agents)]

    print(f"🚀 Running swarm (strategy={strategy}, agents={args.agents})...")
    print(f"   Task: {args.task[:120]}{'…' if len(args.task) > 120 else ''}")
    print()

    if strategy == "debate":
        result = run_swarm_debate(args.task, agent_names, args.rounds)
        print(result.result)
        print()
        print(f"   ⏱  Duration: {result.duration_ms} ms")
        print(f"   📊 Confidence: {result.confidence:.0%}")
    elif strategy == "hierarchical":
        result = run_swarm_hierarchical(args.task, config)
        print(result.result)
        print()
        print(f"   ⏱  Duration: {result.duration_ms} ms")
        print(f"   📊 Confidence: {result.confidence:.0%}")
    else:
        results = run_swarm_parallel(args.task, agent_names, config)
        for r in results:
            print(f"── {r.agent_name} (conf: {r.confidence:.0%}, {r.duration_ms}ms) ──")
            print(r.result)
            print()
        avg_conf = (
            sum(r.confidence for r in results) / len(results) if results else 0
        )
        total_ms = sum(r.duration_ms for r in results)
        print(f"   ⏱  Total: {total_ms} ms  |  Avg Confidence: {avg_conf:.0%}")

    return 0


def _cmd_create(args, store) -> int:
    """Save a new swarm configuration."""
    strategy_map = {
        "parallel": "fan-out",
        "hierarchical": "hierarchical",
        "debate": "debate",
    }
    config = SwarmConfig(
        name=args.name,
        max_agents=args.agents,
        strategy=strategy_map.get(args.strategy, "fan-out"),
        timeout=args.timeout,
    )
    store.save(config)
    print(f"✅ Swarm config '{args.name}' saved.")
    return 0


def _cmd_list(store) -> int:
    """List all saved swarm configurations."""
    configs = store.list_all()
    if not configs:
        print("No swarm configurations saved.")
        return 0

    print(f"Saved swarm configurations ({len(configs)}):")
    print()
    for cfg in configs:
        print(f"  📋 {cfg.name}")
        print(f"     Agents: {cfg.max_agents}  |  Strategy: {cfg.strategy}"
              f"  |  Timeout: {cfg.timeout}s")
    return 0


def _cmd_show(args, store) -> int:
    """Show details of a saved configuration."""
    config = store.load(args.name)
    if config is None:
        print(f"❌ Swarm config '{args.name}' not found.", file=sys.stderr)
        return 1
    print(f"Name:     {config.name}")
    print(f"Agents:   {config.max_agents}")
    print(f"Strategy: {config.strategy}")
    print(f"Timeout:  {config.timeout}s")
    return 0


def _cmd_delete(args, store) -> int:
    """Delete a saved configuration."""
    if store.delete(args.name):
        print(f"🗑️  Swarm config '{args.name}' deleted.")
        return 0
    print(f"❌ Swarm config '{args.name}' not found.", file=sys.stderr)
    return 1