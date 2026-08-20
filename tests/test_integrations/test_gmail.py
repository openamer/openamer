"""Tests for the GmailIntegration class.

Uses monkeypatching to avoid real network calls.
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, PropertyMock, patch

import pytest

from openamer_cli.integrations.gmail import (
    CredentialError,
    GmailAPIError,
    GmailIntegration,
)


class TestCredentialError:
    """Credential detection for Gmail integration."""

    def test_missing_creds_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Missing env vars raise CredentialError via build_credentials()."""
        monkeypatch.delenv("GMAIL_CLIENT_ID", raising=False)
        monkeypatch.delenv("GMAIL_CLIENT_SECRET", raising=False)
        monkeypatch.delenv("GMAIL_REFRESH_TOKEN", raising=False)
        from openamer_cli.integrations.gmail import build_credentials

        with pytest.raises(CredentialError, match="GMAIL_CLIENT_ID"):
            build_credentials()

    def test_message_helpful(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The error message guides the user to set the env var."""
        monkeypatch.delenv("GMAIL_CLIENT_ID", raising=False)
        from openamer_cli.integrations.gmail import build_credentials

        with pytest.raises(CredentialError) as exc:
            build_credentials()
        assert "GMAIL_CLIENT_ID" in str(exc.value)
        assert ".env" in str(exc.value)


class TestGmailIntegration:
    """GmailIntegration unit tests (no real API calls)."""

    @patch("openamer_cli.integrations.gmail.build_credentials")
    @patch("openamer_cli.integrations.gmail.build")
    def test_send_email(
        self,
        mock_build: MagicMock,
        mock_creds: MagicMock,
    ) -> None:
        """send_email posts a base64-encoded MIME message and returns the API response."""
        mock_service = MagicMock()
        mock_build.return_value = mock_service
        mock_execute = MagicMock(return_value={"id": "abc123", "threadId": "t-001"})
        mock_service.users.return_value.messages.return_value.send.return_value.execute = (
            mock_execute
        )

        gmail = GmailIntegration(credentials=mock_creds.return_value)
        result = gmail.send_email("test@example.com", "Subject", "Body")

        assert result["id"] == "abc123"
        mock_execute.assert_called_once()

    @patch("openamer_cli.integrations.gmail.build_credentials")
    @patch("openamer_cli.integrations.gmail.build")
    def test_send_email_api_error(
        self,
        mock_build: MagicMock,
        mock_creds: MagicMock,
    ) -> None:
        """API errors are wrapped in GmailAPIError."""
        mock_service = MagicMock()
        mock_build.return_value = mock_service
        mock_service.users.return_value.messages.return_value.send.return_value.execute.side_effect = Exception(
            "API error"
        )

        gmail = GmailIntegration(credentials=mock_creds.return_value)
        with pytest.raises(GmailAPIError):
            gmail.send_email("test@example.com", "Sub", "Body")

    @patch("openamer_cli.integrations.gmail.build_credentials")
    @patch("openamer_cli.integrations.gmail.build")
    def test_read_emails(
        self,
        mock_build: MagicMock,
        mock_creds: MagicMock,
    ) -> None:
        """read_emails fetches and returns a list of messages."""
        mock_service = MagicMock()
        mock_build.return_value = mock_service

        # Mock list response
        mock_service.users.return_value.messages.return_value.list.return_value.execute.return_value = {
            "messages": [{"id": "m1"}, {"id": "m2"}]
        }
        # Mock get response
        mock_service.users.return_value.messages.return_value.get.return_value.execute.side_effect = [
            {"id": "m1", "snippet": "Hello"},
            {"id": "m2", "snippet": "World"},
        ]

        gmail = GmailIntegration(credentials=mock_creds.return_value)
        msgs = gmail.read_emails("is:unread", max_results=5)
        assert len(msgs) == 2
        assert msgs[0]["id"] == "m1"

    @patch("openamer_cli.integrations.gmail.build_credentials")
    @patch("openamer_cli.integrations.gmail.build")
    def test_search_emails(
        self,
        mock_build: MagicMock,
        mock_creds: MagicMock,
    ) -> None:
        """search_emails delegates to read_emails with a query."""
        mock_service = MagicMock()
        mock_build.return_value = mock_service

        mock_service.users.return_value.messages.return_value.list.return_value.execute.return_value = {
            "messages": []
        }

        gmail = GmailIntegration(credentials=mock_creds.return_value)
        results = gmail.search_emails("from:someone")
        assert results == []


class TestBuildCredentials:
    """Tests for the build_credentials helper."""

    def test_missing_id(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GMAIL_CLIENT_ID", "")
        monkeypatch.setenv("GMAIL_CLIENT_SECRET", "secret")
        monkeypatch.setenv("GMAIL_REFRESH_TOKEN", "token")
        with pytest.raises(CredentialError, match="GMAIL_CLIENT_ID"):
            from openamer_cli.integrations.gmail import build_credentials

            build_credentials()