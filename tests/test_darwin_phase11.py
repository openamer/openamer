"""Phase-11 tests: dashboard server endpoints."""
import importlib.util
import json
import sys
import urllib.request
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "darwin_dashboard", REPO / "scripts" / "darwin_dashboard.py")
dash = importlib.util.module_from_spec(spec)
sys.modules["darwin_dashboard"] = dash
spec.loader.exec_module(dash)


def test_html_contains_cards_and_script():
    assert "Darwin Live Dashboard" in dash.HTML
    assert "/api/status" in dash.HTML
    assert "/api/top" in dash.HTML


def test_handler_routes_status(tmp_path, monkeypatch):
    import darwin_engine
    # the dashboard holds a reference to the same darwin_engine module object
    # that we patch here - no reload needed (reload creates a divergent
    # instance and leaks real paths into the test)
    engine_ref = dash.darwin  # patch THIS instance, whatever loaded it
    # minimal fitness snapshot so /api/top works
    (tmp_path / "reports").mkdir(parents=True)
    (tmp_path / "reports" / "darwin-fitness.json").write_text(json.dumps({
        "updated": "2026-01-01",
        "skills": {"s1": {"fitness": 5, "usage": 2}}}), encoding="utf-8")
    monkeypatch.setattr(engine_ref, "FITNESS_FILE",
                        tmp_path / "reports" / "darwin-fitness.json")
    monkeypatch.setattr(engine_ref, "DARWIN_DIR", tmp_path / "darwin")
    monkeypatch.setattr(engine_ref, "HISTORY_FILE",
                        tmp_path / "reports" / "h.jsonl")
    monkeypatch.setattr(engine_ref, "POPULATION_FILE",
                        tmp_path / "darwin" / "population.json")
    monkeypatch.setattr(engine_ref, "HARVESTED_FILE",
                        tmp_path / "darwin" / "h.json")
    monkeypatch.setattr(engine_ref, "ARENA_FILE",
                        tmp_path / "darwin" / "arena.json")
    monkeypatch.setattr(engine_ref, "LINEAGE_FILE",
                        tmp_path / "darwin" / "lineage.json")
    monkeypatch.setattr(engine_ref, "ROLLBACK_LOG",
                        tmp_path / "darwin" / "rb.json")
    monkeypatch.setattr(engine_ref, "CRON_JOBS_FILE",
                        tmp_path / "cron" / "jobs.json")

    from http.server import ThreadingHTTPServer
    import threading
    server = ThreadingHTTPServer(("127.0.0.1", 0), dash.Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]
    try:
        with urllib.request.urlopen(
                f"http://127.0.0.1:{port}/api/status", timeout=5) as r:
            s = json.loads(r.read())
        assert "population" in s and "trend" in s
        with urllib.request.urlopen(
                f"http://127.0.0.1:{port}/api/top", timeout=5) as r:
            rows = json.loads(r.read())
        assert isinstance(rows, list) and len(rows) >= 1
        assert isinstance(rows[0], list)
        with urllib.request.urlopen(
                f"http://127.0.0.1:{port}/", timeout=5) as r:
            assert b"Darwin Live" in r.read()
    finally:
        server.shutdown()


def test_weekly_report_builds(tmp_path, monkeypatch):
    # import the weekly report module directly
    spec2 = importlib.util.spec_from_file_location(
        "darwin_weekly", REPO / "scripts" / "darwin_weekly_report.py")
    wk = importlib.util.module_from_spec(spec2)
    sys.modules["darwin_weekly"] = wk
    spec2.loader.exec_module(wk)
    report = wk.build_weekly()
    assert "Darwin Weekly" in report
