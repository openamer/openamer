"""Regression test for scripts/benchmark.py load/save — the frozen time-series.

`benchmarks.json` stores runs under "history", but the code read `all_results["runs"]`,
so every `--cron` run crashed with `KeyError: 'runs'` before writing anything.
The capability time-series froze (4 identical entries, all Oct-04) and the
weekly benchmark cron could never land a new data point — the agent had no way
to prove it was getting better.

This test pins the schema normalization: "runs" and "history" both resolve, and
a save keeps them in sync.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

SCRIPT = (
    Path(r"C:\Users\damir\wt-bench\scripts\benchmark.py")
)


def _load(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("benchmark_mod", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["benchmark_mod"] = mod
    spec.loader.exec_module(mod)
    monkeypatch.setattr(mod, "BENCH_FILE", tmp_path / "benchmarks.json")
    return mod


def test_load_normalizes_history_to_runs(tmp_path, monkeypatch):
    """A file that only has "history" must still yield runs (no KeyError)."""
    mod = _load(tmp_path, monkeypatch)
    mod.BENCH_FILE.write_text(json.dumps({"history": [{"ts": "x", "overall_accuracy": 0.4}]}),
                              encoding="utf-8")
    data = mod.load_results()
    assert data["runs"] == data["history"]
    assert data["runs"][0]["overall_accuracy"] == 0.4


def test_load_default_when_missing(tmp_path, monkeypatch):
    mod = _load(tmp_path, monkeypatch)
    data = mod.load_results()
    assert data["runs"] == [] and "best" in data


def test_save_keeps_history_in_sync(tmp_path, monkeypatch):
    """Legacy readers use "history"; a save must keep it equal to "runs"."""
    mod = _load(tmp_path, monkeypatch)
    mod.save_results({"runs": [{"ts": "y"}], "best": {}})
    on_disk = json.loads(mod.BENCH_FILE.read_text(encoding="utf-8"))
    assert on_disk["history"] == on_disk["runs"]


def test_cron_path_appends_without_crashing(tmp_path, monkeypatch):
    """The exact crash: append a run to a history-shaped file."""
    mod = _load(tmp_path, monkeypatch)
    mod.BENCH_FILE.write_text(json.dumps({"history": [{"ts": "old"}], "best": {}}),
                              encoding="utf-8")
    all_results = mod.load_results()
    all_results["runs"].append({"ts": "new"})   # KeyError before the fix
    mod.save_results(all_results)
    assert json.loads(mod.BENCH_FILE.read_text(encoding="utf-8"))["runs"][-1]["ts"] == "new"


class _Resp:
    def __init__(self, payload):
        self._payload = payload

    def read(self):
        return json.dumps(self._payload).encode()


def _mock_model(mod, monkeypatch, content):
    monkeypatch.setattr(mod.urllib.request, "urlopen",
                        lambda *a, **k: _Resp({"choices": [{"message": {"content": content}}]}))


def test_score_gpt_handles_null_content(tmp_path, monkeypatch):
    """A reasoning model can return content=None; `.strip()` on it used to raise
    'NoneType' object has no attribute 'strip' and silently count the task wrong."""
    mod = _load(tmp_path, monkeypatch)
    _mock_model(mod, monkeypatch, None)
    r = mod.score_answer_gpt("q", "42")
    assert r["correct"] is False and r["answer"] == ""


def test_score_gpt_scores_normal_content(tmp_path, monkeypatch):
    mod = _load(tmp_path, monkeypatch)
    _mock_model(mod, monkeypatch, "The answer is 42")
    assert mod.score_answer_gpt("q", "42")["correct"] is True
