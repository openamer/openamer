"""A stale or duplicated dashboard must be detectable, not just "responding".

Measured 2026-11-18 on this install:

* two ``dashboard-server.py`` processes (one from ``dashboard-watchdog.py``,
  one from ``service-watchdog.py``, both started 19:02:02) answered on :8899,
  because ``HTTPServer.allow_reuse_address`` makes ``SO_REUSEADDR`` let the
  second bind a port the first is already serving on Windows;
* the process that bound FIRST kept serving OLD routes, so ``/api/discovery``
  returned 404 while grep found the route in the file on disk;
* every supervisor asked only "is the port open?" and answered ✅.

These tests pin the three questions that replace it: which build answers, how
many processes answer, and does that build match the file on disk.
"""
from __future__ import annotations

import importlib.util
import pathlib
import sys
import threading
import urllib.request

import pytest

REPO = pathlib.Path(__file__).resolve().parents[2]
SCRIPTS = REPO / "scripts"
SERVER = SCRIPTS / "dashboard-server.py"


def _load(name: str, path: pathlib.Path):
    sys.path.insert(0, str(SCRIPTS))
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def ident():
    return _load("dashboard_identity", SCRIPTS / "dashboard_identity.py")


@pytest.fixture(scope="module")
def server_mod():
    return _load("dashboard_server", SERVER)


# ── reading who listens ────────────────────────────────────────────────────

NETSTAT = """
  TCP    127.0.0.1:8899         0.0.0.0:0              LISTENING       20544
  TCP    127.0.0.1:8899         0.0.0.0:0              LISTENING       25772
  TCP    127.0.0.1:8899         127.0.0.1:54530        ESTABLISHED     20544
  TCP    127.0.0.1:88990        0.0.0.0:0              LISTENING       999
  TCP    [::1]:8899             [::]:0                 LISTENING       30001
"""


def test_parse_netstat_counts_only_listeners_on_that_port(ident):
    assert ident.parse_netstat(NETSTAT, 8899) == [20544, 25772, 30001]


# Measured on this German Windows install: the state column reads ABHÖREN, not
# LISTENING. A state-word match there found zero listeners, so the watchdog
# believed the service was down while it was answering.
NETSTAT_DE = """
  TCP    127.0.0.1:8899         127.0.0.1:0            ABH\u00d6REN         4242
  TCP    127.0.0.1:8899         127.0.0.1:60512        WARTEND          0
"""


def test_parse_netstat_does_not_depend_on_the_localised_state_word(ident):
    assert ident.parse_netstat(NETSTAT_DE, 8899) == [4242]


def test_parse_netstat_ignores_established_rows_and_neighbouring_ports(ident):
    pids = ident.parse_netstat(NETSTAT, 8899)
    assert 999 not in pids          # :88990 is a different port
    assert pids.count(20544) == 1   # deduped across LISTENING/ESTABLISHED


# ── build identity ─────────────────────────────────────────────────────────

def test_script_build_is_the_md5_of_the_bytes(ident):
    import hashlib
    want = hashlib.md5(SERVER.read_bytes()).hexdigest()[:12]
    assert ident.script_build(SERVER) == want


def test_script_build_of_a_missing_file_is_unknown_not_a_crash(ident, tmp_path):
    assert ident.script_build(tmp_path / "nope.py") == "unknown"


def test_server_build_matches_the_identity_helper(ident, server_mod):
    assert server_mod.BUILD == ident.script_build(SERVER)


# ── the verdict ────────────────────────────────────────────────────────────

def test_drift_says_not_running_when_nothing_answers(ident):
    needs, reason = ident.drift(8899, SERVER, served=None, pids=[])
    assert needs and reason == "not running"


def test_drift_catches_two_processes_on_one_port(ident):
    on_disk = ident.script_build(SERVER)
    needs, reason = ident.drift(8899, SERVER,
                                served={"build": on_disk, "pid": 1}, pids=[1, 2])
    assert needs and "2 processes" in reason


def test_drift_catches_a_stale_build(ident):
    needs, reason = ident.drift(8899, SERVER,
                                served={"build": "00000000dead", "pid": 1}, pids=[1])
    assert needs and "stale build" in reason


def test_drift_catches_a_build_without_identity(ident):
    needs, reason = ident.drift(8899, SERVER, served=None, pids=[1])
    assert needs and "/api/build" in reason


def test_drift_is_quiet_when_the_disk_build_answers_once(ident):
    on_disk = ident.script_build(SERVER)
    needs, reason = ident.drift(8899, SERVER,
                                served={"build": on_disk, "pid": 1}, pids=[1])
    assert not needs and on_disk in reason


# ── the server refuses to be the second truth ──────────────────────────────

def test_a_second_server_on_the_same_port_fails_loudly(server_mod):
    first = server_mod.ExclusiveHTTPServer(("127.0.0.1", 0), server_mod.DashboardHandler)
    port = first.server_address[1]
    try:
        with pytest.raises(OSError):
            server_mod.ExclusiveHTTPServer(("127.0.0.1", port), server_mod.DashboardHandler)
    finally:
        first.server_close()


def test_api_build_reports_the_served_identity(server_mod, ident):
    srv = server_mod.ExclusiveHTTPServer(("127.0.0.1", 0), server_mod.DashboardHandler)
    port = srv.server_address[1]
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/build", timeout=5) as resp:
            import json
            body = json.loads(resp.read().decode("utf-8"))
        assert body["build"] == ident.script_build(SERVER)
        assert body["pid"] > 0
        assert "/api/discovery" in body["routes"]
    finally:
        srv.shutdown()
        srv.server_close()
