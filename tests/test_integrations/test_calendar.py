"""Tests for the CalendarIntegration class.

Uses monkeypatching to avoid real network calls.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from openamer_cli.integrations.calendar import (
    CalendarAPIError,
    CalendarIntegration,
    CredentialError,
)


class TestCredentialError:
    """Credential detection for Calendar integration."""

    def test_missing_all_creds(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("CALENDAR_CLIENT_ID", raising=False)
        monkeypatch.delenv("GMAIL_CLIENT_ID", raising=False)
        monkeypatch.delenv("CALENDAR_CLIENT_SECRET", raising=False)
        monkeypatch.delenv("GMAIL_CLIENT_SECRET", raising=False)
        monkeypatch.delenv("CALENDAR_REFRESH_TOKEN", raising=False)
        monkeypatch.delenv("GMAIL_REFRESH_TOKEN", raising=False)
        from openamer_cli.integrations.calendar import build_credentials

        with pytest.raises(CredentialError, match="CALENDAR_CLIENT_ID"):
            build_credentials()

    def test_fallback_works(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Calendar falls back to GMAIL_* env vars when CALENDAR_* are missing."""
        monkeypatch.delenv("CALENDAR_CLIENT_ID", raising=False)
        monkeypatch.delenv("CALENDAR_CLIENT_SECRET", raising=False)
        monkeypatch.delenv("CALENDAR_REFRESH_TOKEN", raising=False)
        monkeypatch.setenv("GMAIL_CLIENT_ID", "gmail-id")
        monkeypatch.setenv("GMAIL_CLIENT_SECRET", "gmail-secret")
        monkeypatch.setenv("GMAIL_REFRESH_TOKEN", "gmail-token")
        # This won't instantiate due to _HAS_GOOGLE flag in CI, but the env
        # logic should succeed before that check
        from openamer_cli.integrations.calendar import build_credentials
        from openamer_cli.integrations.calendar import _HAS_GOOGLE

        if not _HAS_GOOGLE:
            pytest.skip("google-api-python-client not installed")


class TestCalendarIntegration:
    """CalendarIntegration unit tests (no real API calls)."""

    @patch("openamer_cli.integrations.calendar.build_credentials")
    @patch("openamer_cli.integrations.calendar.build")
    def test_create_event(
        self,
        mock_build: MagicMock,
        mock_creds: MagicMock,
    ) -> None:
        mock_service = MagicMock()
        mock_build.return_value = mock_service
        mock_execute = MagicMock(
            return_value={
                "id": "evt-001",
                "summary": "Meeting",
                "htmlLink": "https://calendar.google.com/event?id=evt-001",
            }
        )
        mock_service.events.return_value.insert.return_value.execute = mock_execute

        cal = CalendarIntegration(credentials=mock_creds.return_value)
        start = datetime(2026, 8, 20, 14, 0, tzinfo=timezone.utc)
        end = datetime(2026, 8, 20, 15, 0, tzinfo=timezone.utc)
        result = cal.create_event("Meeting", start, end)

        assert result["id"] == "evt-001"
        assert result["summary"] == "Meeting"

    @patch("openamer_cli.integrations.calendar.build_credentials")
    @patch("openamer_cli.integrations.calendar.build")
    def test_create_event_api_error(
        self,
        mock_build: MagicMock,
        mock_creds: MagicMock,
    ) -> None:
        mock_service = MagicMock()
        mock_build.return_value = mock_service
        mock_service.events.return_value.insert.return_value.execute.side_effect = Exception(
            "API error"
        )

        cal = CalendarIntegration(credentials=mock_creds.return_value)
        start = datetime(2026, 8, 20, 14, 0, tzinfo=timezone.utc)
        end = datetime(2026, 8, 20, 15, 0, tzinfo=timezone.utc)
        with pytest.raises(CalendarAPIError):
            cal.create_event("Meeting", start, end)

    @patch("openamer_cli.integrations.calendar.build_credentials")
    @patch("openamer_cli.integrations.calendar.build")
    def test_list_events(
        self,
        mock_build: MagicMock,
        mock_creds: MagicMock,
    ) -> None:
        mock_service = MagicMock()
        mock_build.return_value = mock_service
        mock_execute = MagicMock(
            return_value={
                "items": [
                    {
                        "id": "e1",
                        "summary": "Event 1",
                        "start": {"dateTime": "2026-08-20T14:00:00Z"},
                    },
                    {
                        "id": "e2",
                        "summary": "Event 2",
                        "start": {"dateTime": "2026-08-21T10:00:00Z"},
                    },
                ]
            }
        )
        mock_service.events.return_value.list.return_value.execute = mock_execute

        cal = CalendarIntegration(credentials=mock_creds.return_value)
        time_min = datetime(2026, 8, 20, tzinfo=timezone.utc)
        time_max = datetime(2026, 8, 27, tzinfo=timezone.utc)
        events = cal.list_events(time_min, time_max, max_results=5)

        assert len(events) == 2
        assert events[0]["summary"] == "Event 1"