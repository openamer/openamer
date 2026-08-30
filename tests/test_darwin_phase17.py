"""Phase-17 tests: grid server + client (cross-machine natural selection)."""
import importlib.util
import json
import sys
import threading
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "darwin_grid_server", REPO / "scripts" / "darwin_grid_server.py")
grid = importlib.util.module_from_spec(spec)
sys.modules["darwin_grid_server"] = grid
spec.loader.exec_module(grid)


@pytest.fixture
def server(tmp_path, monkeypatch):
    monkeypatch.setattr(grid, "STORE", tmp_path / "grid-store")
    (tmp_path / "grid-store").mkdir(parents=True, exist_ok=True)
    srv = ThreadingHTTPServer(("127.0.0.1", 0), grid.Handler)
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{srv.server_address[1]}"
    yield url
    srv.shutdown()


def _post(url, body):
    req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                 method="POST",
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=5) as r:
        return json.loads(r.read())


def _get(url):
    with urllib.request.urlopen(url, timeout=5) as r:
        return json.loads(r.read())


def test_health(server):
    assert _get(f"{server}/health")["grid"] is True


def test_push_and_pull_roundtrip(server):
    genome = {"population": {"skillA": {"wins": 2, "losses": 0}},
              "pushed_at": "2026-01-01"}
    resp = _post(f"{server}/push?machine=alpha-01", genome)
    assert resp["ok"] is True and resp["skills"] == 1
    pulled = _get(f"{server}/pull?machine=alpha-01")
    assert pulled["population"]["skillA"]["wins"] == 2


def test_push_invalid_id_rejected(server):
    req = urllib.request.Request(
        f"{server}/push?machine=bad%2Fid", data=b"{}", method="POST")
    try:
        urllib.request.urlopen(req, timeout=5)
        assert False, "should have raised"
    except urllib.error.HTTPError as e:
        assert e.code == 400


def test_push_missing_population_rejected(server):
    req = urllib.request.Request(
        f"{server}/push?machine=ok-id", data=b"{}", method="POST",
        headers={"Content-Type": "application/json"})
    try:
        urllib.request.urlopen(req, timeout=5)
        assert False, "should have raised"
    except urllib.error.HTTPError as e:
        assert e.code == 400


def test_pull_unknown_machine_404(server):
    req = urllib.request.Request(f"{server}/pull?machine=ghost")
    try:
        urllib.request.urlopen(req, timeout=5)
        assert False, "should have raised"
    except urllib.error.HTTPError as e:
        assert e.code == 404


def test_list_shows_machines(server):
    _post(f"{server}/push?machine=machine-one",
          {"population": {"s": {"wins": 1}}})
    _post(f"{server}/push?machine=machine-two",
          {"population": {"s": {"wins": 2}}})
    listing = _get(f"{server}/list")
    names = [m["machine"] for m in listing["machines"]]
    assert set(names) >= {"machine-one", "machine-two"}


def test_pull_all_aggregates(server):
    _post(f"{server}/push?machine=mac-1", {"population": {"a": {"wins": 1}}})
    _post(f"{server}/push?machine=mac-2", {"population": {"b": {"wins": 1}}})
    allg = _get(f"{server}/pull-all")
    assert allg["machines"] == 2
    assert set(allg["genomes"]) == {"mac-1", "mac-2"}


def test_push_overwrites_same_machine(server):
    _post(f"{server}/push?machine=mac-1", {"population": {"old": {"wins": 1}}})
    _post(f"{server}/push?machine=mac-1", {"population": {"new": {"wins": 5}}})
    g = _get(f"{server}/pull?machine=mac-1")
    assert "new" in g["population"] and "old" not in g["population"]
