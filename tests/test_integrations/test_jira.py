"""Tests for the JiraIntegration class.

Uses monkeypatching to avoid real HTTP calls.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from openamer_cli.integrations.jira import (
    CredentialError,
    JiraAPIError,
    JiraIntegration,
)


class TestCredentialError:
    """Credential detection for Jira integration."""

    def test_missing_base_url(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("JIRA_BASE_URL", raising=False)
        monkeypatch.setenv("JIRA_EMAIL", "user@example.com")
        monkeypatch.setenv("JIRA_API_TOKEN", "token")
        with pytest.raises(CredentialError, match="JIRA_BASE_URL"):
            JiraIntegration()

    def test_missing_email(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JIRA_BASE_URL", "https://example.atlassian.net")
        monkeypatch.delenv("JIRA_EMAIL", raising=False)
        monkeypatch.setenv("JIRA_API_TOKEN", "token")
        with pytest.raises(CredentialError, match="JIRA_EMAIL"):
            JiraIntegration()


class TestJiraIntegration:
    """JiraIntegration unit tests (no real API calls)."""

    @patch("openamer_cli.integrations.jira.urllib.request.urlopen")
    def test_create_issue(self, mock_urlopen: MagicMock) -> None:
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(
            {"id": "10001", "key": "PROJ-1", "self": "https://example.atlassian.net/rest/api/3/issue/10001"}
        ).encode()
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        jira = self._make_integration()
        result = jira.create_issue("PROJ", "Summary", "Description")

        assert result["key"] == "PROJ-1"
        assert result["id"] == "10001"

    @patch("openamer_cli.integrations.jira.urllib.request.urlopen")
    def test_get_issue(self, mock_urlopen: MagicMock) -> None:
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(
            {
                "id": "10001",
                "key": "PROJ-1",
                "fields": {"summary": "Test issue", "status": {"name": "To Do"}},
            }
        ).encode()
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        jira = self._make_integration()
        result = jira.get_issue("PROJ-1")

        assert result["key"] == "PROJ-1"
        assert result["fields"]["summary"] == "Test issue"

    @patch("openamer_cli.integrations.jira.urllib.request.urlopen")
    def test_search_issues(self, mock_urlopen: MagicMock) -> None:
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(
            {
                "issues": [
                    {"id": "1", "key": "PROJ-1", "fields": {"summary": "First"}},
                    {"id": "2", "key": "PROJ-2", "fields": {"summary": "Second"}},
                ]
            }
        ).encode()
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        jira = self._make_integration()
        issues = jira.search_issues("project = PROJ")

        assert len(issues) == 2
        assert issues[0]["key"] == "PROJ-1"

    @patch("openamer_cli.integrations.jira.urllib.request.urlopen")
    def test_api_error_wraps(self, mock_urlopen: MagicMock) -> None:
        import urllib.error

        error_response = MagicMock()
        error_response.read.return_value = b'{"errorMessages":["Not found"]}'
        error_response.code = 404

        mock_urlopen.side_effect = urllib.error.HTTPError(
            url="http://example.com", code=404, msg="Not Found",
            hdrs={}, fp=error_response,
        )

        jira = self._make_integration()
        with pytest.raises(JiraAPIError, match="404"):
            jira.get_issue("NONEXISTENT-1")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _make_integration() -> JiraIntegration:
        monkeypatch = pytest.MonkeyPatch()
        monkeypatch.setenv("JIRA_BASE_URL", "https://example.atlassian.net")
        monkeypatch.setenv("JIRA_EMAIL", "user@example.com")
        monkeypatch.setenv("JIRA_API_TOKEN", "api-token")
        try:
            return JiraIntegration()
        finally:
            monkeypatch.undo()