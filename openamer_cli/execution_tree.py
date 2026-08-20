"""Interactive execution tree visualization for OpenAmer.

Records and displays the execution history of agent calls as a tree
structure with timing and performance statistics.
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class ExecutionNode:
    """A single node in an execution tree.

    Attributes:
        id: Unique node identifier.
        parent_id: ID of the parent node, or ``None`` for the root.
        type: Node type indicating what kind of execution this represents.
            One of ``llm_call``, ``tool_call``, ``tool_result``,
            ``condition``, ``branch``.
        start_time: ISO-8601 timestamp when execution began.
        end_time: ISO-8601 timestamp when execution finished, or ``None``.
        duration_ms: Elapsed wall-clock time in milliseconds, or ``None``.
        input_summary: Short text summary of the node's input.
        output_summary: Short text summary of the node's output.
        status: One of ``pending``, ``running``, ``completed``, ``failed``.
    """

    id: str
    parent_id: Optional[str] = None
    type: str = "tool_call"  # llm_call | tool_call | tool_result | condition | branch
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    duration_ms: Optional[float] = None
    input_summary: str = ""
    output_summary: str = ""
    status: str = "pending"


# ---------------------------------------------------------------------------
# Execution tree
# ---------------------------------------------------------------------------


class ExecutionTree:
    """Tracks a hierarchy of execution nodes as a tree.

    Nodes are identified by a unique string ID (UUID by default).  The root
    node has ``parent_id=None``; all other nodes must reference an existing
    parent.
    """

    def __init__(self) -> None:
        self._nodes: dict[str, ExecutionNode] = {}
        self._root_id: Optional[str] = None

    # ---------------------------------------------------------------
    # Node management
    # ---------------------------------------------------------------

    def add_node(
        self,
        parent_id: Optional[str],
        node_type: str,
        input_summary: str = "",
        output_summary: str = "",
        node_id: Optional[str] = None,
    ) -> str:
        """Add a new execution node to the tree.

        Args:
            parent_id: ID of the parent node, or ``None`` for the root.
            node_type: One of ``llm_call``, ``tool_call``, ``tool_result``,
                ``condition``, ``branch``.
            input_summary: Short description of the input.
            output_summary: Short description of the output.
            node_id: Optional explicit ID.  Auto-generated UUID if omitted.

        Returns:
            The node ID (for use in subsequent ``add_node`` calls).

        Raises:
            ValueError: If the parent_id references a non-existent node
                (unless parent_id is ``None`` for the root).
        """
        if parent_id is not None and parent_id not in self._nodes:
            raise ValueError(
                f"Parent node '{parent_id}' does not exist"
            )
        if parent_id is None and self._root_id is not None:
            raise ValueError(
                "Tree already has a root node"
            )

        nid = node_id or uuid.uuid4().hex[:12]
        now = datetime.now(timezone.utc).isoformat()

        node = ExecutionNode(
            id=nid,
            parent_id=parent_id,
            type=node_type,
            start_time=now,
            input_summary=input_summary,
            output_summary=output_summary,
            status="running",
        )
        self._nodes[nid] = node
        if parent_id is None:
            self._root_id = nid
        return nid

    def complete_node(
        self,
        node_id: str,
        output_summary: str = "",
        status: str = "completed",
    ) -> None:
        """Mark a node as finished, setting end time and duration."""
        if node_id not in self._nodes:
            raise ValueError(f"Node '{node_id}' not found")
        node = self._nodes[node_id]
        node.end_time = datetime.now(timezone.utc).isoformat()
        node.status = status
        if output_summary:
            node.output_summary = output_summary
        # Compute duration
        if node.start_time:
            try:
                start_dt = datetime.fromisoformat(node.start_time)
                end_dt = datetime.fromisoformat(node.end_time)
                node.duration_ms = (end_dt - start_dt).total_seconds() * 1000
            except (ValueError, TypeError):
                node.duration_ms = 0.0

    # ---------------------------------------------------------------
    # Tree rendering
    # ---------------------------------------------------------------

    def print_tree(self, tree_id: Optional[str] = None) -> str:
        """Render the execution tree as an ASCII tree with timing info.

        Args:
            tree_id: Root node ID.  Defaults to the tree's root.

        Returns:
            Multi-line ASCII tree representation.
        """
        root_id = tree_id or self._root_id
        if root_id is None:
            return "(empty execution tree)"
        if root_id not in self._nodes:
            return f"(node '{root_id}' not found)"

        lines: list[str] = []
        self._render_subtree(root_id, lines, prefix="", is_last=True)
        return "\n".join(lines)

    def _render_subtree(
        self,
        node_id: str,
        lines: list[str],
        prefix: str,
        is_last: bool,
    ) -> None:
        """Recursively render a node and its children."""
        node = self._nodes[node_id]
        connector = "└── " if is_last else "├── "
        duration_str = ""
        if node.duration_ms is not None:
            duration_str = f" [{node.duration_ms:.0f}ms]"

        status_symbol = {
            "pending": "○",
            "running": "►",
            "completed": "✓",
            "failed": "✗",
        }.get(node.status, "?")

        label = (
            f"{prefix}{connector}{status_symbol} {self._type_icon(node.type)}"
            f" {node.type.upper()}"
            f"{duration_str}"
        )
        if node.input_summary:
            label += f"  ← {node.input_summary[:60]}"
        if node.output_summary and node.status == "completed":
            label += f"  → {node.output_summary[:60]}"
        lines.append(label)

        # Find children
        children = [
            nid for nid, n in self._nodes.items()
            if n.parent_id == node_id
        ]
        child_prefix = prefix + ("    " if is_last else "│   ")
        for i, child_id in enumerate(children):
            self._render_subtree(
                child_id,
                lines,
                prefix=child_prefix,
                is_last=(i == len(children) - 1),
            )

    @staticmethod
    def _type_icon(node_type: str) -> str:
        return {
            "llm_call": "🧠",
            "tool_call": "🔧",
            "tool_result": "📦",
            "condition": "◇",
            "branch": "‖",
        }.get(node_type, "?")

    # ---------------------------------------------------------------
    # Export
    # ---------------------------------------------------------------

    def export_json(self, tree_id: Optional[str] = None) -> dict[str, Any]:
        """Export the execution tree as a JSON-serializable dict.

        Args:
            tree_id: Root node ID.  Defaults to the tree's root.

        Returns:
            Dict with ``root_id``, ``nodes`` (list of node dicts), and
            ``tree`` (nested structural view).
        """
        root_id = tree_id or self._root_id
        if root_id is None:
            return {"root_id": None, "nodes": [], "tree": None}
        if root_id not in self._nodes:
            return {"root_id": root_id, "nodes": [], "tree": None}

        nodes_list = [
            asdict(self._nodes[nid])
            for nid in self._nodes
        ]
        tree_structure = self._build_nested(root_id)
        return {
            "root_id": root_id,
            "nodes": nodes_list,
            "tree": tree_structure,
        }

    def _build_nested(self, node_id: str) -> dict[str, Any]:
        """Recursively build a nested structure for JSON export."""
        node = self._nodes[node_id]
        children = [
            self._build_nested(nid)
            for nid in self._nodes
            if self._nodes[nid].parent_id == node_id
        ]
        result = asdict(node)
        result["children"] = children
        return result

    # ---------------------------------------------------------------
    # Statistics
    # ---------------------------------------------------------------

    def get_stats(self, tree_id: Optional[str] = None) -> dict[str, Any]:
        """Compute performance statistics for a subtree.

        Returns:
            Dict with ``total_nodes``, ``completed``, ``failed``,
            ``pending``, ``total_duration_ms``, ``avg_duration_ms``,
            ``by_type`` breakdown, and ``longest_node`` info.
        """
        root_id = tree_id or self._root_id
        if root_id is None or root_id not in self._nodes:
            return {
                "total_nodes": 0,
                "completed": 0,
                "failed": 0,
                "pending": 0,
                "total_duration_ms": 0.0,
                "avg_duration_ms": 0.0,
                "by_type": {},
                "longest_node": None,
            }

        # Collect all nodes in the subtree
        subtree_ids = self._collect_subtree(root_id)

        total = len(subtree_ids)
        completed = sum(1 for nid in subtree_ids if self._nodes[nid].status == "completed")
        failed = sum(1 for nid in subtree_ids if self._nodes[nid].status == "failed")
        pending = sum(1 for nid in subtree_ids if self._nodes[nid].status == "pending")

        durations = [
            self._nodes[nid].duration_ms or 0.0
            for nid in subtree_ids
            if self._nodes[nid].duration_ms is not None
        ]
        total_dur = sum(durations)
        avg_dur = total_dur / len(durations) if durations else 0.0

        by_type: dict[str, dict[str, Any]] = {}
        longest_node: Optional[dict[str, Any]] = None
        longest_dur = -1.0

        for nid in subtree_ids:
            n = self._nodes[nid]
            t = n.type
            if t not in by_type:
                by_type[t] = {"count": 0, "total_duration_ms": 0.0}
            by_type[t]["count"] += 1
            if n.duration_ms is not None:
                by_type[t]["total_duration_ms"] += n.duration_ms
                if n.duration_ms > longest_dur:
                    longest_dur = n.duration_ms
                    longest_node = {
                        "id": n.id,
                        "type": n.type,
                        "duration_ms": n.duration_ms,
                        "input_summary": n.input_summary,
                    }

        return {
            "total_nodes": total,
            "completed": completed,
            "failed": failed,
            "pending": pending,
            "total_duration_ms": round(total_dur, 2),
            "avg_duration_ms": round(avg_dur, 2),
            "by_type": by_type,
            "longest_node": longest_node,
        }

    def _collect_subtree(self, node_id: str) -> list[str]:
        """Collect all node IDs in the subtree rooted at ``node_id``."""
        result: list[str] = [node_id]
        for nid, n in self._nodes.items():
            if n.parent_id == node_id:
                result.extend(self._collect_subtree(nid))
        return result