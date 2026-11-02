"""Real local subprocess/HTTP proofs; never use or start user services."""

import argparse
import json
import os
import socket
import subprocess
import sys
import threading
import time

import psutil
import pytest

from openamer_cli.supervisor import (
    InstanceLock,
    Supervisor,
    load_registry,
    probe_service,
    register_cli,
    stop_owned,
)


SERVER = """
import http.server, json, sys, time
from pathlib import Path
Path(sys.argv[2]).open("a").write("started\\n")
time.sleep(float(sys.argv[3]))
class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(json.dumps({"status": "ready"}).encode())
    def log_message(self, *args):
        pass
http.server.HTTPServer(("127.0.0.1", int(sys.argv[1])), Handler).serve_forever()
"""


@pytest.fixture
def service(tmp_path):
    script = tmp_path / "server.py"
    script.write_text(SERVER, encoding="utf-8")
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    return {
        "name": "fixture",
        "observe_only": False,
        "start": {
            "argv": [
                sys.executable,
                str(script),
                str(port),
                str(tmp_path / "starts"),
                "0.15",
            ]
        },
        "probe": {
            "kind": "http_json",
            "url": f"http://127.0.0.1:{port}/health",
            "expect": {"status": "ready"},
            "timeout_s": 0.1,
        },
        "ready_timeout_s": 5,
        "backoff_s": 30,
        "restart_budget_per_hour": 2,
    }


@pytest.fixture
def supervisor(tmp_path, monkeypatch):
    home = tmp_path / "profile"
    home.mkdir()
    monkeypatch.setenv("OPENAMER_HOME", str(home))
    obj = Supervisor()
    assert obj.home == home
    obj.init()
    yield obj
    # Clean up only fixture children; adoption tests clean their own children.
    for record in obj.state["services"].values():
        stop_owned(record.get("process", {}))
    for child in obj.children:
        try:
            child.wait(timeout=5)
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait(timeout=5)


def configure(supervisor, *services):
    supervisor.registry.write_text(
        json.dumps({"version": 1, "services": list(services)}), encoding="utf-8"
    )


def wait_for(check, timeout=8):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if check():
            return
        time.sleep(0.02)
    pytest.fail("fixture did not reach expected state within deadline")


def test_empty_default_and_init_never_overwrites(supervisor):
    assert load_registry(supervisor.registry) == []
    assert supervisor.status()["snapshot"] is None
    assert supervisor.status()["running"] is False
    original = supervisor.registry.read_bytes()
    assert supervisor.init() is False
    assert supervisor.registry.read_bytes() == original
    assert supervisor.execute(once=True)["services"] == {}
    assert supervisor.status()["message"] == "not running"


def test_status_without_state_does_not_create_home(tmp_path):
    home = tmp_path / "absent"
    status = Supervisor(home).status()
    assert status == {
        "running": False,
        "message": "not running",
        "snapshot": None,
        "note": "no state",
    }
    assert not home.exists()


def test_start_readiness_and_restart_adoption(supervisor, service, tmp_path):
    configure(supervisor, service)
    state = supervisor.execute(once=True)
    row = state["services"]["fixture"]
    assert row["state"] == "UP"
    assert row["adopted"] is False
    assert probe_service(service["probe"])[0]
    transitions = [event["to"] for event in state["events"]]
    assert transitions == ["DOWN", "STARTING", "UP"]
    assert state["events"][-1]["at"] >= state["events"][-2]["at"]
    # A fresh supervisor process/object loads identity and budget from disk.
    again = Supervisor(supervisor.home).execute(once=True)["services"]["fixture"]
    assert again["state"] == "UP"
    assert again["process"] == row["process"]
    assert len(again["attempts"]) == 1
    assert (tmp_path / "starts").read_text().splitlines() == ["started"]
    assert supervisor.status()["running"] is False
    assert "historical" in supervisor.status()["note"]


def test_external_adoption_does_not_spawn_or_claim_ownership(
    supervisor, service, tmp_path
):
    child = subprocess.Popen(
        service["start"]["argv"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    identity = {"pid": child.pid, "created": psutil.Process(child.pid).create_time()}
    try:
        wait_for(lambda: probe_service(service["probe"])[0])
        configure(supervisor, service)
        row = supervisor.execute(once=True)["services"]["fixture"]
        assert row["state"] == "UP"
        assert row["adopted"] is True
        assert "process" not in row
        assert "attempts" not in row
        assert not supervisor.children
        assert (tmp_path / "starts").read_text().splitlines() == ["started"]
    finally:
        assert stop_owned(identity)
        child.wait(timeout=5)


def test_observe_only_is_default(supervisor, service, tmp_path):
    service.pop("observe_only")
    configure(supervisor, service)
    row = supervisor.execute(once=True)["services"]["fixture"]
    assert row["state"] == "DOWN"
    assert "attempts" not in row
    assert not (tmp_path / "starts").exists()


def test_failed_start_budget_and_backoff_survive_reload(supervisor, service):
    service["start"]["argv"] = [sys.executable, "-c", "raise SystemExit(7)"]
    configure(supervisor, service)
    row = supervisor.execute(once=True)["services"]["fixture"]
    assert row["state"] == "START_FAILED"
    assert "readiness failed" in row["reason"]
    assert row["attempts"]
    restarted = Supervisor(supervisor.home)
    row = restarted.execute(once=True)["services"]["fixture"]
    assert row["state"] == "BACKOFF"
    assert len(row["attempts"]) == 1
    service["restart_budget_per_hour"] = 1
    configure(supervisor, service)
    row = restarted.execute(once=True)["services"]["fixture"]
    assert row["state"] == "BUDGET_EXHAUSTED"
    assert len(row["attempts"]) == 1


def test_timeout_is_failure_not_spawn_success(supervisor, service):
    service["start"]["argv"] = [sys.executable, "-c", "import time; time.sleep(30)"]
    service["ready_timeout_s"] = 0.2
    configure(supervisor, service)
    row = supervisor.execute(once=True)["services"]["fixture"]
    assert row["state"] == "START_FAILED"
    assert "child stopped=True" in row["reason"]
    assert supervisor.children[0].poll() is not None


def test_missing_executable_is_recorded(supervisor, service):
    service["start"]["argv"] = [str(supervisor.home / "no-such-executable")]
    configure(supervisor, service)
    row = supervisor.execute(once=True)["services"]["fixture"]
    assert row["state"] == "START_FAILED"
    assert "FileNotFoundError" in row["reason"]


def test_single_instance_lock_real_subprocess(supervisor):
    code = """
import sys
from pathlib import Path
from openamer_cli.supervisor import InstanceLock
try:
    with InstanceLock(Path(sys.argv[1])):
        pass
except RuntimeError:
    sys.exit(23)
"""
    with InstanceLock(supervisor.lock_path):
        assert supervisor.status()["running"] is True
        result = subprocess.run(
            [sys.executable, "-c", code, str(supervisor.lock_path)], timeout=20
        )
        assert result.returncode == 23
        with pytest.raises(RuntimeError, match="lock held"):
            supervisor.execute(once=True)
    result = subprocess.run(
        [sys.executable, "-c", code, str(supervisor.lock_path)], timeout=20
    )
    assert result.returncode == 0
    assert supervisor.status()["running"] is False


def test_native_loop_runs_until_stopped(supervisor, service):
    configure(supervisor, service)
    stop = threading.Event()
    errors = []

    def run():
        try:
            supervisor.execute(interval=0.1, stop=stop)
        except Exception as exc:
            errors.append(exc)

    thread = threading.Thread(target=run)
    thread.start()
    try:
        wait_for(
            lambda: supervisor.state["services"].get("fixture", {}).get("state") == "UP"
        )
        assert thread.is_alive()
        assert supervisor.status()["running"] is True
    finally:
        stop.set()
        thread.join(timeout=10)
    assert not thread.is_alive()
    assert not errors
    assert supervisor.status()["running"] is False
    # Ready child survives supervisor shutdown and remains independently healthy.
    assert probe_service(service["probe"])[0]


@pytest.mark.parametrize(
    "change",
    [
        {"observe_only": "false"},
        {"start": {"argv": "python server.py"}},
        {"start": {"argv": ["bad.cmd"]}},
        {"ready_timeout_s": float("nan")},
        {"restart_budget_per_hour": -1},
        {"probe": {"kind": "process"}},
        {"probe": {"kind": "http_status", "url": "https://example.com"}},
    ],
)
def test_validate_all_before_any_action(supervisor, service, change, tmp_path):
    invalid = dict(service, name="invalid", **change)
    configure(supervisor, service, invalid)
    with pytest.raises(ValueError):
        supervisor.execute(once=True)
    assert not (tmp_path / "starts").exists()


def test_cli_parser_and_safe_commands(supervisor, capsys):
    parser = argparse.ArgumentParser()
    register_cli(parser.add_subparsers())
    for argv in (
        ["supervisor", "status"],
        ["supervisor", "init"],
        ["supervisor", "once"],
    ):
        args = parser.parse_args(argv)
        assert args.func(args) == 0
    assert "not running" in capsys.readouterr().out
    with pytest.raises(SystemExit):
        parser.parse_args(["supervisor", "run", "--interval", "nan"])


def test_json_health_failure_is_not_http_success(supervisor, service):
    service["probe"]["expect"] = {"status": "not-ready"}
    service["ready_timeout_s"] = 2.0
    configure(supervisor, service)
    row = supervisor.execute(once=True)["services"]["fixture"]
    assert row["state"] == "START_FAILED"
    assert "JSON health assertions failed" in row["reason"]
    assert "UP" not in [event["to"] for event in supervisor.state["events"]]


def test_unhealthy_owned_process_is_not_duplicated(supervisor, service, tmp_path):
    configure(supervisor, service)
    row = supervisor.execute(once=True)["services"]["fixture"]
    assert row["state"] == "UP"
    service["probe"]["expect"] = {"status": "different"}
    configure(supervisor, service)
    row = Supervisor(supervisor.home).execute(once=True)["services"]["fixture"]
    assert row["state"] == "DEGRADED"
    assert len(row["attempts"]) == 1
    assert (tmp_path / "starts").read_text().splitlines() == ["started"]


def test_real_cli_entrypoint_uses_temporary_profile(supervisor):
    def cli(*args):
        return subprocess.run(
            [sys.executable, "-m", "openamer_cli.main", "supervisor", *args],
            env=dict(os.environ, OPENAMER_HOME=str(supervisor.home)),
            capture_output=True,
            text=True,
            timeout=40,
        )

    result = cli("status")
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["note"] == "no state"
    result = cli("init")
    assert result.returncode == 0, result.stderr
    assert "unchanged" in result.stdout
    result = cli("once")
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["services"] == {}
    result = cli("status")
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["running"] is False


def test_journal_is_valid_and_bounded(supervisor):
    for index in range(210):
        supervisor.transition("test", str(index), "test transition")
    saved = json.loads(supervisor.state_path.read_text(encoding="utf-8"))
    assert len(saved["events"]) == 200
    assert saved["events"][-1]["to"] == saved["services"]["test"]["state"]
    assert not list(supervisor.directory.glob("*.tmp"))


def test_recycled_pid_never_signalled():
    assert stop_owned({"pid": os.getpid(), "created": 0})
    assert psutil.Process(os.getpid()).is_running()
