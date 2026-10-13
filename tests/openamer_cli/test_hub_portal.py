"""
Tests für ``openamer_cli.hub_portal`` — OpenAmer Hub Dashboard.

Testet:
  - HubPortal start/stop/is_running
  - HTTP-Server antwortet auf API-Endpunkte
  - Dashboard HTML wird korrekt gerendert
  - API-Endpunkte liefern JSON mit erwarteten Schlüsseln
  - CLI-Parser-Registrierung
  - Singleton-Verhalten
"""

from __future__ import annotations

import json
import threading
import time
from http.client import HTTPConnection
from pathlib import Path
from typing import Any
from unittest.mock import patch, MagicMock

import pytest

from openamer_cli.hub_portal import (
    HubPortal,
    _get_portal,
    _get_superintelligence_status,
    _get_model_config,
    _get_token_usage,
    _get_providers,
    _get_skills_list,
    _get_memory_status,
)


# =============================================================================
# Hilfsfunktionen
# =============================================================================


def _wait_for_server(portal: HubPortal, timeout: float = 10.0) -> bool:
    """Wartet bis der Server auf dem Port lauscht."""
    time.sleep(0.5)  # Kurze Startverzögerung abfangen
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            conn = HTTPConnection(portal.host, portal.port, timeout=1)
            conn.request("GET", "/")
            resp = conn.getresponse()
            resp.read()
            conn.close()
            return True
        except (ConnectionRefusedError, TimeoutError, OSError):
            time.sleep(0.1)
    return False


def _fetch(portal: HubPortal, path: str) -> tuple[int, bytes, dict[str, Any]]:
    """Führt eine GET-Anfrage gegen das Portal aus.

    Returns:
        (status_code, body_bytes, response_headers)
    """
    conn = HTTPConnection(portal.host, portal.port, timeout=5)
    conn.request("GET", path)
    resp = conn.getresponse()
    body = resp.read()
    headers = dict(resp.getheaders())
    conn.close()
    return resp.status, body, headers


# =============================================================================
# Test: HubPortal start/stop/is_running
# =============================================================================


class TestHubPortalLifecycle:
    """Start, Stop und Lebenszyklus des Portals."""

    def test_start_stop(self):
        """Ein Portal starten und wieder stoppen."""
        portal = HubPortal(port=0, quiet=True)  # port=0 → OS wählt Port
        try:
            server = portal.start()
            assert portal.is_running, "Portal sollte nach start() running sein"
            assert portal._server is server
            assert portal._thread is not None
            assert portal._thread.is_alive()
        finally:
            portal.stop()
        assert not portal.is_running, "Portal sollte nach stop() nicht running sein"

    def test_start_assigns_port(self):
        """start(port=X) überschreibt self.port."""
        portal = HubPortal(port=9999, quiet=True)
        try:
            portal.start(port=8765)
            assert portal.port == 8765
        finally:
            portal.stop()

    def test_start_twice_is_noop(self, capsys):
        """Zweimaliges start() sollte eine Warnung ausgeben und die selbe Instanz liefern."""
        portal = HubPortal(port=0, quiet=False)
        try:
            s1 = portal.start()
            s2 = portal.start()
            assert s1 is s2
            out = capsys.readouterr().out
            assert "läuft bereits" in out
        finally:
            portal.stop()

    def test_stop_without_start(self, capsys):
        """stop() ohne vorheriges start() sollte eine freundliche Meldung ausgeben."""
        portal = HubPortal(port=9999, quiet=False)
        portal.stop()
        out = capsys.readouterr().out
        assert "Kein aktiver Server" in out

    def test_is_running_false_after_stop(self):
        """is_running sollte False sein, sobald der Server gestoppt ist."""
        portal = HubPortal(port=0, quiet=True)
        assert not portal.is_running
        try:
            portal.start()
            assert portal.is_running
        finally:
            portal.stop()
        assert not portal.is_running


# =============================================================================
# Test: Dashboard HTML
# =============================================================================


class TestDashboardHTML:
    """Das Dashboard wird als HTML ausgeliefert."""

    def test_html_renders(self):
        """render_dashboard() gibt gültiges HTML zurück."""
        portal = HubPortal(port=0, quiet=True)
        html = portal.render_dashboard()
        assert "<!DOCTYPE html>" in html
        assert "OpenAmer Hub" in html
        assert "</html>" in html
        # Wichtige UI-Elemente
        assert "System-Status" in html
        assert "Provider-Status" in html
        assert "Token-Verbrauch" in html
        assert "Skills" in html
        assert "Memory" in html
        # Version
        assert "1.0.0" in html

    def test_html_dark_theme_css(self):
        """Das HTML enthält Dark-Theme CSS-Variablen."""
        html = HubPortal(port=0, quiet=True).render_dashboard()
        assert "--bg: #0d1117" in html
        assert "--surface: #161b22" in html
        assert "--accent: #58a6ff" in html

    def test_html_inline_refresh_js(self):
        """Das HTML enthält das JS für Live-Updates (fetchAll)."""
        html = HubPortal(port=0, quiet=True).render_dashboard()
        assert "fetchAll" in html
        assert "fetch('/api/status')" in html
        assert "REFRESH_INTERVAL_MS" in html

    def test_html_responsive_meta(self):
        """Das HTML enthält responsive viewport meta."""
        html = HubPortal(port=0, quiet=True).render_dashboard()
        assert 'name="viewport"' in html
        assert "device-width" in html


# =============================================================================
# Test: HTTP-Endpunkte
# =============================================================================


class TestAPIEndpoints:
    """Die REST-API-Endpunkte liefern korrekte Antworten."""

    @pytest.fixture
    def portal(self):
        """Startet ein Portal auf einem freien Port."""
        p = HubPortal(port=0, quiet=True)
        p.start()
        if not _wait_for_server(p):
            pytest.fail("Portal konnte nicht innerhalb des Timeouts starten")
        yield p
        try:
            p.stop()
        except Exception:
            pass

    def test_root_returns_html(self, portal):
        """GET / sollte HTML mit dem Dashboard zurückgeben."""
        status, body, headers = _fetch(portal, "/")
        assert status == 200
        ct = headers.get("Content-Type", "")
        assert "text/html" in ct
        assert "OpenAmer Hub" in body.decode("utf-8")

    def test_api_status(self, portal):
        """GET /api/status sollte JSON mit overall_score liefern."""
        status, body, headers = _fetch(portal, "/api/status")
        assert status == 200
        assert "application/json" in headers.get("Content-Type", "")
        data = json.loads(body)
        assert "overall_score" in data
        assert "tools_count" in data
        assert "skills_count" in data
        assert "timestamp" in data

    def test_api_model(self, portal):
        """GET /api/model sollte JSON zurückgeben."""
        status, body, headers = _fetch(portal, "/api/model")
        assert status == 200
        data = json.loads(body)
        assert "model" in data
        assert "provider" in data
        assert "base_url" in data

    def test_api_usage(self, portal):
        """GET /api/usage sollte Token-Zählungen enthalten."""
        status, body, headers = _fetch(portal, "/api/usage")
        assert status == 200
        data = json.loads(body)
        assert "total_tokens" in data
        assert "tokens_in" in data
        assert "tokens_out" in data
        assert "total_cost" in data

    def test_api_providers(self, portal):
        """GET /api/providers sollte eine Liste liefern."""
        status, body, headers = _fetch(portal, "/api/providers")
        assert status == 200
        data = json.loads(body)
        assert isinstance(data, list)
        if data:
            entry = data[0]
            assert "name" in entry
            assert "status" in entry

    def test_api_skills(self, portal):
        """GET /api/skills sollte eine Liste liefern."""
        status, body, headers = _fetch(portal, "/api/skills")
        assert status == 200
        data = json.loads(body)
        assert isinstance(data, list)

    def test_api_memory(self, portal):
        """GET /api/memory sollte Speicherstatistiken enthalten."""
        status, body, headers = _fetch(portal, "/api/memory")
        assert status == 200
        data = json.loads(body)
        assert "memory_files" in data
        assert "memory_size_mb" in data
        assert "vector_size_mb" in data

    def test_api_404(self, portal):
        """Unbekannter Pfad sollte 404 + JSON zurückgeben."""
        status, body, headers = _fetch(portal, "/api/nonexistent")
        assert status == 404
        data = json.loads(body)
        assert data.get("error") == "not_found"

    def test_api_cors_headers(self, portal):
        """API-Antworten sollten CORS-Header enthalten."""
        _, _, headers = _fetch(portal, "/api/status")
        assert headers.get("Access-Control-Allow-Origin") == "*"

    def test_api_no_cache_headers(self, portal):
        """API-Antworten sollten Cache-Control: no-cache enthalten."""
        _, _, headers = _fetch(portal, "/api/status")
        cc = headers.get("Cache-Control", "")
        assert "no-cache" in cc


# =============================================================================
# Test: Module-Level Singleton
# =============================================================================


class TestSingleton:
    """_get_portal() liefert immer die selbe Instanz."""

    def test_singleton_identity(self):
        p1 = _get_portal()
        p2 = _get_portal()
        assert p1 is p2

    def test_singleton_defaults(self):
        p = _get_portal()
        assert isinstance(p, HubPortal)


# =============================================================================
# Test: API-Hilfsfunktionen
# =============================================================================


class TestHelpers:
    """Die internen Hilfsfunktionen sollten fehlertolerant sein."""

    def test_get_superintelligence_status_returns_dict(self):
        result = _get_superintelligence_status()
        assert isinstance(result, dict)
        assert "overall_score" in result

    def test_get_model_config_returns_dict(self):
        result = _get_model_config()
        assert isinstance(result, dict)
        assert "model" in result
        assert "provider" in result

    def test_get_token_usage_returns_dict(self):
        result = _get_token_usage()
        assert isinstance(result, dict)
        assert "total_tokens" in result
        assert result["total_tokens"] == 0  # kein echter Store → 0

    def test_get_providers_returns_list(self):
        result = _get_providers()
        assert isinstance(result, list)

    def test_get_skills_list_returns_list(self):
        result = _get_skills_list()
        assert isinstance(result, list)

    def test_get_memory_status_returns_dict(self):
        result = _get_memory_status()
        assert isinstance(result, dict)
        assert "memory_files" in result
        assert "memory_size_mb" in result


# =============================================================================
# Test: CLI-Parser
# =============================================================================


class TestCLIParser:
    """Der argparse-Parser für ``openamer hub`` sollte korrekt funktionieren."""

    def test_parser_registers_commands(self):
        """Der Parser sollte die Subbefehle start, status, stop kennen."""
        from openamer_cli.hub_portal import add_parser
        import argparse

        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers()
        add_parser(subparsers)

        # hub start
        args = parser.parse_args(["hub", "start"])
        assert args.hub_command == "start"
        assert hasattr(args, "func")

        # hub status
        args = parser.parse_args(["hub", "status"])
        assert args.hub_command == "status"
        assert hasattr(args, "func")

        # hub stop
        args = parser.parse_args(["hub", "stop"])
        assert args.hub_command == "stop"
        assert hasattr(args, "func")

    def test_start_port_default(self):
        """``hub start`` sollte Port 5000 als Standard haben."""
        from openamer_cli.hub_portal import add_parser
        import argparse

        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers()
        add_parser(subparsers)

        args = parser.parse_args(["hub", "start"])
        assert args.port == 5000

    def test_start_port_override(self):
        """``hub start --port 8080`` sollte den Port überschreiben."""
        from openamer_cli.hub_portal import add_parser
        import argparse

        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers()
        add_parser(subparsers)

        args = parser.parse_args(["hub", "start", "--port", "8080"])
        assert args.port == 8080