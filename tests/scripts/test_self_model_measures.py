"""The self-model must MEASURE its own state, not recite constants.

The contract under test (invariants, not frozen values):

  * ``memory_episodes`` equals the number of lines in
    ``<OPENAMER_HOME>/memory/longterm_episodes.jsonl``
  * ``tools`` / ``tool_names`` equal the tool registry in
    ``<OPENAMER_HOME>/scripts/training/tool_server.py``
  * the rendered ``identity.md`` repeats those measured numbers

Before this contract existed, the module wrote ``"memory_episodes": 3012`` and
``"tools": 9`` as literals, so a rendered self-model could disagree with the
machine it describes. The tests drive the inputs to values that appear nowhere
in the source, so a re-hardcoded literal cannot pass by coincidence.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

MODULE = Path(__file__).resolve().parents[2] / "scripts" / "training" / "self_model.py"


def _seed(tmp_home: Path, episodes: int, tools: list[str]) -> None:
    (tmp_home / "memory").mkdir(parents=True, exist_ok=True)
    (tmp_home / "scripts" / "training").mkdir(parents=True, exist_ok=True)
    with open(tmp_home / "memory" / "longterm_episodes.jsonl", "w",
              encoding="utf-8") as fh:
        for i in range(episodes):
            fh.write('{"n": %d}\n' % i)
    body = ",\n".join('    {"name": "%s", "desc": "d"}' % t for t in tools)
    (tmp_home / "scripts" / "training" / "tool_server.py").write_text(
        "TOOLS = [\n%s\n]\n" % body, encoding="utf-8")


def _load(tmp_home: Path, monkeypatch, name: str):
    monkeypatch.setenv("OPENAMER_HOME", str(tmp_home))
    spec = importlib.util.spec_from_file_location(name, MODULE)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    # A mis-set environment must never make this test write into the real
    # install's memory store; fail loudly instead.
    assert str(mod.SELF_DIR).startswith(str(tmp_home)), (
        "self_model resolved SELF_DIR outside the temp home: %s" % mod.SELF_DIR)
    return mod


@pytest.mark.parametrize("episodes", [0, 7, 11])
def test_episode_count_follows_the_store(tmp_path, monkeypatch, episodes):
    _seed(tmp_path, episodes, ["alpha_tool"])
    mod = _load(tmp_path, monkeypatch, "self_model_episodes_%d" % episodes)
    assert mod.gather_state()["memory_episodes"] == episodes


@pytest.mark.parametrize("tools", [
    ["alpha_tool"],
    ["alpha_tool", "beta_tool", "gamma_tool"],
])
def test_tool_count_and_names_follow_the_registry(tmp_path, monkeypatch, tools):
    _seed(tmp_path, 3, tools)
    mod = _load(tmp_path, monkeypatch, "self_model_tools_%d" % len(tools))
    state = mod.gather_state()
    assert state["tools"] == len(tools)
    assert state["tool_names"] == tools


def test_rendered_identity_repeats_the_measured_numbers(tmp_path, monkeypatch):
    tools = ["alpha_tool", "beta_tool", "gamma_tool"]
    _seed(tmp_path, 7, tools)
    mod = _load(tmp_path, monkeypatch, "self_model_render")
    doc = mod.update_identity(mod.gather_state())
    assert "- 7 episodic memories" in doc
    assert "- 3 tools: " + ", ".join(tools) in doc


def test_source_does_not_restate_a_stale_prose_tool_list():
    """The doc must render the registry; a prose copy drifts the moment a tool
    is added, which is how the self-model came to claim 9 tools while the
    server exposed 10."""
    src = MODULE.read_text(encoding="utf-8")
    assert "9 tools: see, hear" not in src
