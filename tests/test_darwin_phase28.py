"""Phase-28 tests: LLM worker agents via Ollama."""
import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

REPO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "darwin_agents", REPO / "scripts" / "darwin_agents.py")
agents = importlib.util.module_from_spec(spec)
sys.modules["darwin_agents"] = agents
spec.loader.exec_module(agents)


def test_ollama_think_returns_response():
    r = agents.ollama_think("qwen3:1.7b", "Say hello", timeout=120)
    # Ollama can be slow on first load; accept empty OR skip
    if not r:
        pytest.skip("Ollama not responding (model loading)")
    assert len(r) > 0


def test_decide_action_parses_response():
    ident = {"name": "Gaia the Deep", "first_name": "Gaia",
             "personality": ["brave"], "mood": "thriving", "bio": "test"}
    state = {"stats": {"population": 10}, "gaps": []}
    with patch.object(agents, "ollama_think",
                      return_value="ACTION: PREDATE\nPREDATE: because the weak must feed the strong"):
        r = agents.decide_action(ident, state)
    assert r["action"] == "PREDATE"
    assert "PREDATE" in r["reason"] or "weak" in r["reason"]


def test_decide_action_defaults_to_rest_on_garbage():
    ident = {"name": "X", "first_name": "X", "personality": [], "mood": "ok"}
    with patch.object(agents, "ollama_think", return_value="I like cheese"):
        r = agents.decide_action(ident, {})
    assert r["action"] == "REST"


def test_system_prompt_contains_personality():
    ident = {"name": "Boris the Bold", "first_name": "Boris",
             "personality": ["brave", "curious"], "mood": "thriving",
             "bio": "A bold agent."}
    p = agents.build_system_prompt(ident, {"stats": {}, "gaps": []})
    assert "Boris the Bold" in p
    assert "brave" in p
    assert "MUTATE" in p  # available actions listed
    assert "REST" in p


def test_execute_action_realExplore(fake_world=None):
    # EXPLORE is safe: runs introspection, doesn't modify anything
    r = agents.execute_action("test", "EXPLORE")
    assert r["executed"] is True


def test_execute_rest_does_nothing():
    r = agents.execute_action("test", "REST")
    assert r["executed"] is False
    assert r["result"] == "rested"


def test_agent_log_written(tmp_path, monkeypatch):
    monkeypatch.setattr(agents, "AGENT_LOG", tmp_path / "log.json")
    ident = {"name": "Test", "first_name": "T", "personality": [],
             "mood": "ok", "bio": ""}
    with patch.object(agents, "ollama_think", return_value="ACTION: REST"):
        r = agents.run_agent_turn(ident, {"stats": {}, "gaps": []})
    log = json.loads((tmp_path / "log.json").read_text(encoding="utf-8"))
    assert len(log) == 1
    assert log[0]["action"] == "REST"
