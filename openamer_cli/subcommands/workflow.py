"""``openamer workflow`` subcommand — create, run, and list workflows.

Usage:

    openamer workflow create                          — create and save a demo workflow
    openamer workflow run <name> [input]              — run a saved workflow
    openamer workflow run <name> --durable [--run-id] — crash-safe run with a step journal
    openamer workflow list                            — list saved workflows
    openamer workflow status [run-id]                 — inspect durable run journals
    openamer workflow visualize <name>                — show ASCII graph of a workflow
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone

from openamer_cli.durable_execution import (
    AmbiguousExternalEffect,
    DurableExecutionError,
    list_runs,
    open_run,
)
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

    journal = None
    if getattr(args, "durable", False):
        run_id = getattr(args, "run_id", None) or (
            f"{args.name}-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        )
        try:
            journal = open_run(run_id)
        except DurableExecutionError as e:
            print(f"Error: cannot open durable run {run_id!r}: {e}", file=sys.stderr)
            return 2
        print(f"Durable run: {journal.run_id}")
        print(f"Journal: {journal.journal_path}")

    engine = GraphWorkflowEngine()
    try:
        result = engine.execute(workflow, initial_input=args.input, journal=journal)
    except AmbiguousExternalEffect as e:
        print(f"HALTED: {e}", file=sys.stderr)
        print(
            "No step was re-executed. Verify the external system, then resolve "
            "the step with DurableRun.resolve_ambiguous(...) and re-run.",
            file=sys.stderr,
        )
        return 3
    except DurableExecutionError as e:
        print(f"Error: durable execution stopped: {e}", file=sys.stderr)
        return 2

    print(f"Executed workflow: {args.name}")
    print(f"Success: {result['success']}")
    print(f"Execution path: {' → '.join(result['execution_path'])}")
    if "durable" in result:
        durable = result["durable"]
        print(f"Durable steps executed now: {durable['executed_steps'] or '(none)'}")
        print(f"Durable steps restored from journal: {durable['reused_steps'] or '(none)'}")
    print(f"Results: {json.dumps(result['results'], indent=2, default=str)}")
    return 0


def _cmd_status(args) -> int:
    """Show durable run journals for the active profile."""
    run_id = getattr(args, "run_id", None)
    if not run_id:
        runs = list_runs()
        if not runs:
            print("No durable runs recorded for this profile.")
            return 0
        print(f"{'Run':<40} {'Steps':>9}  {'Updated':<26} State")
        print("-" * 92)
        for run in runs:
            if "error" in run:
                print(f"{run['run_id']:<40} {'?':>9}  {'?':<26} {run['error']}")
                continue
            state = "ok"
            if run["ambiguous"]:
                state = f"AMBIGUOUS({','.join(run['ambiguous'])})"
            elif run["failed"]:
                state = f"failed({','.join(run['failed'])})"
            print(
                f"{run['run_id']:<40} {run['completed']}/{run['steps']:>3}  "
                f"{run['updated_at'][:26]:<26} {state}"
            )
        return 0

    try:
        run = open_run(run_id)
    except DurableExecutionError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2
    if not run.journal_path.exists():
        print(f"No durable run {run_id!r} for this profile.")
        return 1

    snapshot = run.status()
    print(f"Run {snapshot['run_id']}")
    print(f"  journal: {snapshot['path']}")
    print(f"  profile: {snapshot['profile']}   revision: {snapshot['revision']}")
    print(f"  updated: {snapshot['updated_at']}")
    for step in snapshot["steps"]:
        print(
            f"  {step['status']:<10} {step['name']}  attempts={step['attempts']} "
            f"effect={step['effect']}"
        )
        if step["error"]:
            print(f"             error: {step['error']}")
    if snapshot["ambiguous"]:
        print(
            "Ambiguous external effects (verify externally, then resolve): "
            + ", ".join(snapshot["ambiguous"])
        )
        return 3
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
    run_p.add_argument(
        "--durable",
        action="store_true",
        help="Persist a step journal so an interrupted run resumes instead of "
             "repeating completed steps",
    )
    run_p.add_argument(
        "--run-id",
        default=None,
        help="Durable run id to create or resume (default: <workflow>-<UTC timestamp>)",
    )
    run_p.set_defaults(func=_cmd_run)

    # workflow status [run-id]
    status_p = sub.add_parser(
        "status",
        help="Show durable run journals",
        description=(
            "List durable runs for the active profile, or show the step "
            "journal of one run including in-flight external effects that "
            "need explicit resolution."
        ),
    )
    status_p.add_argument("run_id", nargs="?", default=None, help="Run id to inspect")
    status_p.set_defaults(func=_cmd_status)

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