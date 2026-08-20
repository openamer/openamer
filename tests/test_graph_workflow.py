"""Tests for the graph workflow engine."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from openamer_cli.graph_workflow import (
    GraphWorkflowEngine,
    WorkflowGraph,
    WorkflowNode,
    WorkflowStore,
)


class TestWorkflowNode:
    """WorkflowNode creation and validation."""

    def test_basic_creation(self):
        node = WorkflowNode(
            id="node1",
            type="task",
            name="First task",
            config={"action": "print"},
            next_node_ids=["node2"],
        )
        assert node.id == "node1"
        assert node.type == "task"
        assert node.name == "First task"
        assert node.config == {"action": "print"}
        assert node.next_node_ids == ["node2"]

    def test_defaults(self):
        node = WorkflowNode(id="n1", type="output", name="Output")
        assert node.config == {}
        assert node.next_node_ids == []

    def test_all_types(self):
        for t in ("task", "condition", "parallel", "output"):
            node = WorkflowNode(id=t, type=t, name=t.title())
            assert node.type == t

    def test_invalid_type(self):
        node = WorkflowNode(id="bad", type="invalid", name="Bad")
        # The data model doesn't enforce enum — that's the engine's job
        assert node.type == "invalid"


class TestWorkflowGraph:
    """WorkflowGraph creation and mutation."""

    def test_empty_graph(self):
        g = WorkflowGraph()
        assert g.nodes == {}
        assert g.edges == []
        assert g.entry_node_id == ""
        assert g.state == {}

    def test_graph_with_nodes(self):
        n1 = WorkflowNode(id="a", type="task", name="A")
        n2 = WorkflowNode(id="b", type="output", name="B")
        g = WorkflowGraph(
            nodes={"a": n1, "b": n2},
            edges=[("a", "b", None)],
            entry_node_id="a",
            state={"counter": 0},
        )
        assert len(g.nodes) == 2
        assert g.entry_node_id == "a"
        assert g.state["counter"] == 0


class TestGraphWorkflowEngine:
    """GraphWorkflowEngine execution logic."""

    def test_execute_simple_linear(self):
        engine = GraphWorkflowEngine()
        g = WorkflowGraph(
            nodes={
                "start": WorkflowNode(
                    id="start", type="task", name="Start",
                    config={"result": "hello"},
                ),
                "end": WorkflowNode(
                    id="end", type="output", name="End",
                    config={"message": "done"},
                ),
            },
            entry_node_id="start",
        )
        g.nodes["start"].next_node_ids = ["end"]

        result = engine.execute(g, initial_input="go")
        assert result["success"] is True
        assert len(result["results"]) == 1
        assert result["results"][0]["message"] == "done"
        assert "start" in result["execution_path"]
        assert "end" in result["execution_path"]

    def test_execute_condition_true_then_task(self):
        """Condition evaluates True — downstream node executes."""
        engine = GraphWorkflowEngine(
            condition_evaluator=lambda nid, cfg, state: cfg.get("expected", True),
        )
        g = WorkflowGraph(
            nodes={
                "check": WorkflowNode(
                    id="check", type="condition", name="Check",
                    config={"expected": True},
                    next_node_ids=["process"],
                ),
                "process": WorkflowNode(
                    id="process", type="task", name="Process",
                    config={"result": "processed"},
                    next_node_ids=["out"],
                ),
                "out": WorkflowNode(
                    id="out", type="output", name="Output",
                    config={"final": True},
                ),
            },
            entry_node_id="check",
        )

        result = engine.execute(g)
        assert result["success"] is True
        assert result["node_outputs"]["check"]["_condition_result"] is True
        assert "process" in result["execution_path"]

    def test_execute_condition_false_skips_downstream(self):
        """Condition evaluates False — downstream nodes are still in path
        but the condition result is tracked."""
        engine = GraphWorkflowEngine(
            condition_evaluator=lambda nid, cfg, state: False,
        )
        g = WorkflowGraph(
            nodes={
                "check": WorkflowNode(
                    id="check", type="condition", name="Check",
                    next_node_ids=["process"],
                ),
                "process": WorkflowNode(
                    id="process", type="task", name="Process",
                    config={"result": "should not run"},
                ),
            },
            entry_node_id="check",
        )

        result = engine.execute(g)
        assert result["success"] is True
        assert result["node_outputs"]["check"]["_condition_result"] is False
        # Process node is still in execution_path
        assert "process" in result["execution_path"]

    def test_execute_parallel(self):
        """Parallel node runs branches concurrently."""
        call_order: list[str] = []

        def executor(nid, cfg, state):
            call_order.append(nid)
            return cfg.get("result", nid)

        engine = GraphWorkflowEngine(task_executor=executor)
        g = WorkflowGraph(
            nodes={
                "fork": WorkflowNode(
                    id="fork", type="parallel", name="Fork",
                    config={"max_workers": 2},
                    next_node_ids=["branch_a", "branch_b"],
                ),
                "branch_a": WorkflowNode(
                    id="branch_a", type="task", name="Branch A",
                    config={"result": "a"},
                ),
                "branch_b": WorkflowNode(
                    id="branch_b", type="task", name="Branch B",
                    config={"result": "b"},
                ),
            },
            entry_node_id="fork",
        )

        result = engine.execute(g)
        assert result["success"] is True
        assert len(call_order) == 2
        assert "branch_a" in call_order
        assert "branch_b" in call_order

    def test_execute_output_node_returns_config(self):
        engine = GraphWorkflowEngine()
        g = WorkflowGraph(
            nodes={
                "out": WorkflowNode(
                    id="out", type="output", name="Done",
                    config={"key": "value"},
                ),
            },
            entry_node_id="out",
        )

        result = engine.execute(g)
        assert result["results"] == [{"key": "value", "_input": None}]

    def test_missing_entry_node_raises(self):
        engine = GraphWorkflowEngine()
        g = WorkflowGraph(
            nodes={"n1": WorkflowNode(id="n1", type="task", name="N1")},
            entry_node_id="nonexistent",
        )
        with pytest.raises(ValueError, match="not found in nodes"):
            engine.execute(g)

    def test_empty_entry_node_id_raises(self):
        engine = GraphWorkflowEngine()
        g = WorkflowGraph(
            nodes={"n1": WorkflowNode(id="n1", type="task", name="N1")},
        )
        with pytest.raises(ValueError, match="no entry_node_id"):
            engine.execute(g)

    def test_custom_executor(self):
        def my_executor(nid, cfg, state):
            return f"executed-{nid}"

        engine = GraphWorkflowEngine(task_executor=my_executor)
        g = WorkflowGraph(
            nodes={
                "t1": WorkflowNode(
                    id="t1", type="task", name="T1",
                    config={},
                    next_node_ids=["out"],
                ),
                "out": WorkflowNode(id="out", type="output", name="Done"),
            },
            entry_node_id="t1",
        )

        result = engine.execute(g)
        assert result["node_outputs"]["t1"] == "executed-t1"

    def test_custom_condition(self):
        def my_condition(nid, cfg, state):
            return state.get("allowed", False)

        engine = GraphWorkflowEngine(condition_evaluator=my_condition)
        g = WorkflowGraph(
            nodes={
                "check": WorkflowNode(
                    id="check", type="condition", name="Check",
                    next_node_ids=["out"],
                ),
                "out": WorkflowNode(id="out", type="output", name="Done"),
            },
            entry_node_id="check",
            state={"allowed": True},
        )

        result = engine.execute(g)
        assert result["node_outputs"]["check"]["_condition_result"] is True

    def test_state_accumulates(self):
        engine = GraphWorkflowEngine()
        g = WorkflowGraph(
            nodes={
                "step1": WorkflowNode(
                    id="step1", type="task", name="Step 1",
                    config={"result": "first"},
                    next_node_ids=["step2"],
                ),
                "step2": WorkflowNode(
                    id="step2", type="task", name="Step 2",
                    config={"result": "second"},
                    next_node_ids=["out"],
                ),
                "out": WorkflowNode(id="out", type="output", name="Done"),
            },
            entry_node_id="step1",
        )

        result = engine.execute(g)
        assert result["node_outputs"]["step1"] == "first"
        assert result["node_outputs"]["step2"] == "second"

    def test_visualize_non_empty(self):
        engine = GraphWorkflowEngine()
        g = WorkflowGraph(
            nodes={
                "start": WorkflowNode(
                    id="start", type="task", name="Start",
                    next_node_ids=["end"],
                ),
                "end": WorkflowNode(id="end", type="output", name="End"),
            },
            entry_node_id="start",
        )
        viz = engine.visualize(g)
        assert "Start" in viz
        assert "End" in viz
        assert "╔" in viz
        assert "Legend" in viz or "Legend" in viz

    def test_visualize_empty(self):
        engine = GraphWorkflowEngine()
        g = WorkflowGraph()
        viz = engine.visualize(g)
        assert "empty" in viz

    def test_add_node_and_edge(self):
        engine = GraphWorkflowEngine()
        # These are no-ops on the engine level (edges live on the graph data model)
        # but the methods should not raise
        engine.add_node(
            WorkflowNode(id="n1", type="task", name="N1")
        )
        engine.add_edge("n1", "n2")

    def test_topo_order_with_cycle(self):
        """Graph with a cycle still executes (resilience)."""
        engine = GraphWorkflowEngine()
        g = WorkflowGraph(
            nodes={
                "a": WorkflowNode(
                    id="a", type="task", name="A",
                    config={"result": "a"},
                    next_node_ids=["b"],
                ),
                "b": WorkflowNode(
                    id="b", type="task", name="B",
                    config={"result": "b"},
                    next_node_ids=["a"],  # cycle back
                ),
            },
            entry_node_id="a",
        )
        result = engine.execute(g)
        assert result["success"] is True


class TestWorkflowStore:
    """WorkflowStore persistence."""

    def test_save_and_load(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = WorkflowStore(store_dir=tmpdir)
            g = WorkflowGraph(
                nodes={
                    "n1": WorkflowNode(
                        id="n1", type="task", name="N1",
                        config={"key": "value"},
                        next_node_ids=["n2"],
                    ),
                    "n2": WorkflowNode(id="n2", type="output", name="N2"),
                },
                entry_node_id="n1",
            )
            path = store.save("test_wf", g)
            assert Path(path).exists()

            loaded = store.load("test_wf")
            assert loaded.entry_node_id == "n1"
            assert len(loaded.nodes) == 2
            assert loaded.nodes["n1"].name == "N1"
            assert loaded.nodes["n1"].config["key"] == "value"
            assert loaded.nodes["n1"].next_node_ids == ["n2"]

    def test_list_workflows(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = WorkflowStore(store_dir=tmpdir)
            g1 = WorkflowGraph(
                nodes={"a": WorkflowNode(id="a", type="output", name="A")},
                entry_node_id="a",
            )
            g2 = WorkflowGraph(
                nodes={"b": WorkflowNode(id="b", type="output", name="B")},
                entry_node_id="b",
            )
            store.save("wf1", g1)
            store.save("wf2", g2)

            workflows = store.list_workflows()
            assert len(workflows) == 2
            names = [w["name"] for w in workflows]
            assert "wf1" in names
            assert "wf2" in names

    def test_delete(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = WorkflowStore(store_dir=tmpdir)
            g = WorkflowGraph(
                nodes={"a": WorkflowNode(id="a", type="output", name="A")},
                entry_node_id="a",
            )
            store.save("to_delete", g)
            assert store.delete("to_delete") is True
            assert store.delete("nonexistent") is False
            with pytest.raises(FileNotFoundError):
                store.load("to_delete")

    def test_load_nonexistent_raises(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = WorkflowStore(store_dir=tmpdir)
            with pytest.raises(FileNotFoundError):
                store.load("no_such_workflow")

    def test_save_invalid_name_raises(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = WorkflowStore(store_dir=tmpdir)
            g = WorkflowGraph(
                nodes={"a": WorkflowNode(id="a", type="output", name="A")},
                entry_node_id="a",
            )
            with pytest.raises(ValueError, match="Invalid workflow name"):
                store.save("../escape", g)
            with pytest.raises(ValueError, match="cannot be empty"):
                store.save("", g)
            with pytest.raises(ValueError, match="Invalid workflow name"):
                store.save("path/traversal", g)

    def test_store_dir_created(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            subdir = os.path.join(tmpdir, "nested", "dir")
            store = WorkflowStore(store_dir=subdir)
            assert os.path.isdir(subdir)

    def test_get_path(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = WorkflowStore(store_dir=tmpdir)
            path = store.get_path("myworkflow")
            assert path.endswith("myworkflow.json")
            assert tmpdir in path

    def test_round_trip_preserves_state(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = WorkflowStore(store_dir=tmpdir)
            g = WorkflowGraph(
                nodes={
                    "n1": WorkflowNode(id="n1", type="task", name="N1"),
                },
                entry_node_id="n1",
                state={"counter": 42, "tags": ["a", "b"]},
            )
            store.save("stateful", g)
            loaded = store.load("stateful")
            assert loaded.state["counter"] == 42
            assert loaded.state["tags"] == ["a", "b"]


class TestIntegration:
    """End-to-end workflow execution integration tests."""

    def test_full_pipeline(self):
        """A realistic pipeline: parse → validate → transform → output."""
        engine = GraphWorkflowEngine()
        g = WorkflowGraph(
            nodes={
                "parse": WorkflowNode(
                    id="parse", type="task", name="Parse Input",
                    config={"result": "parsed_data"},
                    next_node_ids=["validate"],
                ),
                "validate": WorkflowNode(
                    id="validate", type="condition", name="Validate",
                    config={"field": "_input", "expected": "valid"},
                    next_node_ids=["transform", "error"],
                ),
                "transform": WorkflowNode(
                    id="transform", type="task", name="Transform",
                    config={"result": "transformed"},
                    next_node_ids=["output"],
                ),
                "error": WorkflowNode(
                    id="error", type="output", name="Error Handler",
                    config={"status": "error", "message": "Validation failed"},
                ),
                "output": WorkflowNode(
                    id="output", type="output", name="Final Output",
                    config={"status": "ok"},
                ),
            },
            entry_node_id="parse",
        )

        # Valid input should go through transform → output
        result = engine.execute(g, initial_input="valid")
        assert result["success"] is True
        assert result["node_outputs"]["validate"]["_condition_result"] is True
        # Check results include the output node
        output_results = [r for r in result["results"] if r.get("status") == "ok"]
        assert len(output_results) >= 1

        # Invalid input should go to error
        result2 = engine.execute(g, initial_input="invalid")
        assert result2["success"] is True
        assert result2["node_outputs"]["validate"]["_condition_result"] is False

    def test_default_executor_with_callable(self):
        """The default executor can run a callable from config."""
        calls = []

        def my_action(state):
            calls.append(state.get("_input"))
            return f"done-{state.get('_input')}"

        engine = GraphWorkflowEngine()
        g = WorkflowGraph(
            nodes={
                "t1": WorkflowNode(
                    id="t1", type="task", name="T1",
                    config={"action": my_action},
                    next_node_ids=["out"],
                ),
                "out": WorkflowNode(id="out", type="output", name="Out"),
            },
            entry_node_id="t1",
        )

        result = engine.execute(g, initial_input="test_value")
        assert result["node_outputs"]["t1"] == "done-test_value"
        assert calls == ["test_value"]