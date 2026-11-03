"""runner/eval.py prediction labelling: gold baselines must never look like agent output."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_runner_eval():
    spec = importlib.util.spec_from_file_location(
        "runner_eval_under_test", REPO_ROOT / "runner" / "eval.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def runner_eval():
    return _load_runner_eval()


TASKS = [
    {"instance_id": "sympy__sympy-1", "patch": "--- a/x\n+++ b/x\n"},
    {"instance_id": "django__django-2", "patch": ""},
]


def test_gold_baseline_requires_explicit_opt_in(runner_eval):
    """No agent_fn must raise instead of emitting gold patches under the model name."""
    with pytest.raises(ValueError, match="refusing to emit gold patches"):
        runner_eval.build_predictions(TASKS)


def test_gold_baseline_is_labelled_distinctly_from_the_model(runner_eval):
    preds = runner_eval.build_predictions(TASKS, allow_gold_baseline=True)

    assert runner_eval.GOLD_BASELINE_LABEL != runner_eval.MODEL_NAME
    assert {p["model_name_or_path"] for p in preds} == {
        runner_eval.GOLD_BASELINE_LABEL
    }
    assert all(p["model_name_or_path"] != runner_eval.MODEL_NAME for p in preds)


def test_agent_predictions_keep_the_model_label(runner_eval):
    preds = runner_eval.build_predictions(
        TASKS, agent_fn=lambda task: f"patch for {task['instance_id']}"
    )

    assert {p["model_name_or_path"] for p in preds} == {runner_eval.MODEL_NAME}
    assert preds[0]["model_patch"] == "patch for sympy__sympy-1"


def test_validation_rejects_gold_records_as_model_predictions(runner_eval, tmp_path):
    path = tmp_path / "preds.jsonl"
    preds = runner_eval.build_predictions(TASKS, allow_gold_baseline=True)
    path.write_text(
        "\n".join(json.dumps(p) for p in preds) + "\n", encoding="utf-8"
    )

    assert runner_eval.validate_predictions(path) is False
    assert runner_eval.validate_predictions(path, allow_gold_baseline=True) is True


def test_validation_accepts_agent_records(runner_eval, tmp_path):
    path = tmp_path / "preds.jsonl"
    preds = runner_eval.build_predictions(TASKS, agent_fn=lambda _task: "p")
    path.write_text(
        "\n".join(json.dumps(p) for p in preds) + "\n", encoding="utf-8"
    )

    assert runner_eval.validate_predictions(path) is True


def test_main_refuses_to_submit_a_gold_baseline(runner_eval, monkeypatch, tmp_path):
    monkeypatch.setattr(runner_eval, "REPORTS", tmp_path)
    monkeypatch.setattr(runner_eval, "load_subset", lambda n, seed=42: TASKS[:1])
    monkeypatch.setattr(
        sys, "argv", ["eval.py", "--baseline", "gold", "--submit", "--dry-run"]
    )

    with pytest.raises(SystemExit) as excinfo:
        runner_eval.main()

    assert "refusing to submit" in str(excinfo.value)


def test_main_without_agent_or_baseline_does_not_silently_emit_gold(
    runner_eval, monkeypatch, tmp_path
):
    monkeypatch.setattr(runner_eval, "REPORTS", tmp_path)
    monkeypatch.setattr(runner_eval, "load_subset", lambda n, seed=42: TASKS[:1])
    monkeypatch.setattr(sys, "argv", ["eval.py", "--dry-run"])

    with pytest.raises(SystemExit) as excinfo:
        runner_eval.main()

    assert "no agent patch generator" in str(excinfo.value)


def test_main_gold_dry_run_writes_labelled_predictions(
    runner_eval, monkeypatch, tmp_path
):
    monkeypatch.setattr(runner_eval, "REPORTS", tmp_path)
    monkeypatch.setattr(runner_eval, "load_subset", lambda n, seed=42: TASKS[:1])
    monkeypatch.setattr(
        sys, "argv",
        ["eval.py", "--baseline", "gold", "--dry-run", "--run-id", "unit-test"],
    )

    runner_eval.main()

    out = tmp_path / "swebench_preds_unit-test.jsonl"
    assert out.is_file()
    records = [
        json.loads(line) for line in out.read_text(encoding="utf-8").splitlines() if line
    ]
    assert [r["model_name_or_path"] for r in records] == [
        runner_eval.GOLD_BASELINE_LABEL
    ]
