"""Regression test: KTA's LoRA-rank experiment must report a real measurement.

Live bug 23.09.26: ``experiment_lora_rank()`` polled ``/health`` and returned
the fixed string "LoRA rank experiment: baseline recorded (r=16 live)". That
string was logged 184 times while no baseline was written anywhere — the claim
was untrue, and because the result never varied, the rotation looked healthy.

These tests pin the replacement contract:
  * no artifact           -> measurable False, names the probe to run
  * failed probe          -> measurable False, surfaces the probe's own error
  * successful probe      -> returns the artifact's numbers verbatim
  * probe resolves the SAME training dir as the reader (else writer and reader
    silently diverge when one of them runs from a repo checkout)
"""
import importlib
import json
import sys
from pathlib import Path

TRAIN = Path(__file__).resolve().parents[2] / "scripts" / "training"
sys.path.insert(0, str(TRAIN))


def _kta(tmp_path, monkeypatch):
    """Load knowledge_to_action with T pointed at a scratch training dir."""
    import knowledge_to_action as kta

    monkeypatch.setattr(kta, "T", str(tmp_path))
    return kta


def test_no_artifact_is_reported_as_unmeasured(tmp_path, monkeypatch):
    kta = _kta(tmp_path, monkeypatch)

    result = kta.experiment_lora_rank()

    assert result["measurable"] is False
    assert "no artifact" in result["result"]
    assert "kta_lora_rank_probe" in result["result"]


def test_failed_probe_surfaces_its_error(tmp_path, monkeypatch):
    kta = _kta(tmp_path, monkeypatch)
    art = tmp_path / "kta_artifacts"
    art.mkdir()
    (art / "lora_rank_result.json").write_text(
        json.dumps({"ok": False, "error": "skipped: only 1.0 GB free RAM"}),
        encoding="utf-8")

    result = kta.experiment_lora_rank()

    assert result["measurable"] is False
    assert "1.0 GB free RAM" in result["result"]


def test_successful_probe_numbers_are_passed_through(tmp_path, monkeypatch):
    kta = _kta(tmp_path, monkeypatch)
    art = tmp_path / "kta_artifacts"
    art.mkdir()
    (art / "lora_rank_result.json").write_text(json.dumps({
        "ok": True,
        "arms": [{"rank": 4, "final_loss": 4.36},
                 {"rank": 8, "final_loss": 4.21},
                 {"rank": 16, "final_loss": 4.03}],
        "result": "r=8 vs r=16: final loss 4.21 vs 4.03 (delta -0.18)",
    }), encoding="utf-8")

    result = kta.experiment_lora_rank()

    assert result["measurable"] is True
    assert "[4, 8, 16]" in result["action"]
    assert "4.03" in result["result"]
    assert Path(result["artifact"]).exists()


def test_result_is_not_a_frozen_string(tmp_path, monkeypatch):
    """The old bug: the same string for every cycle, whatever the state."""
    kta = _kta(tmp_path, monkeypatch)
    first = kta.experiment_lora_rank()

    art = tmp_path / "kta_artifacts"
    art.mkdir()
    (art / "lora_rank_result.json").write_text(
        json.dumps({"ok": True, "arms": [{"rank": 16, "final_loss": 2.5}],
                    "result": "r=16 final loss 2.5"}), encoding="utf-8")
    second = kta.experiment_lora_rank()

    assert first["result"] != second["result"]


def test_probe_writes_where_the_reader_looks(monkeypatch):
    """Writer/reader must agree on the training dir."""
    import kta_lora_rank_probe
    import knowledge_to_action as kta

    assert Path(kta_lora_rank_probe.T).resolve() == Path(kta.T).resolve()
