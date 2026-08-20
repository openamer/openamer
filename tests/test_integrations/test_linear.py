"""Tests for the LinearIntegration class.

Uses monkeypatching to avoid real HTTP calls.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from openamer_cli.integrations.linear import (
    CredentialError,
    LinearAPIError,
    LinearIntegration,
)


class TestCredentialError:
    """Credential detection for Linear integration."""

    def test_missing_api_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("LINEAR_API_KEY", raising=False)
        with pytest.raises(CredentialError, match="LINEAR_API_KEY"):
            LinearIntegration()


class TestLinearIntegration:
    """LinearIntegration unit tests (no real API calls)."""

    @patch("openamer_cli.integrations.linear.urllib.request.urlopen")
    def test_create_issue(self, mock_urlopen: MagicMock) -> None:
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "data": {
                "issueCreate": {
                    "success": True,
                    "issue": {
                        "id": "lin-123",
                        "title": "Test Issue",
                        "identifier": "TEA-1",
                        "url": "https://linear.app/team/issue/TEA-1",
                    },
                }
            }
        }).encode()
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        linear = self._make_integration()
        result = linear.create_issue("team-id", "Test Issue", "Description")

        assert result["identifier"] == "TEA-1"
        assert result["title"] == "Test Issue"

    @patch("openamer_cli.integrations.linear.urllib.request.urlopen")
    def test_get_issue(self, mock_urlopen: MagicMock) -> None:
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "data": {
                "issue": {
                    "id": "lin-123",
                    "title": "Existing Issue",
                    "identifier": "TEA-2",
                    "url": "https://linear.app/team/issue/TEA-2",
                    "state": {"id": "s1", "name": "In Progress", "type": "started"},
                    "priority": 3,
                }
            }
        }).encode()
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        linear = self._make_integration()
        result = linear.get_issue("lin-123")

        assert result["identifier"] == "TEA-2"
        assert result["state"]["name"] == "In Progress"

    @patch("openamer_cli.integrations.linear.urllib.request.urlopen")
    def test_list_issues(self, mock_urlopen: MagicMock) -> None:
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "data": {
                "team": {
                    "issues": {
                        "nodes": [
                            {
                                "id": "lin-1",
                                "title": "Issue 1",
                                "identifier": "TEA-3",
                                "priority": 1,
                            },
                            {
                                "id": "lin-2",
                                "title": "Issue 2",
                                "identifier": "TEA-4",
                                "priority": 2,
                            },
                        ]
                    }
                }
            }
        }).encode()
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        linear = self._make_integration()
        issues = linear.list_issues("team-id")

        assert len(issues) == 2
        assert issues[0]["identifier"] == "TEA-3"
        assert issues[1]["title"] == "Issue 2"

    @patch("openamer_cli.integrations.linear.urllib.request.urlopen")
    def test_api_error_raises(self, mock_urlopen: MagicMock) -> None:
        import urllib.error

        error_response = MagicMock()
        error_response.read.return_value = b'{"errors":[{"message":"Invalid API key"}]}'
        error_response.code = 401

        mock_urlopen.side_effect = urllib.error.HTTPError(
            url="http://example.com", code=401, msg="Unauthorized",
            hdrs={}, fp=error_response,
        )

        linear = self._make_integration()
        with pytest.raises(LinearAPIError, match="401"):
            linear.list_issues("team-id")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _make_integration() -> LinearIntegration:
        monkeypatch = pytest.MonkeyPatch()
        monkeypatch.setenv("LINEAR_API_KEY", "lin-api-key-123")
        try:
            return LinearIntegration()
        finally:
            monkeypatch.undo()