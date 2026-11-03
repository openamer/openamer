"""Contract tests for the hardened durable-execution store.

These cover the guarantees the adoption report asked for and that the previous
implementation could not make: the store follows the *active profile*, every
write is atomic, payloads are schema- and identity-validated, and a step
journal distinguishes completed work from a retryable failure and from an
ambiguous in-flight external effect.
"""

from __future__ import annotations

import json
import os

import pytest

from openamer_cli import durable_execution as de
from openamer_cli.graph_workflow import (
    GraphWorkflowEngine,
    WorkflowGraph,
    WorkflowNode,
)


# ---------------------------------------------------------------------------
# Store location and atomicity
# ---------------------------------------------------------------------------


class TestProfileSafeStore:
    def test_store_follows_active_profile(self, tmp_path, monkeypatch):
        home = tmp_path / "profiles" / "dev"
        home.mkdir(parents=True)
        monkeypatch.setenv("OPENAMER_HOME", str(home))

        de.save_checkpoint("sess", [{"role": "user", "content": "hi"}])

        assert str(de._checkpoint_root()).startswith(str(home))
        assert (home / "checkpoints" / "sess" / "0001.json").exists()
        assert de.get_checkpoint_stats()["root"] == str(home / "checkpoints")

    def test_other_profile_cannot_read_or_resume(self, tmp_path, monkeypatch):
        first = tmp_path / "profiles" / "one"
        second = tmp_path / "profiles" / "two"
        first.mkdir(parents=True)
        second.mkdir(parents=True)

        monkeypatch.setenv("OPENAMER_HOME", str(first))
        de.save_checkpoint("shared-id", [{"role": "user", "content": "one"}])

        monkeypatch.setenv("OPENAMER_HOME", str(second))
        assert de.load_latest_checkpoint("shared-id") is None
        assert de.resolve_checkpoint_for_resume("shared-id") is None

        # Even if a file is copied across profiles, the stamped identity wins.
        copied = second / "checkpoints" / "shared-id"
        copied.mkdir(parents=True)
        source = first / "checkpoints" / "shared-id" / "0001.json"
        copied.joinpath("0001.json").write_text(
            source.read_text(encoding="utf-8"), encoding="utf-8"
        )
        assert de.load_latest_checkpoint("shared-id") is None
        with pytest.raises(de.CheckpointValidationError):
            de.load_latest_checkpoint("shared-id", strict=True)


class TestAtomicWrites:
    def test_failed_rename_leaves_previous_checkpoint_intact(self, monkeypatch):
        messages = [{"role": "user", "content": "first"}]
        de.save_checkpoint("sess", messages)
        session_dir = de._checkpoint_root() / "sess"
        before = (session_dir / "0001.json").read_bytes()

        def boom(*_args, **_kwargs):
            raise OSError("simulated crash before rename")

        monkeypatch.setattr(os, "replace", boom)
        with pytest.raises(OSError):
            de.save_checkpoint("sess", [{"role": "user", "content": "second"}])

        assert (session_dir / "0001.json").read_bytes() == before
        assert sorted(p.name for p in session_dir.iterdir()) == ["0001.json"]
        assert de.load_latest_checkpoint("sess").messages[0]["content"] == "first"

    def test_corrupt_newest_file_falls_back_to_last_good_checkpoint(self):
        de.save_checkpoint("sess", [{"role": "user", "content": "first"}])
        session_dir = de._checkpoint_root() / "sess"
        # A process killed mid-write used to leave exactly this behind.
        (session_dir / "0002.json").write_text('{\n  "number": 2,\n  "', encoding="utf-8")

        restored = de.load_latest_checkpoint("sess")

        assert restored is not None, "prior checkpoint must remain resumable"
        assert restored.number == 1
        assert restored.messages[0]["content"] == "first"


class TestPayloadValidation:
    def _write(self, session_dir, number, payload):
        session_dir.mkdir(parents=True, exist_ok=True)
        (session_dir / f"{number:04d}.json").write_text(
            json.dumps(payload), encoding="utf-8"
        )

    def test_stored_checkpoint_carries_schema_and_profile(self):
        de.save_checkpoint("sess", [{"role": "user", "content": "x"}])
        payload = json.loads(
            (de._checkpoint_root() / "sess" / "0001.json").read_text(encoding="utf-8")
        )
        assert payload["schema_version"] == de.CHECKPOINT_SCHEMA_VERSION
        assert payload["kind"] == "checkpoint"
        assert payload["profile_home"]

    def test_foreign_session_id_is_rejected(self):
        session_dir = de._checkpoint_root() / "sess-a"
        self._write(session_dir, 1, {
            "kind": "checkpoint",
            "schema_version": de.CHECKPOINT_SCHEMA_VERSION,
            "number": 1,
            "session_id": "sess-b",
            "timestamp": "t",
            "messages": [],
            "tool_states": {},
            "memory_state": {},
        })
        assert de.load_latest_checkpoint("sess-a") is None
        with pytest.raises(de.CheckpointValidationError):
            de.load_latest_checkpoint("sess-a", strict=True)

    def test_future_schema_is_rejected_not_coerced(self):
        session_dir = de._checkpoint_root() / "sess-future"
        self._write(session_dir, 1, {
            "kind": "checkpoint",
            "schema_version": de.CHECKPOINT_SCHEMA_VERSION + 1,
            "number": 1,
            "session_id": "sess-future",
            "timestamp": "t",
            "messages": [],
            "tool_states": {},
            "memory_state": {},
        })
        with pytest.raises(de.CheckpointValidationError):
            de.load_latest_checkpoint("sess-future", strict=True)

    def test_malformed_payload_is_a_validation_error(self):
        session_dir = de._checkpoint_root() / "sess-bad"
        self._write(session_dir, 1, {"kind": "checkpoint", "number": 1})
        with pytest.raises(de.CheckpointValidationError):
            de.load_latest_checkpoint("sess-bad", strict=True)

    def test_path_traversal_in_session_id_is_rejected(self):
        with pytest.raises(de.CheckpointValidationError):
            de.save_checkpoint("../escape", [])


# ---------------------------------------------------------------------------
# Step journal
# ---------------------------------------------------------------------------


class TestStepJournal:
    def test_completed_step_is_not_executed_again(self):
        calls = []
        run = de.open_run("run-once")

        run.run_step("compute", lambda: calls.append("compute") or {"n": 7})
        run.run_step("compute", lambda: calls.append("again") or {"n": 8})

        assert calls == ["compute"]
        assert run.reused_steps == ["compute"]

    def test_reopened_run_reuses_persisted_result(self):
        calls = []
        de.open_run("run-reopen").run_step("compute", lambda: calls.append(1) or 5)

        second = de.open_run("run-reopen")
        assert second.run_step("compute", lambda: calls.append(2) or 6) == 5
        assert calls == [1]
        assert second.status()["completed"] == ["compute"]

    def test_failed_step_is_recorded_and_retryable(self):
        run = de.open_run("run-fail")

        with pytest.raises(RuntimeError):
            run.run_step("fragile", lambda: (_ for _ in ()).throw(RuntimeError("boom")))

        snapshot = de.open_run("run-fail").status()
        assert snapshot["failed"] == ["fragile"]
        assert snapshot["steps"][0]["retryable"] is True
        assert "boom" in snapshot["steps"][0]["error"]

        assert de.open_run("run-fail").run_step("fragile", lambda: "ok") == "ok"

    def test_non_retryable_step_refuses_silent_retry(self):
        run = de.open_run("run-hard")

        with pytest.raises(RuntimeError):
            run.run_step("irreversible", lambda: (_ for _ in ()).throw(RuntimeError("no")),
                         retryable=False)

        with pytest.raises(de.NonRetryableStepError):
            de.open_run("run-hard").run_step("irreversible", lambda: "again")

        assert de.open_run("run-hard").run_step(
            "irreversible", lambda: "forced", allow_retry_failed=True
        ) == "forced"

    def test_interrupted_external_effect_is_ambiguous_not_replayed(self):
        run = de.open_run("run-ambiguous")

        def interrupted():
            raise KeyboardInterrupt("process died mid-effect")

        with pytest.raises(KeyboardInterrupt):
            run.run_step("deploy", interrupted, effect=de.EffectClass.EXTERNAL)

        snapshot = de.open_run("run-ambiguous").status()
        assert snapshot["ambiguous"] == ["deploy"]
        assert snapshot["completed"] == []
        assert snapshot["failed"] == []

        executed = []
        with pytest.raises(de.AmbiguousExternalEffect):
            de.open_run("run-ambiguous").run_step(
                "deploy", lambda: executed.append("dup"), effect=de.EffectClass.EXTERNAL
            )
        assert executed == [], "an unknown external outcome must never be replayed"

    def test_interrupted_safe_step_is_retried(self):
        run = de.open_run("run-safe-retry")

        def interrupted():
            raise KeyboardInterrupt("killed")

        with pytest.raises(KeyboardInterrupt):
            run.run_step("copy", interrupted, effect=de.EffectClass.IDEMPOTENT)

        assert de.open_run("run-safe-retry").run_step(
            "copy", lambda: "done", effect=de.EffectClass.IDEMPOTENT
        ) == "done"
        attempts = de.open_run("run-safe-retry").status()["steps"][0]["attempts"]
        assert attempts == 2

    def test_resolve_ambiguous_completed_and_retry(self):
        run = de.open_run("run-resolve")
        with pytest.raises(KeyboardInterrupt):
            run.run_step("send", lambda: (_ for _ in ()).throw(KeyboardInterrupt()),
                         effect="external")

        reopened = de.open_run("run-resolve")
        reopened.resolve_ambiguous("send", resolution="completed", result={"sent": True})
        snapshot = de.open_run("run-resolve").status()
        assert snapshot["completed"] == ["send"]
        assert snapshot["ambiguous"] == []

        other = de.open_run("run-resolve-retry")
        with pytest.raises(KeyboardInterrupt):
            other.run_step("send", lambda: (_ for _ in ()).throw(KeyboardInterrupt()),
                           effect="external")
        de.open_run("run-resolve-retry").resolve_ambiguous("send", resolution="retry")
        assert de.open_run("run-resolve-retry").run_step(
            "send", lambda: "resent", effect="external"
        ) == "resent"

    def test_unknown_effect_label_is_treated_as_external(self):
        run = de.open_run("run-typo")
        with pytest.raises(KeyboardInterrupt):
            run.run_step("deploy", lambda: (_ for _ in ()).throw(KeyboardInterrupt()),
                         effect="externl")
        with pytest.raises(de.AmbiguousExternalEffect):
            de.open_run("run-typo").run_step("deploy", lambda: "dup", effect="externl")

    def test_second_executor_cannot_advance_the_same_run(self):
        first = de.open_run("run-shared")
        second = de.open_run("run-shared")
        first.run_step("a", lambda: 1)
        with pytest.raises(de.ConcurrentRunError):
            second.run_step("b", lambda: 2)

    def test_secrets_are_redacted_and_results_bounded(self):
        run = de.open_run("run-secret")
        run.run_step("login", lambda: {"access_token": "sk-live-xyz", "user": "damir"})

        journal = run.journal_path.read_text(encoding="utf-8")
        assert "sk-live-xyz" not in journal
        assert "[redacted]" in journal

        long_string = de.open_run("run-long")
        long_string.run_step("dump", lambda: "z" * (de._MAX_STRING_CHARS + 50))
        assert "chars omitted" in long_string.journal_path.read_text(encoding="utf-8")

        oversized = de.open_run("run-huge")
        oversized.run_step(
            "dump", lambda: {f"k{i}": "z" * 4000 for i in range(120)}
        )
        assert "_truncated" in oversized.journal_path.read_text(encoding="utf-8")

    def test_unserializable_result_does_not_break_the_run(self):
        run = de.open_run("run-object")
        marker = object()
        assert run.run_step("obj", lambda: marker) is marker
        snapshot = de.open_run("run-object").status()
        assert snapshot["completed"] == ["obj"]


# ---------------------------------------------------------------------------
# Production wiring: graph workflow engine
# ---------------------------------------------------------------------------


def _two_step_graph(effect: str = "none") -> WorkflowGraph:
    return WorkflowGraph(
        nodes={
            "a": WorkflowNode(id="a", type="task", name="A", next_node_ids=["b"]),
            "b": WorkflowNode(
                id="b", type="task", name="B",
                config={"durable_effect": effect}, next_node_ids=["out"],
            ),
            "out": WorkflowNode(id="out", type="output", name="Out"),
        },
        entry_node_id="a",
    )


class TestEngineJournal:
    def test_completed_nodes_are_restored_after_restart(self):
        calls = []

        def executor(node_id, config, state):
            calls.append(node_id)
            return {"node": node_id}

        engine = GraphWorkflowEngine(task_executor=executor)
        graph = _two_step_graph()

        first = engine.execute(graph, journal=de.open_run("run-engine"))
        assert calls == ["a", "b"]
        assert first["durable"]["executed_steps"] == ["a", "b"]

        calls.clear()
        second = engine.execute(graph, journal=de.open_run("run-engine"))
        assert calls == [], "no completed node may run again"
        assert second["durable"]["reused_steps"] == ["a", "b"]
        assert second["node_outputs"]["a"] == {"node": "a"}

    def test_engine_halts_on_ambiguous_external_node(self):
        calls = []

        def executor(node_id, config, state):
            if node_id == "b":
                raise KeyboardInterrupt("killed mid-effect")
            calls.append(node_id)
            return node_id

        graph = _two_step_graph(effect="external")
        with pytest.raises(KeyboardInterrupt):
            GraphWorkflowEngine(task_executor=executor).execute(
                graph, journal=de.open_run("run-engine-ext")
            )

        calls.clear()
        with pytest.raises(de.AmbiguousExternalEffect):
            GraphWorkflowEngine(task_executor=executor).execute(
                graph, journal=de.open_run("run-engine-ext")
            )
        assert calls == [], "upstream work must not be repeated either"

    def test_condition_nodes_are_journaled(self, monkeypatch):
        graph = WorkflowGraph(
            nodes={
                "gate": WorkflowNode(id="gate", type="condition", name="Gate",
                                     next_node_ids=["ok"]),
                "ok": WorkflowNode(id="ok", type="task", name="OK"),
            },
            entry_node_id="gate",
        )
        engine = GraphWorkflowEngine(condition_evaluator=lambda *_: True)

        engine.execute(graph, journal=de.open_run("run-cond"))
        result = engine.execute(graph, journal=de.open_run("run-cond"))

        assert set(result["durable"]["reused_steps"]) == {"gate", "ok"}

    def test_parallel_graphs_are_refused_with_a_journal(self):
        graph = WorkflowGraph(
            nodes={
                "fan": WorkflowNode(id="fan", type="parallel", name="Fan",
                                    next_node_ids=["a"]),
                "a": WorkflowNode(id="a", type="task", name="A"),
            },
            entry_node_id="fan",
        )
        with pytest.raises(ValueError, match="parallel"):
            GraphWorkflowEngine().execute(graph, journal=de.open_run("run-par"))

    def test_graph_executes_unchanged_without_a_journal(self):
        calls = []
        engine = GraphWorkflowEngine(
            task_executor=lambda nid, cfg, st: calls.append(nid) or nid
        )
        result = engine.execute(_two_step_graph())
        assert calls == ["a", "b"]
        assert "durable" not in result
