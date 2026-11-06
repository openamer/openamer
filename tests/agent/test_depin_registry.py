"""DIR-19: DePIN registry — registration, liveness, deterministic routing."""

from __future__ import annotations

import json

import pytest

from agent.depin_registry import (
    DEFAULT_STALE_AFTER_S,
    NodeCapability,
    NodeRegistry,
    distribute_rewards,
    powu_weight,
)


def _node(node_id: str, **kw) -> NodeCapability:
    kw.setdefault("backends", ["cuda"])
    kw.setdefault("vram_gb", 24.0)
    kw.setdefault("benchmark_score", 100.0)
    return NodeCapability(node_id=node_id, **kw)


def test_register_then_live(tmp_path) -> None:
    reg = NodeRegistry(tmp_path / "nodes.json")
    reg.register(_node("gpu-a"), now=1000.0)
    live = reg.live_nodes(now=1001.0)
    assert [r.capability.node_id for r in live] == ["gpu-a"]


def test_registry_survives_a_reload(tmp_path) -> None:
    path = tmp_path / "nodes.json"
    reg = NodeRegistry(path)
    reg.register(_node("gpu-a", vram_gb=12.0), now=1000.0)
    again = NodeRegistry(path)
    assert [r.capability.node_id for r in again.nodes()] == ["gpu-a"]
    assert again.nodes()[0].capability.vram_gb == 12.0


def test_reregister_keeps_the_original_since_time(tmp_path) -> None:
    reg = NodeRegistry(tmp_path / "nodes.json")
    reg.register(_node("gpu-a"), now=1000.0)
    reg.register(_node("gpu-a", benchmark_score=150.0), now=2000.0)
    only = reg.nodes()[0]
    assert only.registered_at == 1000.0  # "since", not "last touched"
    assert only.last_seen == 2000.0
    assert only.capability.benchmark_score == 150.0


def test_stale_node_is_not_live_but_is_kept(tmp_path) -> None:
    reg = NodeRegistry(tmp_path / "nodes.json", stale_after_s=10.0)
    reg.register(_node("gpu-a"), now=1000.0)
    assert reg.live_nodes(now=1005.0)
    assert not reg.live_nodes(now=1000.0 + 11.0)
    assert [r.capability.node_id for r in reg.stale_nodes(now=1011.0)] == ["gpu-a"]
    assert len(reg.nodes()) == 1  # stale is a status, not a deletion


def test_heartbeat_refreshes_and_unknown_node_returns_false(tmp_path) -> None:
    reg = NodeRegistry(tmp_path / "nodes.json", stale_after_s=10.0)
    reg.register(_node("gpu-a"), now=1000.0)
    assert reg.heartbeat("gpu-a", now=1020.0) is True
    assert reg.live_nodes(now=1025.0)
    assert reg.heartbeat("never-registered", now=1025.0) is False


def test_select_prefers_score_and_breaks_ties_on_id(tmp_path) -> None:
    reg = NodeRegistry(tmp_path / "nodes.json")
    reg.register(_node("zzz", benchmark_score=200.0), now=1000.0)
    reg.register(_node("aaa", benchmark_score=200.0), now=1000.0)
    reg.register(_node("slow", benchmark_score=10.0), now=1000.0)
    picked = reg.select(now=1001.0)
    assert picked.capability.node_id == "aaa"  # deterministic, not dict order


def test_select_filters_on_backend_and_vram(tmp_path) -> None:
    reg = NodeRegistry(tmp_path / "nodes.json")
    reg.register(_node("small", vram_gb=8.0), now=1000.0)
    reg.register(_node("big", vram_gb=48.0), now=1000.0)
    reg.register(_node("mac", backends=["metal"], vram_gb=64.0), now=1000.0)
    assert reg.select(backend="cuda", min_vram_gb=24.0, now=1001.0).capability.node_id == "big"
    assert reg.select(backend="metal", now=1001.0).capability.node_id == "mac"
    assert reg.select(backend="rocm", now=1001.0) is None


def test_select_returns_none_when_every_node_is_stale(tmp_path) -> None:
    reg = NodeRegistry(tmp_path / "nodes.json", stale_after_s=5.0)
    reg.register(_node("gpu-a"), now=1000.0)
    assert reg.select(now=1000.0 + DEFAULT_STALE_AFTER_S) is None


def test_summary_counts_live_and_stale(tmp_path) -> None:
    reg = NodeRegistry(tmp_path / "nodes.json", stale_after_s=10.0)
    reg.register(_node("a", vram_gb=24.0), now=1000.0)
    reg.register(_node("b", vram_gb=8.0), now=1000.0)
    reg.heartbeat("b", now=1015.0)
    s = reg.summary(now=1016.0)
    assert s["total"] == 2 and s["live"] == 1 and s["stale"] == 1
    assert s["live_vram_gb"] == 8.0
    assert s["backends"] == ["cuda"]


def test_deregister_removes_the_node(tmp_path) -> None:
    reg = NodeRegistry(tmp_path / "nodes.json")
    reg.register(_node("gpu-a"), now=1000.0)
    assert reg.deregister("gpu-a") is True
    assert reg.deregister("gpu-a") is False
    assert reg.nodes() == []


def test_corrupt_registry_reads_as_empty_instead_of_raising(tmp_path) -> None:
    path = tmp_path / "nodes.json"
    path.write_text("{not json", encoding="utf-8")
    reg = NodeRegistry(path)  # must not raise
    assert reg.nodes() == []


def test_save_is_atomic_no_temp_files_left(tmp_path) -> None:
    path = tmp_path / "nodes.json"
    reg = NodeRegistry(path)
    for i in range(5):
        reg.register(_node(f"gpu-{i}"), now=1000.0 + i)
    leftovers = [p.name for p in tmp_path.iterdir() if p.name.startswith(".depin-")]
    assert leftovers == []
    assert len(json.loads(path.read_text(encoding="utf-8"))["nodes"]) == 5


@pytest.mark.parametrize("bad", ["", "   "])
def test_blank_node_id_is_rejected(bad: str) -> None:
    with pytest.raises(ValueError):
        NodeCapability(node_id=bad)


def test_unknown_backend_is_rejected() -> None:
    with pytest.raises(ValueError, match="unknown backend"):
        NodeCapability(node_id="x", backends=["vulkan"])


def test_negative_vram_is_rejected() -> None:
    with pytest.raises(ValueError):
        NodeCapability(node_id="x", vram_gb=-1)


# ── PoUW accounting (DIR-20/23) ──────────────────────────────────────────────


def test_powu_weight_is_the_product_of_its_inputs() -> None:
    assert powu_weight(100.0, 1.0, 1.0) == 100.0
    assert powu_weight(100.0, 0.5, 0.5) == 25.0


def test_unverified_work_earns_nothing() -> None:
    """Anti-spoofing: no cross-node verification means no reward."""
    assert powu_weight(1000.0, 1.0, 0.0) == 0.0


@pytest.mark.parametrize(
    "kwargs",
    [
        {"benchmark_score": -1.0},
        {"uptime_fraction": -0.1},
        {"uptime_fraction": 1.5},
        {"verified_share": -0.1},
        {"verified_share": 2.0},
    ],
)
def test_powu_weight_rejects_out_of_range_inputs(kwargs) -> None:
    base = {"benchmark_score": 1.0, "uptime_fraction": 1.0, "verified_share": 1.0}
    base.update(kwargs)
    with pytest.raises(ValueError):
        powu_weight(**base)


def test_rewards_are_proportional_and_sum_to_the_pot() -> None:
    payouts = distribute_rewards([("a", 3.0), ("b", 1.0)], 400.0)
    assert payouts["a"] == 300.0
    assert payouts["b"] == 100.0
    assert sum(payouts.values()) == pytest.approx(400.0)


def test_zero_weight_or_zero_pot_pays_nobody() -> None:
    assert distribute_rewards([("a", 0.0)], 100.0) == {"a": 0.0}
    assert distribute_rewards([("a", 1.0)], 0.0) == {"a": 0.0}
