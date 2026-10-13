"""Tests für openamer_cli.tracing — Tracing & Debugging Dashboard.

Mindestens 18 Tests (deutlich über der geforderten Mindestanzahl von 8).
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
import time
from pathlib import Path

import pytest

from openamer_cli.tracing import (
    TraceEntry,
    TraceStore,
    generate_html_dashboard,
    start_dashboard_server,
    build_tracing_parser,
    cmd_tracing_export,
)


# ── Fixtures ────────────────────────────────────────────────────────────


@pytest.fixture
def db_path() -> Path:
    """Liefert einen temporären DB-Pfad."""
    with tempfile.TemporaryDirectory() as tmp:
        yield Path(tmp) / "test_tracing.db"


@pytest.fixture
def store(db_path: Path) -> TraceStore:
    """Liefert einen TraceStore mit temporärer DB + cleanup."""
    s = TraceStore(db_path=db_path)
    yield s
    s.close()


@pytest.fixture
def sample_entries(store: TraceStore) -> TraceStore:
    """Befüllt den Store mit Beispiel-Daten."""
    entries = [
        TraceEntry(
            id=f"e{i:04d}",
            session_id="sess-test-001",
            action="run",
            tool="terminal",
            duration_ms=1200.0,
            status="success",
        )
        for i in range(5)
    ]
    entries.extend([
        TraceEntry(
            id="e1000",
            session_id="sess-test-001",
            action="read",
            tool="read_file",
            duration_ms=50.0,
            status="success",
        ),
        TraceEntry(
            id="e1001",
            session_id="sess-test-001",
            action="write",
            tool="write_file",
            duration_ms=500.0,
            status="error",
            error="Permission denied",
        ),
        TraceEntry(
            id="e1002",
            session_id="sess-test-002",
            action="search",
            tool="search_files",
            duration_ms=800.0,
            status="timeout",
            error="Timeout after 10s",
        ),
        TraceEntry(
            id="e1003",
            session_id="",
            action="chat",
            tool="",
            duration_ms=3500.0,
            status="success",
        ),
    ])
    for e in entries:
        store.record(e)
    return store


# ── Tests: TraceEntry ─────────────────────────────────────────────────


class TestTraceEntry:
    def test_default_values(self) -> None:
        """TraceEntry hat sinnvolle Defaults."""
        entry = TraceEntry()
        assert len(entry.id) == 12
        assert entry.status == "success"
        assert entry.duration_ms == 0.0
        assert entry.error == ""

    def test_to_dict_structure(self) -> None:
        """to_dict() liefert alle Felder."""
        entry = TraceEntry(
            action="test",
            tool="pytest",
            session_id="sess-123",
            duration_ms=42.5,
            status="error",
            error="something broke",
        )
        d = entry.to_dict()
        assert d["action"] == "test"
        assert d["tool"] == "pytest"
        assert d["session_id"] == "sess-123"
        assert d["duration_ms"] == 42.5
        assert d["status"] == "error"
        assert d["error"] == "something broke"


# ── Tests: TraceStore ─────────────────────────────────────────────────


class TestTraceStore:
    def test_record_and_query(self, store: TraceStore) -> None:
        """record() speichert und query() findet den Eintrag."""
        entry = TraceEntry(
            session_id="sess-alpha", action="run", tool="terminal",
            duration_ms=999.0,
        )
        entry_id = store.record(entry)
        assert entry_id == entry.id
        results = store.query(session_id="sess-alpha", limit=10)
        assert len(results) == 1
        assert results[0].id == entry.id
        assert results[0].duration_ms == 999.0

    def test_query_with_filters(self, sample_entries: TraceStore) -> None:
        """query() filtert nach action, tool, session_id."""
        results = sample_entries.query(tool="read_file", limit=10)
        assert len(results) == 1
        assert results[0].tool == "read_file"

        results = sample_entries.query(action="writ", limit=10)
        assert len(results) == 1
        assert results[0].tool == "write_file"

        results = sample_entries.query(session_id="nope", limit=10)
        assert len(results) == 0

    def test_query_limit(self, sample_entries: TraceStore) -> None:
        """query() respektiert das limit."""
        results = sample_entries.query(limit=3)
        assert len(results) == 3

    def test_get_stats_empty(self, store: TraceStore) -> None:
        """get_stats() auf leerem Store liefert Null-Werte."""
        stats = store.get_stats()
        assert stats["total_runs"] == 0
        assert stats["avg_duration_ms"] == 0.0
        assert stats["tool_usage_counts"] == {}
        assert stats["error_rate"] == 0.0

    def test_get_stats_full(self, sample_entries: TraceStore) -> None:
        """get_stats() berechnet korrekte Werte."""
        stats = sample_entries.get_stats()
        assert stats["total_runs"] == 9
        assert stats["avg_duration_ms"] > 0

        usage = stats["tool_usage_counts"]
        assert usage.get("terminal", 0) == 5
        assert usage.get("read_file", 0) == 1

        assert 11.0 <= stats["error_rate"] <= 12.0
        assert stats["status_counts"]["error"] == 1
        assert stats["status_counts"]["timeout"] == 1
        assert stats["status_counts"]["success"] == 7

    def test_get_timeline(self, sample_entries: TraceStore) -> None:
        """get_timeline() liefert chronologische Abfolge."""
        timeline = sample_entries.get_timeline("sess-test-001")
        assert len(timeline) == 7
        timestamps = [t["timestamp"] for t in timeline]
        assert timestamps == sorted(timestamps)

    def test_timeline_empty_session(self, store: TraceStore) -> None:
        """get_timeline() für unbekannte Session ist leer."""
        assert store.get_timeline("nonexistent") == []

    def test_clear(self, sample_entries: TraceStore) -> None:
        """clear() löscht alle Einträge."""
        assert sample_entries.get_stats()["total_runs"] > 0
        count = sample_entries.clear()
        assert count == 9
        assert sample_entries.get_stats()["total_runs"] == 0

    def test_record_updates_existing(self, store: TraceStore) -> None:
        """record() überschreibt bei gleicher ID."""
        e1 = TraceEntry(id="fixed", action="first", tool="a", duration_ms=100.0)
        store.record(e1)
        e2 = TraceEntry(id="fixed", action="second", tool="b", duration_ms=200.0)
        store.record(e2)
        results = store.query(limit=10)
        assert len(results) == 1
        assert results[0].action == "second"

    def test_db_file_created(self, db_path: Path) -> None:
        """Die DB-Datei wird beim ersten record() angelegt."""
        store = TraceStore(db_path=db_path)
        assert not db_path.exists()
        store.record(TraceEntry(action="x", tool="y"))
        store.close()
        assert db_path.exists()
        assert db_path.stat().st_size > 0

    def test_close_releases_file(self, db_path: Path) -> None:
        """Nach close() kann die DB-Datei gelöscht werden."""
        store = TraceStore(db_path=db_path)
        store.record(TraceEntry(action="a", tool="b"))
        store.close()
        # Sollte ohne PermissionError gehen
        db_path.unlink()
        assert not db_path.exists()


# ── Tests: HTML Dashboard ──────────────────────────────────────────────


class TestDashboard:
    def test_generate_html_empty(self, store: TraceStore) -> None:
        """Dashboard-HTML wird auch ohne Daten generiert."""
        html = generate_html_dashboard(store)
        assert "<!DOCTYPE html>" in html
        assert "OpenAmer Tracing Dashboard" in html
        assert "</html>" in html

    def test_generate_html_with_data(self, sample_entries: TraceStore) -> None:
        """Dashboard-HTML enhält Daten-Visualisierungen."""
        html = generate_html_dashboard(sample_entries)
        assert "Gesamtläufe" in html
        assert "9" in html
        assert "terminal" in html
        assert "<table>" in html
        assert "status-success" in html
        assert "sess-test-001" in html

    def test_dashboard_contains_css(self, store: TraceStore) -> None:
        """Dashboard hat eingebettetes CSS (keine externen Dependencies)."""
        html = generate_html_dashboard(store)
        assert "<style>" in html
        assert "@import" not in html


# ── Tests: Dashboard Server ────────────────────────────────────────────


@pytest.fixture
def server_info():
    """Startet einen Dashboard-Server in einem Thread (eigener Store)."""
    import shutil as _su
    import tempfile as _tf
    tdir = _tf.TemporaryDirectory()
    dbp = Path(tdir.name) / "srv.db"
    # Der Store wird im Server-Thread verwendet; kein close() vom Main-Thread.
    s = TraceStore(db_path=dbp)
    server = start_dashboard_server(port=0, store=s)
    port = server.server_port
    assert port > 0

    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    time.sleep(0.15)

    yield port

    server.shutdown()
    server.server_close()
    # SQLite-Connection gehört dem Server-Thread → ignore_errors
    _su.rmtree(tdir.name, ignore_errors=True)


class TestDashboardServer:
    def test_server_serves_html(self, server_info: int) -> None:
        """Server liefert HTML-Dashboard."""
        import urllib.request

        resp = urllib.request.urlopen(
            f"http://localhost:{server_info}/", timeout=5
        )
        html = resp.read().decode("utf-8")
        assert "OpenAmer Tracing Dashboard" in html

    def test_server_api_stats(self, server_info: int) -> None:
        """Server liefert JSON-API."""
        import urllib.request

        resp = urllib.request.urlopen(
            f"http://localhost:{server_info}/api/stats", timeout=5
        )
        stats = json.loads(resp.read().decode("utf-8"))
        assert "total_runs" in stats
        assert "avg_duration_ms" in stats

    def test_server_api_traces(self, server_info: int) -> None:
        """Server liefert Traces-JSON."""
        import urllib.request

        resp = urllib.request.urlopen(
            f"http://localhost:{server_info}/api/traces", timeout=5
        )
        data = json.loads(resp.read().decode("utf-8"))
        assert isinstance(data, list)

    def test_server_404(self, server_info: int) -> None:
        """Unbekannte Pfade geben 404."""
        import urllib.error
        import urllib.request

        try:
            urllib.request.urlopen(
                f"http://localhost:{server_info}/nothing", timeout=5
            )
            assert False, "Sollte 404 werfen"
        except urllib.error.HTTPError as e:
            assert e.code == 404


# ── Tests: CLI Interface ───────────────────────────────────────────────


class TestCLI:
    def test_build_parser_record(self) -> None:
        """Parser erkennt 'record'-Subcommand."""
        import argparse

        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="tracing_command")
        build_tracing_parser(subparsers)
        ns = parser.parse_args(["tracing", "record", "run", "terminal"])
        assert ns.tracing_command == "record"
        assert ns.action == "run"
        assert ns.tool == "terminal"

    def test_build_parser_list(self) -> None:
        """Parser erkennt 'list'-Subcommand."""
        import argparse

        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="tracing_command")
        build_tracing_parser(subparsers)
        ns = parser.parse_args(["tracing", "list", "--limit", "5"])
        assert ns.tracing_command == "list"
        assert ns.limit == 5

    def test_build_parser_dashboard(self) -> None:
        """Parser erkennt 'dashboard'-Subcommand."""
        import argparse

        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="tracing_command")
        build_tracing_parser(subparsers)
        ns = parser.parse_args(["tracing", "dashboard"])
        assert ns.tracing_command == "dashboard"

    def test_export_generates_file(self, sample_entries: TraceStore) -> None:
        """cmd_tracing_export schreibt eine HTML-Datei."""
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "report.html"

            import openamer_cli.tracing as tracing_mod

            original = tracing_mod.TraceStore
            tracing_mod.TraceStore = lambda **kw: sample_entries  # noqa: E731

            class FakeArgs:
                output = str(out)

            try:
                cmd_tracing_export(FakeArgs())
            finally:
                tracing_mod.TraceStore = original

            assert out.exists()
            content = out.read_text("utf-8")
            assert "OpenAmer Tracing Dashboard" in content
            assert "terminal" in content


# ── Test: Integration (Quick-Record) ───────────────────────────────────


class TestIntegration:
    def test_quick_record(self, store: TraceStore) -> None:
        """_quick_record erzeugt gültigen Eintrag."""
        from openamer_cli.tracing import _quick_record

        import openamer_cli.tracing as tracing_mod

        original = tracing_mod.TraceStore
        tracing_mod.TraceStore = lambda **kw: store

        try:
            entry_id = _quick_record(
                action="run", tool="terminal",
                session_id="sess-999", duration_ms=123.0,
            )
        finally:
            tracing_mod.TraceStore = original

        results = store.query(session_id="sess-999", limit=10)
        assert len(results) == 1
        assert results[0].duration_ms == 123.0