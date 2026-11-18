from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest

from gateway.readiness import collect_runtime_readiness

GB = 1024**3


def _fake_disk_usage(used_gb: int, total_gb: int = 100):
    """Stand-in for ``shutil.disk_usage`` with a chosen fill level.

    The real probe reads the host's disk, so a test that leaves it unpatched
    asserts the developer's/CI box's free space instead of the function's
    contract: on a machine above the 90% threshold the "healthy runtime" test
    went red while nothing was wrong with the code. Disk state belongs to the
    test, not to the machine running it.
    """
    used = used_gb * GB
    total = total_gb * GB
    return SimpleNamespace(total=total, used=used, free=total - used)


@pytest.fixture
def healthy_disk(monkeypatch):
    monkeypatch.setattr("gateway.readiness.shutil.disk_usage", lambda _p: _fake_disk_usage(40))


def test_collect_runtime_readiness_reports_healthy_local_runtime(
    tmp_path, monkeypatch, healthy_disk
):
    home = tmp_path / ".openamer"
    home.mkdir()
    (home / "config.yaml").write_text(
        "model:\n  provider: openrouter\n  model: test/model\n",
        encoding="utf-8",
    )
    with sqlite3.connect(home / "state.db") as conn:
        conn.execute("CREATE TABLE probe (id INTEGER PRIMARY KEY)")
    monkeypatch.setenv("OPENAMER_HOME", str(home))

    result = collect_runtime_readiness(
        configured_model="test/model",
        runtime_status={
            "gateway_state": "running",
            "platforms": {"telegram": {"state": "connected"}},
            "updated_at": "2026-07-09T00:00:00Z",
        },
        active_api_runs=2,
    )

    assert result["status"] == "ok"
    assert result["checks"]["state_db"]["status"] == "ok"
    assert result["checks"]["config"]["status"] == "ok"
    assert result["checks"]["model"]["status"] == "ok"
    assert result["checks"]["gateway"]["status"] == "ok"
    assert result["checks"]["background_queues"]["active_api_runs"] == 2
    assert result["checks"]["disk"]["status"] == "ok"


def test_collect_runtime_readiness_degrades_when_disk_is_nearly_full(
    tmp_path, monkeypatch
):
    """A full disk is a real readiness signal, not host noise.

    Pinned here so the probe keeps degrading a nearly-full disk even though the
    healthy-path test above now patches the fill level.
    """
    monkeypatch.setattr("gateway.readiness.shutil.disk_usage", lambda _p: _fake_disk_usage(95))
    home = tmp_path / ".openamer"
    home.mkdir()
    (home / "config.yaml").write_text(
        "model:\n  provider: openrouter\n  model: test/model\n",
        encoding="utf-8",
    )
    with sqlite3.connect(home / "state.db") as conn:
        conn.execute("CREATE TABLE probe (id INTEGER PRIMARY KEY)")
    monkeypatch.setenv("OPENAMER_HOME", str(home))

    result = collect_runtime_readiness(
        configured_model="test/model",
        runtime_status={"gateway_state": "running", "platforms": {}},
    )

    assert result["status"] == "degraded"
    assert result["checks"]["disk"]["status"] == "degraded"
    assert result["checks"]["disk"]["used_percent"] == 95.0
    assert result["checks"]["gateway"]["status"] == "ok"


def test_collect_runtime_readiness_degrades_on_invalid_config_and_stopped_gateway(
    tmp_path, monkeypatch
):
    home = tmp_path / ".openamer"
    home.mkdir()
    (home / "config.yaml").write_text("model: [unterminated", encoding="utf-8")
    monkeypatch.setenv("OPENAMER_HOME", str(home))

    result = collect_runtime_readiness(
        configured_model="",
        runtime_status={"gateway_state": "stopped", "platforms": {}},
    )

    assert result["status"] == "degraded"
    assert result["checks"]["config"]["status"] == "degraded"
    assert result["checks"]["model"]["status"] == "degraded"
    assert result["checks"]["gateway"]["status"] == "degraded"
    # Readiness is diagnostic data, not an exception or a destructive repair.
    assert (home / "config.yaml").read_text(encoding="utf-8") == "model: [unterminated"


def test_collect_runtime_readiness_marks_corrupt_state_db_degraded(tmp_path, monkeypatch):
    home = tmp_path / ".openamer"
    home.mkdir()
    (home / "config.yaml").write_text("{}\n", encoding="utf-8")
    (home / "state.db").write_bytes(b"not sqlite")
    monkeypatch.setenv("OPENAMER_HOME", str(home))

    result = collect_runtime_readiness(configured_model="configured-model", runtime_status={})

    assert result["status"] == "degraded"
    assert result["checks"]["state_db"]["status"] == "degraded"
    assert "detail" in result["checks"]["state_db"]


def test_collect_runtime_readiness_never_exposes_config_values(tmp_path, monkeypatch):
    home = tmp_path / ".openamer"
    home.mkdir()
    secret = "do-not-return-this-value"
    (home / "config.yaml").write_text(
        f"model:\n  provider: openrouter\nprivate_value: {secret}\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("OPENAMER_HOME", str(home))

    result = collect_runtime_readiness(configured_model="model", runtime_status={})

    assert secret not in json.dumps(result)
    assert str(home) not in json.dumps(result)
    assert result["checks"]["config"]["status"] == "ok"


def test_collect_runtime_readiness_uses_active_profile_home(tmp_path, monkeypatch):
    profile_home = tmp_path / "profiles" / "coder"
    profile_home.mkdir(parents=True)
    (profile_home / "config.yaml").write_text("{}\n", encoding="utf-8")
    monkeypatch.setenv("OPENAMER_HOME", str(profile_home))

    result = collect_runtime_readiness(configured_model="model", runtime_status={})

    assert result["checks"]["config"]["status"] == "ok"
    assert not (tmp_path / ".openamer" / "state.db").exists()
    assert os.environ["OPENAMER_HOME"] == str(profile_home)
