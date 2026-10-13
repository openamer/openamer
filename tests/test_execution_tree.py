"""Tests for the execution tree visualization."""

from __future__ import annotations

import pytest

from openamer_cli.execution_tree import ExecutionNode, ExecutionTree


class TestExecutionNode:
    """ExecutionNode creation and defaults."""

    def test_basic_creation(self):
        node = ExecutionNode(
            id="n1",
            parent_id="root",
            type="tool_call",
            input_summary="call foo()",
            output_summary="result 42",
            status="completed",
        )
        assert node.id == "n1"
        assert node.parent_id == "root"
        assert node.type == "tool_call"
        assert node.input_summary == "call foo()"
        assert node.output_summary == "result 42"
        assert node.status == "completed"

    def test_defaults(self):
        node = ExecutionNode(id="n1")
        assert node.parent_id is None
        assert node.type == "tool_call"
        assert node.start_time is None
        assert node.end_time is None
        assert node.duration_ms is None
        assert node.input_summary == ""
        assert node.output_summary == ""
        assert node.status == "pending"


class TestExecutionTree:
    """ExecutionTree node management and rendering."""

    def test_add_root_node(self):
        tree = ExecutionTree()
        nid = tree.add_node(None, "llm_call", input_summary="Hello")
        assert nid is not None
        assert isinstance(nid, str)
        assert len(nid) > 0

    def test_add_child_node(self):
        tree = ExecutionTree()
        root_id = tree.add_node(None, "llm_call")
        child_id = tree.add_node(root_id, "tool_call", input_summary="search")
        assert child_id is not None
        assert child_id != root_id

    def test_add_child_to_nonexistent_parent(self):
        tree = ExecutionTree()
        with pytest.raises(ValueError, match="Parent node 'bad' does not exist"):
            tree.add_node("bad", "tool_call")

    def test_second_root_raises(self):
        tree = ExecutionTree()
        tree.add_node(None, "llm_call")
        with pytest.raises(ValueError, match="already has a root"):
            tree.add_node(None, "llm_call")

    def test_custom_node_id(self):
        tree = ExecutionTree()
        nid = tree.add_node(None, "tool_call", node_id="my-custom-id")
        assert nid == "my-custom-id"

    def test_complete_node(self):
        tree = ExecutionTree()
        nid = tree.add_node(None, "tool_call")
        tree.complete_node(nid, output_summary="done", status="completed")
        node = tree._nodes[nid]
        assert node.status == "completed"
        assert node.output_summary == "done"
        assert node.end_time is not None
        assert node.duration_ms is not None
        assert node.duration_ms >= 0

    def test_complete_nonexistent_node(self):
        tree = ExecutionTree()
        with pytest.raises(ValueError, match="Node 'bad' not found"):
            tree.complete_node("bad")

    def test_print_empty_tree(self):
        tree = ExecutionTree()
        output = tree.print_tree()
        assert "empty" in output

    def test_print_tree_basic(self):
        tree = ExecutionTree()
        root = tree.add_node(None, "llm_call", input_summary="query")
        child = tree.add_node(root, "tool_call", input_summary="search web")
        tree.complete_node(child, "results")
        tree.complete_node(root, "answer")

        output = tree.print_tree()
        assert "LLM_CALL" in output or "llm_call" in output
        assert "TOOL_CALL" in output or "tool_call" in output
        assert "query" in output or "search" in output

    def test_print_tree_specific_id(self):
        tree = ExecutionTree()
        root = tree.add_node(None, "llm_call")
        tree.add_node(root, "tool_call")
        output = tree.print_tree(tree_id=root)
        assert "LLM_CALL" in output

    def test_print_tree_missing_id(self):
        tree = ExecutionTree()
        output = tree.print_tree(tree_id="nonexistent")
        assert "not found" in output

    def test_export_json_empty(self):
        tree = ExecutionTree()
        exported = tree.export_json()
        assert exported["root_id"] is None
        assert exported["nodes"] == []
        assert exported["tree"] is None

    def test_export_json_basic(self):
        tree = ExecutionTree()
        root = tree.add_node(None, "llm_call", input_summary="hi")
        child = tree.add_node(root, "tool_call", input_summary="fetch")
        tree.complete_node(child, "data")
        tree.complete_node(root, "response")

        exported = tree.export_json()
        assert exported["root_id"] == root
        assert len(exported["nodes"]) == 2
        assert exported["tree"]["id"] == root
        assert len(exported["tree"]["children"]) == 1

    def test_export_specific_id(self):
        tree = ExecutionTree()
        root = tree.add_node(None, "llm_call")
        exported = tree.export_json(tree_id=root)
        assert exported["root_id"] == root

    def test_export_missing_id(self):
        tree = ExecutionTree()
        exported = tree.export_json(tree_id="bad")
        assert exported["root_id"] == "bad"
        assert exported["tree"] is None

    def test_get_stats_empty(self):
        tree = ExecutionTree()
        stats = tree.get_stats()
        assert stats["total_nodes"] == 0

    def test_get_stats_basic(self):
        tree = ExecutionTree()
        root = tree.add_node(None, "llm_call", input_summary="query")
        child1 = tree.add_node(root, "tool_call", input_summary="search")
        child2 = tree.add_node(root, "tool_call", input_summary="read")
        tree.complete_node(child1, "data1")
        tree.complete_node(child2, "data2")
        tree.complete_node(root, "answer")

        stats = tree.get_stats()
        assert stats["total_nodes"] == 3
        assert stats["completed"] == 3
        assert stats["failed"] == 0
        assert stats["pending"] == 0
        assert stats["total_duration_ms"] >= 0
        assert stats["avg_duration_ms"] >= 0
        assert "llm_call" in stats["by_type"]
        assert stats["by_type"]["tool_call"]["count"] == 2

    def test_get_stats_with_failed(self):
        tree = ExecutionTree()
        root = tree.add_node(None, "llm_call")
        child = tree.add_node(root, "tool_call")
        tree.complete_node(child, "error", status="failed")
        tree.complete_node(root, "done")

        stats = tree.get_stats()
        assert stats["completed"] == 1
        assert stats["failed"] == 1

    def test_get_stats_longest_node(self):
        tree = ExecutionTree()
        root = tree.add_node(None, "llm_call", input_summary="slow")
        tree.complete_node(root, "result")
        stats = tree.get_stats()
        assert stats["longest_node"] is not None
        assert stats["longest_node"]["type"] == "llm_call"

    def test_get_stats_specific_id(self):
        tree = ExecutionTree()
        root = tree.add_node(None, "llm_call")
        sub = tree.add_node(root, "branch")
        stats = tree.get_stats(tree_id=sub)
        assert stats["total_nodes"] == 1

    def test_get_stats_missing_id(self):
        tree = ExecutionTree()
        stats = tree.get_stats(tree_id="bad")
        assert stats["total_nodes"] == 0

    def test_multi_level_tree(self):
        """Build a 3-level tree and verify all nodes appear."""
        tree = ExecutionTree()
        r = tree.add_node(None, "llm_call", "prompt")
        c1 = tree.add_node(r, "tool_call", "search")
        c1a = tree.add_node(c1, "tool_result", "raw data")
        c2 = tree.add_node(r, "condition", "check result")
        c2a = tree.add_node(c2, "branch", "if valid")

        tree.complete_node(c1a, "parsed")
        tree.complete_node(c1, "search done")
        tree.complete_node(c2a, "branch done")
        tree.complete_node(c2, "true")
        tree.complete_node(r, "final answer")

        output = tree.print_tree()
        assert "LLM_CALL" in output
        assert "TOOL_CALL" in output
        assert "TOOL_RESULT" in output
        assert "CONDITION" in output
        assert "BRANCH" in output

        exported = tree.export_json()
        assert len(exported["nodes"]) == 5

        stats = tree.get_stats()
        assert stats["total_nodes"] == 5
        assert stats["completed"] == 5

    def test_node_types(self):
        """Verify all five node types render correctly."""
        tree = ExecutionTree()
        r = tree.add_node(None, "llm_call", "think")
        t1 = tree.add_node(r, "tool_call", "action")
        t2 = tree.add_node(r, "tool_result", "result")
        c1 = tree.add_node(r, "condition", "branch?")
        b1 = tree.add_node(r, "branch", "fork")

        tree.complete_node(t1)
        tree.complete_node(t2)
        tree.complete_node(c1)
        tree.complete_node(b1)
        tree.complete_node(r)

        output = tree.print_tree()
        for label in ["LLM_CALL", "TOOL_CALL", "TOOL_RESULT", "CONDITION", "BRANCH"]:
            assert label in output

    def test_status_symbols(self):
        """Different statuses show different symbols."""
        tree = ExecutionTree()
        r = tree.add_node(None, "llm_call")
        # Leave running as-is (status='running')
        output = tree.print_tree()
        assert "►" in output or "○" in output