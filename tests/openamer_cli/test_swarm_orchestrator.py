"""Tests for openamer_cli.swarm_orchestrator — Swarm orchestration engine.

Exercises ``SwarmConfig``, ``SwarmResult``, all three swarm strategies
(fan-out, hierarchical, debate), and ``SwarmStore`` persistence.

All tests are self-contained (no network, no real agent calls).
"""

from __future__ import annotations

import pytest

from openamer_cli.swarm_orchestrator import (
    SwarmConfig,
    SwarmResult,
    SwarmStore,
    _estimate_confidence,
    run_swarm_debate,
    run_swarm_hierarchical,
    run_swarm_parallel,
)


# ---------------------------------------------------------------------------
# SwarmConfig
# ---------------------------------------------------------------------------


class TestSwarmConfig:
    def test_defaults(self):
        cfg = SwarmConfig(name="test")
        assert cfg.name == "test"
        assert cfg.max_agents == 3
        assert cfg.strategy == "fan-out"
        assert cfg.timeout == 120

    def test_custom(self):
        cfg = SwarmConfig(
            name="deep-research",
            max_agents=5,
            strategy="hierarchical",
            timeout=300,
        )
        assert cfg.max_agents == 5
        assert cfg.strategy == "hierarchical"


# ---------------------------------------------------------------------------
# SwarmResult
# ---------------------------------------------------------------------------


class TestSwarmResult:
    def test_defaults(self):
        r = SwarmResult(agent_name="agent-1", result="ok")
        assert r.confidence == 0.0
        assert r.duration_ms == 0

    def test_custom(self):
        r = SwarmResult(
            agent_name="agent-1",
            result="analysis complete",
            confidence=0.85,
            duration_ms=1200,
        )
        assert r.confidence == 0.85
        assert r.duration_ms == 1200


# ---------------------------------------------------------------------------
# _estimate_confidence
# ---------------------------------------------------------------------------


class TestEstimateConfidence:
    def test_empty_returns_low(self):
        assert _estimate_confidence("") == 0.3

    def test_certainty_boosts(self):
        text = "I recommend this approach. The key finding is proven. Best practice."
        score = _estimate_confidence(text)
        assert 0.5 < score <= 1.0

    def test_hedging_lowers(self):
        text = "Maybe we could possibly try this. It might work."
        score = _estimate_confidence(text)
        assert score <= 0.6


# ---------------------------------------------------------------------------
# run_swarm_parallel — fan-out strategy
# ---------------------------------------------------------------------------


class TestRunSwarmParallel:
    def test_requires_agents(self):
        cfg = SwarmConfig(name="test", max_agents=3)
        with pytest.raises(ValueError, match="At least one agent"):
            run_swarm_parallel("task", [], cfg)

    def test_runs_agents(self):
        cfg = SwarmConfig(name="test", max_agents=4)
        agents = ["researcher", "analyst", "writer"]
        results = run_swarm_parallel("Test task", agents, cfg)
        assert len(results) == 3
        for r in results:
            assert r.agent_name in agents
            assert len(r.result) > 0
            assert 0.0 <= r.confidence <= 1.0

    def test_respects_max_agents(self):
        cfg = SwarmConfig(name="test", max_agents=2)
        agents = ["a1", "a2", "a3", "a4"]
        results = run_swarm_parallel("task", agents, cfg)
        assert len(results) == 2


# ---------------------------------------------------------------------------
# run_swarm_hierarchical
# ---------------------------------------------------------------------------


class TestRunSwarmHierarchical:
    def test_requires_min_agents(self):
        cfg = SwarmConfig(name="test", max_agents=1)
        with pytest.raises(ValueError, match="Hierarchical strategy requires"):
            run_swarm_hierarchical("task", cfg)

    def test_returns_result(self):
        cfg = SwarmConfig(name="test", max_agents=3, strategy="hierarchical")
        result = run_swarm_hierarchical("Research AI safety", cfg)
        assert isinstance(result, SwarmResult)
        assert result.agent_name == "hierarchy"
        assert len(result.result) > 0
        assert result.duration_ms > 0
        assert 0.0 <= result.confidence <= 1.0


# ---------------------------------------------------------------------------
# run_swarm_debate
# ---------------------------------------------------------------------------


class TestRunSwarmDebate:
    def test_requires_min_agents(self):
        with pytest.raises(ValueError, match="Debate requires"):
            run_swarm_debate("question", ["a1"], rounds=2)

    def test_requires_rounds(self):
        with pytest.raises(ValueError, match="Debate rounds"):
            run_swarm_debate("question", ["a1", "a2"], rounds=0)

    def test_returns_consensus(self):
        result = run_swarm_debate(
            "Is AI alignment solved?",
            ["optimist", "skeptic"],
            rounds=2,
        )
        assert isinstance(result, SwarmResult)
        assert result.agent_name == "debate"
        assert "DEBATE CONSENSUS" in result.result
        assert result.duration_ms > 0
        assert 0.0 <= result.confidence <= 1.0


# ---------------------------------------------------------------------------
# SwarmStore
# ---------------------------------------------------------------------------


class TestSwarmStore:
    def test_save_and_load(self, monkeypatch, tmp_path):
        store_dir = tmp_path / "swarm_store"
        store_dir.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(
            "openamer_cli.swarm_orchestrator._swarm_store_dir",
            lambda: store_dir,
        )
        store = SwarmStore()
        cfg = SwarmConfig(name="test-cfg", max_agents=4, strategy="debate", timeout=60)
        store.save(cfg)

        loaded = store.load("test-cfg")
        assert loaded is not None
        assert loaded.name == "test-cfg"
        assert loaded.max_agents == 4
        assert loaded.strategy == "debate"

    def test_load_missing(self, monkeypatch, tmp_path):
        store_dir = tmp_path / "swarm_store"
        store_dir.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(
            "openamer_cli.swarm_orchestrator._swarm_store_dir",
            lambda: store_dir,
        )
        store = SwarmStore()
        assert store.load("nobody") is None

    def test_list_all(self, monkeypatch, tmp_path):
        store_dir = tmp_path / "swarm_store"
        store_dir.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(
            "openamer_cli.swarm_orchestrator._swarm_store_dir",
            lambda: store_dir,
        )
        store = SwarmStore()
        store.save(SwarmConfig(name="a", max_agents=2))
        store.save(SwarmConfig(name="b", max_agents=3))
        all_cfgs = store.list_all()
        names = [c.name for c in all_cfgs]
        assert "a" in names
        assert "b" in names

    def test_delete(self, monkeypatch, tmp_path):
        store_dir = tmp_path / "swarm_store"
        store_dir.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(
            "openamer_cli.swarm_orchestrator._swarm_store_dir",
            lambda: store_dir,
        )
        store = SwarmStore()
        store.save(SwarmConfig(name="del-me", max_agents=2))
        assert store.delete("del-me") is True
        assert store.load("del-me") is None
        assert store.delete("del-me") is False