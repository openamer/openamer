"""``openamer workflow`` subcommand — create, run, and list workflows.

Usage:

    openamer workflow create                          — create and save a demo workflow
    openamer workflow run <name> [input]              — run a saved workflow
    openamer workflow list                            — list saved workflows
    openamer workflow visualize <name>                — show ASCII graph of a workflow
"""

from __future__ import annotations

import json
import sys

from openamer_cli.graph_workflow import (
    GraphWorkflowEngine,
    WorkflowGraph,
    WorkflowNode,
    WorkflowStore,
)


def _cmd_create(args) -> int:
    """Create and save an example workflow."""
    engine = GraphWorkflowEngine()
    store = WorkflowStore()

    g = WorkflowGraph(
        nodes={
            "parse": WorkflowNode(
                id="parse", type="task", name="Parse Input",
                config={"action": "parse"},
                next_node_ids=["validate"],
            ),
            "validate": WorkflowNode(
                id="validate", type="condition", name="Validate Input",
                config={"field": "_input", "expected": "valid"},
                next_node_ids=["process", "error"],
            ),
            "process": WorkflowNode(
                id="process", type="task", name="Process Data",
                config={"action": "transform"},
                next_node_ids=["output"],
            ),
            "output": WorkflowNode(
                id="output", type="output", name="Final Output",
                config={"status": "ok"},
            ),
            "error": WorkflowNode(
                id="error", type="output", name="Error Handler",
                config={"status": "error", "message": "Validation failed"},
            ),
        },
        entry_node_id="parse",
    )

    path = store.save("demo-workflow", g)
    print(f"Created demo workflow 'demo-workflow'")
    print(f"Saved to: {path}")
    print()
    print(engine.visualize(g))
    return 0


def _cmd_run(args) -> int:
    """Load and execute a saved workflow."""
    store = WorkflowStore()
    try:
        workflow = store.load(args.name)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    engine = GraphWorkflowEngine()
    result = engine.execute(workflow, initial_input=args.input)

    print(f"Executed workflow: {args.name}")
    print(f"Success: {result['success']}")
    print(f"Execution path: {' → '.join(result['execution_path'])}")
    print(f"Results: {json.dumps(result['results'], indent=2, default=str)}")
    return 0


def _cmd_list(args) -> int:
    """List all saved workflows."""
    store = WorkflowStore()
    workflows = store.list_workflows()

    if not workflows:
        print("No workflows saved yet.")
        return 0

    print(f"{'Name':<25} {'Nodes':>6} {'Saved':<30}")
    print("-" * 65)
    for wf in workflows:
        name = wf.get("name", "?")
        nodes = wf.get("node_count", "?")
        saved = wf.get("saved_at", "?")
        if saved and len(saved) > 25:
            saved = saved[:25]
        print(f"{name:<25} {nodes:>6} {saved:<30}")
    return 0


def _cmd_visualize(args) -> int:
    """Show ASCII visualization of a workflow."""
    store = WorkflowStore()
    try:
        workflow = store.load(args.name)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    engine = GraphWorkflowEngine()
    print(engine.visualize(workflow))
    return 0


def build_workflow_parser(subparsers) -> None:
    """Attach the ``workflow`` subcommand tree to ``subparsers``."""
    p = subparsers.add_parser(
        "workflow",
        help="Create, run, and list graph-based workflows",
        description=(
            "Manage graph-based workflow definitions.  Workflows are DAGs of "
            "task, condition, parallel, and output nodes that can be saved, "
            "loaded, and executed."
        ),
    )
    sub = p.add_subparsers(dest="workflow_command")

    # workflow create
    create_p = sub.add_parser(
        "create",
        help="Create a new demo workflow",
        description="Create an example workflow and save it to the workflow store.",
    )
    create_p.set_defaults(func=_cmd_create)

    # workflow run <name> [input]
    run_p = sub.add_parser(
        "run",
        help="Run a saved workflow",
        description="Load and execute a saved workflow by name.",
    )
    run_p.add_argument("name", help="Workflow name to execute")
    run_p.add_argument("input", nargs="?", default=None, help="Optional initial input value")
    run_p.set_defaults(func=_cmd_run)

    # workflow list
    list_p = sub.add_parser(
        "list", aliases=["ls"],
        help="List saved workflows",
        description="List all workflows stored in the workflow store.",
    )
    list_p.set_defaults(func=_cmd_list)

    # workflow visualize <name>
    viz_p = sub.add_parser(
        "visualize", aliases=["viz"],
        help="Visualize a workflow as ASCII art",
        description="Render a saved workflow's DAG as an ASCII art diagram.",
    )
    viz_p.add_argument("name", help="Workflow name to visualize")
    viz_p.set_defaults(func=_cmd_visualize)