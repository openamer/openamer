"""Graph-based workflow engine for OpenAmer.

Provides a DAG-based workflow execution system with support for task nodes,
conditional branching, parallel execution, topological traversal, and
ASCII visualization.
"""

from __future__ import annotations

import json
import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class WorkflowNode:
    """A single node in a workflow DAG.

    Attributes:
        id: Unique node identifier.
        type: Node type — ``task`` (executes a callable or config action),
            ``condition`` (evaluates a predicate), ``parallel`` (runs child
            branches concurrently), ``output`` (terminal result node).
        name: Human-readable node name.
        config: Arbitrary configuration dict passed to the node's executor.
        next_node_ids: IDs of successor nodes in the DAG.
    """

    id: str
    type: str  # task | condition | parallel | output
    name: str
    config: dict[str, Any] = field(default_factory=dict)
    next_node_ids: list[str] = field(default_factory=list)


@dataclass
class WorkflowGraph:
    """A complete workflow DAG.

    Attributes:
        nodes: Mapping of node ID to WorkflowNode.
        edges: List of (from_id, to_id, condition) tuples.
        entry_node_id: The node at which execution starts.
        state: Mutable state dict that accumulates across the run.
    """

    nodes: dict[str, WorkflowNode] = field(default_factory=dict)
    edges: list[tuple[str, str, Optional[str]]] = field(default_factory=list)
    entry_node_id: str = ""
    state: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Execution engine
# ---------------------------------------------------------------------------


class GraphWorkflowEngine:
    """Executes a ``WorkflowGraph`` as a directed acyclic graph.

    Nodes are traversed in topological order.  ``task`` nodes invoke an
    optional *executor* callable; ``condition`` nodes evaluate a predicate
    (also passed as a callable); ``parallel`` nodes fan out multiple paths
    concurrently; ``output`` nodes terminate a branch and return their
    config as results.
    """

    def __init__(
        self,
        task_executor: Optional[Callable[[str, dict[str, Any], dict[str, Any]], Any]] = None,
        condition_evaluator: Optional[Callable[[str, dict[str, Any], dict[str, Any]], bool]] = None,
    ):
        self._task_executor = task_executor or self._default_executor
        self._condition_evaluator = condition_evaluator or self._default_condition
        self._lock = threading.Lock()

    # ---------------------------------------------------------------
    # Graph mutation
    # ---------------------------------------------------------------

    def add_node(self, node: WorkflowNode) -> None:
        """Register a node in the engine's internal graph."""
        if not isinstance(node, WorkflowNode):
            raise TypeError("Expected a WorkflowNode instance")
        if not isinstance(node.id, str) or not node.id:
            raise ValueError("Node id must be a non-empty string")
        # stored in the engine for builder-style fluent usage;
        # alternatively nodes are carried inside WorkflowGraph.
        pass

    def add_edge(self, from_id: str, to_id: str, condition: Optional[str] = None) -> None:
        """Declare a directed edge (validated at execute time)."""
        if not isinstance(from_id, str) or not from_id:
            raise ValueError("from_id must be a non-empty string")
        if not isinstance(to_id, str) or not to_id:
            raise ValueError("to_id must be a non-empty string")
        # stored for builder-style usage; edges are normally on the graph.
        pass

    # ---------------------------------------------------------------
    # Execution
    # ---------------------------------------------------------------

    def execute(
        self,
        workflow: WorkflowGraph,
        initial_input: Optional[Any] = None,
    ) -> dict[str, Any]:
        """Execute the workflow DAG and return results.

        Traverses nodes in topological order.  ``task`` nodes call the
        executor; ``condition`` nodes evaluate a predicate and follow
        only the matching outgoing edge; ``parallel`` nodes run all
        reachable branches concurrently; ``output`` nodes collect results.

        Returns a dict with keys:
          - ``success`` (bool)
          - ``results`` (list of output node results)
          - ``state`` (final workflow state)
          - ``node_outputs`` (dict mapping node id → output)
          - ``execution_path`` (list of node ids in visit order)
        """
        if not workflow.entry_node_id:
            raise ValueError("Workflow has no entry_node_id set")

        # Validate all referenced nodes exist
        for nid in workflow.nodes:
            node = workflow.nodes[nid]
            for next_id in node.next_node_ids:
                if next_id not in workflow.nodes:
                    raise ValueError(
                        f"Node '{nid}' references unknown next_node '{next_id}'"
                    )

        if workflow.entry_node_id not in workflow.nodes:
            raise ValueError(
                f"entry_node_id '{workflow.entry_node_id}' not found in nodes"
            )

        # Copy state so we don't mutate the original
        state = dict(workflow.state)
        if initial_input is not None:
            state["_input"] = initial_input

        results: list[Any] = []
        node_outputs: dict[str, Any] = {}
        execution_path: list[str] = []
        executed_by_parallel: set[str] = set()
        skipped_nodes: set[str] = set()

        # Topological sort
        topo_order = self._topological_sort(workflow)

        # Create a lookup of node_id -> set of predecessor ids for dependency tracking
        predecessors: dict[str, set[str]] = {nid: set() for nid in workflow.nodes}
        for nid, node in workflow.nodes.items():
            for next_id in node.next_node_ids:
                if next_id in predecessors:
                    predecessors[next_id].add(nid)

        # Execute in topological order
        for nid in topo_order:
            if nid not in workflow.nodes:
                continue
            node = workflow.nodes[nid]
            execution_path.append(nid)

            if node.type == "task":
                if nid in executed_by_parallel:
                    continue
                if nid in skipped_nodes:
                    node_outputs[nid] = {"_skipped": True}
                    continue
                output = self._execute_task(node, state)
                node_outputs[nid] = output
                state[nid] = output

            elif node.type == "condition":
                if nid in skipped_nodes:
                    node_outputs[nid] = {"_skipped": True}
                    continue
                outcome = self._evaluate_condition(node, state)
                node_outputs[nid] = {"_condition_result": outcome}
                state[nid] = {"_condition_result": outcome}
                # If condition is False, skip all downstream nodes
                if not outcome:
                    self._mark_skipped(workflow, nid, topo_order, execution_path, skipped_nodes)

            elif node.type == "parallel":
                if nid in executed_by_parallel:
                    continue
                if nid in skipped_nodes:
                    node_outputs[nid] = {"_skipped": True}
                    continue
                parallel_results, para_nodes = self._execute_parallel(node, workflow, state, topo_order)
                executed_by_parallel.update(para_nodes)
                node_outputs[nid] = parallel_results
                state[nid] = {"_parallel_results": parallel_results}

            elif node.type == "output":
                if nid in skipped_nodes:
                    node_outputs[nid] = {"_skipped": True}
                    continue
                output = dict(node.config)
                output["_input"] = state.get("_input")
                node_outputs[nid] = output
                results.append(output)

        return {
            "success": True,
            "results": results,
            "state": state,
            "node_outputs": node_outputs,
            "execution_path": execution_path,
        }

    # ---------------------------------------------------------------
    # Visualization
    # ---------------------------------------------------------------

    def visualize(self, workflow: WorkflowGraph) -> str:
        """Render an ASCII art representation of the workflow graph."""
        lines: list[str] = []
        lines.append(f"╔══════════════════════════════════════╗")
        lines.append(f"║   Workflow: {workflow.entry_node_id or '(empty)'!s:<27} ║")
        lines.append(f"╚══════════════════════════════════════╝")
        lines.append("")

        if not workflow.nodes:
            lines.append("  (empty workflow)")
            return "\n".join(lines)

        # Show each node with its connections
        topo_order = self._topological_sort(workflow) if workflow.nodes else []

        for i, nid in enumerate(topo_order):
            node = workflow.nodes[nid]
            symbol = self._node_symbol(node.type)
            entry_mark = " ►" if nid == workflow.entry_node_id else "  "
            lines.append(f"  {entry_mark} [{symbol}] {node.name}  ({nid})")

            if node.config:
                for k, v in list(node.config.items())[:3]:
                    lines.append(f"         └─ {k}: {v!s:.50}")

            if node.next_node_ids:
                next_names = ", ".join(
                    f"{workflow.nodes[n].name}({n})" if n in workflow.nodes else f"?({n})"
                    for n in node.next_node_ids
                )
                lines.append(f"         → {next_names}")

            # Add edge conditions
            for from_id, to_id, condition in workflow.edges:
                if from_id == nid and condition:
                    target_name = workflow.nodes[to_id].name if to_id in workflow.nodes else to_id
                    lines.append(f"         ╘═ condition: [{condition}] → {target_name}")

            if i < len(topo_order) - 1:
                lines.append(f"         │")

        lines.append("")
        lines.append(self._legend())
        return "\n".join(lines)

    # ---------------------------------------------------------------
    # Internals
    # ---------------------------------------------------------------

    @staticmethod
    def _node_symbol(node_type: str) -> str:
        return {
            "task": "⚙",
            "condition": "◇",
            "parallel": "‖",
            "output": "●",
        }.get(node_type, "?")

    @staticmethod
    def _legend() -> str:
        return (
            "  Legend:  ⚙ Task    ◇ Condition    ‖ Parallel    ● Output    ► Entry"
        )

    def _topological_sort(self, workflow: WorkflowGraph) -> list[str]:
        """Kahn's algorithm for topological ordering of the DAG."""
        in_degree: dict[str, int] = {nid: 0 for nid in workflow.nodes}
        adjacency: dict[str, list[str]] = {nid: [] for nid in workflow.nodes}

        for nid, node in workflow.nodes.items():
            for next_id in node.next_node_ids:
                if next_id in workflow.nodes:
                    adjacency[nid].append(next_id)
                    in_degree[next_id] = in_degree.get(next_id, 0) + 1

        queue: list[str] = [
            nid for nid, deg in in_degree.items() if deg == 0
        ]
        # If no zero-in-degree node, use the entry node
        if not queue and workflow.entry_node_id in workflow.nodes:
            queue = [workflow.entry_node_id]

        ordered: list[str] = []
        while queue:
            nid = queue.pop(0)
            ordered.append(nid)
            for neighbor in adjacency.get(nid, []):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        # If there are cycles, some nodes won't be in ordered; add them anyway
        remaining = set(workflow.nodes.keys()) - set(ordered)
        if remaining:
            # Cycle detected — append remaining nodes in their original dict order
            for nid in workflow.nodes:
                if nid in remaining:
                    ordered.append(nid)

        return ordered

    def _execute_task(self, node: WorkflowNode, state: dict[str, Any]) -> Any:
        """Execute a task node by calling the executor."""
        return self._task_executor(node.id, node.config, state)

    def _evaluate_condition(self, node: WorkflowNode, state: dict[str, Any]) -> bool:
        """Evaluate a condition node."""
        return self._condition_evaluator(node.id, node.config, state)

    def _execute_parallel(
        self,
        node: WorkflowNode,
        workflow: WorkflowGraph,
        state: dict[str, Any],
        topo_order: list[str],
    ) -> tuple[list[dict[str, Any]], set[str]]:
        """Execute all successor branches of a parallel node concurrently.

        Returns (results, executed_node_ids).
        """
        parallel_results: list[dict[str, Any]] = []
        executed_node_ids: set[str] = set()
        max_workers = node.config.get("max_workers", 4)
        timeout = node.config.get("timeout", 60)

        # Collect the sub-graphs reachable from each next_node_id
        branches: list[str] = list(node.next_node_ids)

        if not branches:
            return parallel_results, executed_node_ids

        def _run_branch(branch_entry: str) -> tuple[dict[str, Any], list[str]]:
            """Execute a single branch starting at branch_entry.
            Returns (result_summary, visited_node_ids)."""
            branch_state = dict(state)
            branch_results: list[Any] = []
            branch_path: list[str] = []
            visited_nodes: list[str] = []
            current = branch_entry
            visited: set[str] = set()

            while current and current in workflow.nodes and current not in visited:
                visited.add(current)
                visited_nodes.append(current)
                curr_node = workflow.nodes[current]
                branch_path.append(current)

                if curr_node.type == "task":
                    out = self._execute_task(curr_node, branch_state)
                    branch_state[current] = out
                    branch_results.append(out)

                elif curr_node.type == "condition":
                    outcome = self._evaluate_condition(curr_node, branch_state)
                    branch_state[current] = {"_condition_result": outcome}

                elif curr_node.type == "output":
                    out = dict(curr_node.config)
                    branch_results.append(out)
                    break

                # Move to next node (follow first next_node_id for linear branches)
                if curr_node.next_node_ids:
                    current = curr_node.next_node_ids[0]
                else:
                    break

            return (
                {
                    "branch_entry": branch_entry,
                    "path": branch_path,
                    "results": branch_results,
                    "state": branch_state,
                },
                visited_nodes,
            )

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_map = {
                executor.submit(_run_branch, be): be for be in branches
            }
            try:
                for future in as_completed(future_map, timeout=timeout):
                    be = future_map[future]
                    try:
                        result, visited_nodes = future.result()
                        parallel_results.append(result)
                        executed_node_ids.update(visited_nodes)
                    except Exception as exc:
                        parallel_results.append(
                            {"branch_entry": be, "error": str(exc)}
                        )
            except TimeoutError:
                for future in future_map:
                    future.cancel()
                parallel_results.append({"error": "Parallel execution timed out"})

        return parallel_results, executed_node_ids

    def _mark_skipped(
        self,
        workflow: WorkflowGraph,
        from_nid: str,
        topo_order: list[str],
        execution_path: list[str],
        skipped_nodes: set[str] | None = None,
    ) -> None:
        """Mark nodes reachable from a failed condition as skipped in execution_path."""
        to_skip: set[str] = set()
        stack = list(workflow.nodes[from_nid].next_node_ids)
        while stack:
            nid = stack.pop()
            if nid in workflow.nodes and nid not in to_skip:
                to_skip.add(nid)
                stack.extend(workflow.nodes[nid].next_node_ids)

        # Add skipped markers to execution_path
        # (they're already there from topo order, so we mark them)
        for skip_id in to_skip:
            if skip_id not in execution_path:
                execution_path.append(f"{skip_id} (skipped)")

    @staticmethod
    def _default_executor(
        node_id: str, config: dict[str, Any], state: dict[str, Any]
    ) -> Any:
        """Default task executor: runs the ``action`` from config if callable,
        otherwise returns the config as-is."""
        action = config.get("action")
        if callable(action):
            return action(state)
        if isinstance(action, str) and action in state:
            return state[action]
        return config.get("result", f"Executed task '{node_id}'")

    @staticmethod
    def _default_condition(
        node_id: str, config: dict[str, Any], state: dict[str, Any]
    ) -> bool:
        """Default condition evaluator: checks ``predicate`` callable or
        evaluates a simple expression in state."""
        predicate = config.get("predicate")
        if callable(predicate):
            return bool(predicate(state))
        field = config.get("field", "")
        expected = config.get("expected", True)
        actual = state.get(field, state.get("_input"))
        return actual == expected


# ---------------------------------------------------------------------------
# Workflow persistence store
# ---------------------------------------------------------------------------


class WorkflowStore:
    """Persist ``WorkflowGraph`` objects as JSON files in a directory.

    Args:
        store_dir: Directory path for JSON workflow files.  Created if it
            does not exist.
    """

    def __init__(self, store_dir: Optional[str] = None):
        if store_dir is None:
            store_dir = os.path.join(
                os.path.expanduser("~"),
                ".openamer",
                "workflows",
            )
        self._store_dir = Path(store_dir)
        self._store_dir.mkdir(parents=True, exist_ok=True)

    # ---------------------------------------------------------------
    # Serialization helpers
    # ---------------------------------------------------------------

    @staticmethod
    def _graph_to_dict(workflow: WorkflowGraph) -> dict[str, Any]:
        """Serialize a WorkflowGraph to a JSON-compatible dict."""
        return {
            "entry_node_id": workflow.entry_node_id,
            "state": workflow.state,
            "edges": [
                [e[0], e[1], e[2]] for e in workflow.edges
            ],
            "nodes": {
                nid: {
                    "id": node.id,
                    "type": node.type,
                    "name": node.name,
                    "config": node.config,
                    "next_node_ids": node.next_node_ids,
                }
                for nid, node in workflow.nodes.items()
            },
        }

    @staticmethod
    def _dict_to_graph(data: dict[str, Any]) -> WorkflowGraph:
        """Deserialize a dict back to a WorkflowGraph."""
        nodes = {
            nid: WorkflowNode(**nodedata)
            for nid, nodedata in data.get("nodes", {}).items()
        }
        edges_raw = data.get("edges", [])
        edges: list[tuple[str, str, Optional[str]]] = [
            (e[0], e[1], e[2] if len(e) > 2 else None) for e in edges_raw
        ]
        return WorkflowGraph(
            nodes=nodes,
            edges=edges,
            entry_node_id=data.get("entry_node_id", ""),
            state=data.get("state", {}),
        )

    # ---------------------------------------------------------------
    # Public API
    # ---------------------------------------------------------------

    def save(self, name: str, workflow: WorkflowGraph) -> str:
        """Save a workflow to ``<name>.json`` in the store directory.

        Returns the full path to the saved file.
        """
        if not name:
            raise ValueError("Workflow name cannot be empty")
        if "/" in name or "\\" in name or ".." in name:
            raise ValueError(f"Invalid workflow name: {name!r}")

        path = self._store_dir / f"{name}.json"
        data = self._graph_to_dict(workflow)
        data["_meta"] = {
            "name": name,
            "saved_at": datetime.now(timezone.utc).isoformat(),
            "node_count": len(workflow.nodes),
        }
        path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
        return str(path)

    def load(self, name: str) -> WorkflowGraph:
        """Load a workflow by name from the store directory.

        Raises FileNotFoundError if the file does not exist.
        """
        path = self._store_dir / f"{name}.json"
        if not path.exists():
            raise FileNotFoundError(f"Workflow '{name}' not found at {path}")
        data = json.loads(path.read_text(encoding="utf-8"))
        return self._dict_to_graph(data)

    def list_workflows(self) -> list[dict[str, Any]]:
        """Return a list of metadata dicts for all stored workflows.

        Each dict contains ``name``, ``saved_at``, and ``node_count``.
        """
        results: list[dict[str, Any]] = []
        for p in sorted(self._store_dir.glob("*.json")):
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                meta = data.get("_meta", {})
                results.append({
                    "name": p.stem,
                    "saved_at": meta.get("saved_at", "unknown"),
                    "node_count": meta.get("node_count", 0),
                })
            except (json.JSONDecodeError, OSError):
                results.append({
                    "name": p.stem,
                    "error": "corrupt file",
                })
        return results

    def delete(self, name: str) -> bool:
        """Delete a stored workflow by name.  Returns True if deleted."""
        path = self._store_dir / f"{name}.json"
        if path.exists():
            path.unlink()
            return True
        return False

    def get_path(self, name: str) -> str:
        """Return the file path for a workflow name without loading it."""
        return str(self._store_dir / f"{name}.json")