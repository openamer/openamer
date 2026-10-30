"""Tests for the native Genesis runtime (``agent/genesis_runtime.py``).

The contract these tests pin down: every one of the 24 directives has an owner
inside the product, a gate and a probe that really runs; a probe that cannot
measure reports ``unknown`` and is never upgraded to ``satisfied``; and ``tick``
persists state + heartbeat on its own, so the loop needs no cron entry or helper
script. A status only changes when a measurement changed it.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from agent import genesis_directives, genesis_runtime
from agent import genesis_runtime as rt


def test_contracts_cover_every_directive_exactly_once():
    declared = [d.id for d in genesis_directives.GENESIS_DIRECTIVES]
    contract_ids = [c.id for c in rt.CONTRACTS]

    assert len(declared) == 24
    assert contract_ids == declared, "ids must match the constitution, in order"
    assert len(set(contract_ids)) == 24


def test_every_contract_declares_owner_gate_and_probe():
    for contract in rt.CONTRACTS:
        assert contract.integration.strip(), f"{contract.id}: no integration"
        assert contract.gate.strip(), f"{contract.id}: no gate"
        assert contract.unblocks.strip(), f"{contract.id}: no unblock action"
        assert contract.probe in rt._PROBES, f"{contract.id}: probe {contract.probe!r} missing"


def test_every_probe_runs_and_reports_a_typed_verdict():
    for name, probe in rt._PROBES.items():
        result = probe()
        assert isinstance(result, rt.Probe), f"{name}: wrong return type"
        assert result.verdict in (
            rt.SATISFIED,
            rt.PARTIAL,
            rt.BLOCKED,
            rt.UNKNOWN,
        ), f"{name}: unknown verdict {result.verdict!r}"
        assert result.detail.strip(), f"{name}: verdict without evidence"
        assert isinstance(result.values, dict), f"{name}: values must be a dict"


def test_unknown_is_never_promoted_to_implemented():
    assert rt.STATUS_BY_VERDICT[rt.UNKNOWN] == "gated"
    assert rt.STATUS_BY_VERDICT[rt.BLOCKED] == "gated"
    assert rt.STATUS_BY_VERDICT[rt.PARTIAL] == "partial"
    assert rt.STATUS_BY_VERDICT[rt.SATISFIED] == "implemented"


def test_probe_exception_becomes_unknown(monkeypatch):
    def boom():
        raise RuntimeError("hardware gone")

    monkeypatch.setitem(rt._PROBES, "quantum", boom)
    rows = {row["id"]: row for row in rt.measure()}

    row = rows["DIR-11"]
    assert row["verdict"] == rt.UNKNOWN
    assert row["status"] == "gated"
    assert "hardware gone" in row["measured"]


def test_measure_rows_carry_measurement_owner_and_gate_state():
    rows = rt.measure()
    assert len(rows) == 24

    for row in rows:
        assert row["gate_state"] in ("open", "closed")
        assert (row["gate_state"] == "open") == (row["verdict"] == rt.SATISFIED)
        assert row["measured"], f"{row['id']}: no measured detail"
        assert row["integration"], f"{row['id']}: no owner"
        assert row["mark"] in ("✓", "◐", "▨")


def test_tokenomics_probe_matches_the_genesis_identity():
    result = rt._probe_tokenomics()

    assert result.verdict == rt.SATISFIED
    assert result.values["max_supply"] == 9_000_000_000
    assert result.values["allocated"] == 9_000_000_000


def test_creator_probe_reads_the_vesting_contract_not_only_the_genesis_one():
    result = rt._probe_creator_allocation()

    assert result.values["creator"] == 900_000_000
    # The cliff/vesting lives in its own contract; a probe that only reads
    # OpenAmerGenesis.sol reports the allocation as unvested and is wrong.
    assert result.values["vesting_contracts"], "no vesting contract measured"
    assert any("Vault" in name for name in result.values["vesting_contracts"])


@pytest.fixture()
def temp_home(tmp_path, monkeypatch):
    monkeypatch.setattr(rt, "_home", lambda: tmp_path)
    return tmp_path


def test_tick_persists_state_and_heartbeat(temp_home):
    payload = rt.tick(now=1000.0)

    assert rt.state_path().exists()
    assert rt.heartbeat_path().exists()
    assert payload["summary"]["total"] == 24
    stored = json.loads(rt.state_path().read_text(encoding="utf-8"))
    assert stored["measured_at"] == 1000.0
    assert len(stored["directives"]) == 24


def test_tick_logs_only_actual_status_changes(temp_home, monkeypatch):
    monkeypatch.setitem(rt._PROBES, "quantum", lambda: rt.Probe(rt.BLOCKED, "no sdk"))
    rt.tick(now=1000.0)
    assert not rt.events_path().exists(), "first tick has nothing to compare against"

    monkeypatch.setitem(
        rt._PROBES, "quantum", lambda: rt.Probe(rt.PARTIAL, "qiskit present, no VQE")
    )
    payload = rt.tick(now=2000.0)

    assert payload["changes"] == [
        {"id": "DIR-11", "from": "gated", "to": "partial"}
    ]
    events = [json.loads(line) for line in rt.events_path().read_text(encoding="utf-8").splitlines()]
    assert events[-1]["changes"][0]["id"] == "DIR-11"


def test_tick_if_due_respects_the_interval(temp_home, monkeypatch):
    monkeypatch.setitem(rt._PROBES, "quantum", lambda: rt.Probe(rt.BLOCKED, "no sdk"))
    rt.tick(now=1000.0)

    assert rt.tick_if_due(min_interval_s=900, now=1100.0) is None, "fresh state must not tick"
    later = rt.tick_if_due(min_interval_s=900, now=1901.0)
    assert later is not None and later["measured_at"] == 1901.0


def test_tick_if_due_measures_once_when_never_measured(temp_home):
    assert rt.read_state() is None
    payload = rt.tick_if_due(now=5000.0)
    assert payload is not None
    assert rt.read_state()["measured_at"] == 5000.0


def test_render_shows_gate_state_and_owner():
    text = rt.render(rt.measure(), age_s=42)

    assert "DIR-01" in text and "DIR-24" in text
    assert "closed" in text and "open" in text
    assert "owns:" in text, "each row must name the surface that owns the directive"
    assert "24 directives" in text
    assert "42s ago" in text


def test_cli_json_reads_the_persisted_state(temp_home, capsys):
    from openamer_cli.subcommands import genesis as cli

    rt.tick(now=time.time())

    class Args:
        json = True
        tick = False
        gates = False

    assert cli._cmd_genesis(Args()) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["summary"]["total"] == 24
    assert len(payload["directives"]) == 24
    assert payload["age_seconds"] is not None


def test_cli_gates_lists_only_closed_ones(temp_home, capsys):
    from openamer_cli.subcommands import genesis as cli

    rt.tick(now=time.time())

    class Args:
        json = False
        tick = False
        gates = True

    assert cli._cmd_genesis(Args()) == 0
    out = capsys.readouterr().out
    assert "closed gate(s)" in out
    assert "then :" in out


def test_tick_proves_the_replication_artifact_each_time(temp_home, monkeypatch):
    calls = []

    def fake_selftest(*args, **kwargs):
        calls.append(kwargs)
        return {"ok": True, "files": 1, "bytes": 1}

    monkeypatch.setattr("agent.replication.selftest", fake_selftest)
    rt.tick(now=1000.0)

    assert calls, "every tick must re-prove that a sealed snapshot still restores"


def test_measure_stays_cheap():
    """A tick may not spend seconds walking trees.

    Regression: two probes used ``rglob`` over the whole home and the whole repo,
    which made ``measure()`` take **15.4 s** (measured 2026-10-30) — on the first
    gateway housekeeping pass, i.e. during app boot. The bound is generous on
    purpose (slow CI disks); it only catches a return to recursive walking.
    """
    rt.measure()  # warm the import/module caches
    started = time.monotonic()
    rt.measure()
    elapsed = time.monotonic() - started

    assert elapsed < 6.0, f"measure() took {elapsed:.1f}s — a probe is walking a tree recursively"


def test_state_written_atomically_leaves_no_tmp_file(temp_home):
    rt.tick(now=1000.0)
    leftovers = list(Path(temp_home).glob("**/*.tmp"))
    assert leftovers == [], f"atomic write left {leftovers}"
