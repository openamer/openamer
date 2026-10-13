"""
Calendar Integration — create and list calendar events via the Google Calendar API.

Uses OAuth 2.0 via ``google.oauth2.credentials`` and the Google API client
(``googleapiclient``). Credentials are loaded from environment variables:

* ``CALENDAR_CLIENT_ID``
* ``CALENDAR_CLIENT_SECRET``
* ``CALENDAR_REFRESH_TOKEN``

Alternatively, you can reuse the same ``GMAIL_*`` variables by passing a
custom ``credentials`` object to the constructor — the OAuth scopes overlap.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    _HAS_GOOGLE = True
except ImportError:
    _HAS_GOOGLE = False

    class Credentials:  # type: ignore[no-redef]
        pass

    def build(*args: Any, **kwargs: Any) -> Any:  # type: ignore[misc]
        raise ImportError(
            "google-api-python-client is required for Calendar integration. "
            "Install it with: pip install google-api-python-client google-auth-httplib2"
        )


# ---------------------------------------------------------------------------
# Error types
# ---------------------------------------------------------------------------


class CredentialError(Exception):
    """Raised when a required credential is missing or invalid."""


class CalendarAPIError(Exception):
    """Raised when the Calendar API returns an error."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _require_env(name: str) -> str:
    """Return *name* from the environment or raise :class:`CredentialError`."""
    val = os.environ.get(name)
    if not val:
        raise CredentialError(
            f"Calendar integration requires {name!r} to be set in the environment. "
            f"Set it in your .env file or export it before running OpenAmer."
        )
    return val


SCOPES = ["https://www.googleapis.com/auth/calendar.events"]


def build_credentials() -> Credentials:
    """Build OAuth2 :class:`Credentials` for the Calendar API.

    Reads ``CALENDAR_CLIENT_ID``, ``CALENDAR_CLIENT_SECRET``, and
    ``CALENDAR_REFRESH_TOKEN`` from the environment. Falls back to reusing
    Gmail credentials (``GMAIL_CLIENT_ID``, etc.) if calendar-specific ones
    are absent.
    """
    client_id = os.environ.get("CALENDAR_CLIENT_ID") or os.environ.get(
        "GMAIL_CLIENT_ID"
    )
    client_secret = os.environ.get("CALENDAR_CLIENT_SECRET") or os.environ.get(
        "GMAIL_CLIENT_SECRET"
    )
    refresh_token = os.environ.get("CALENDAR_REFRESH_TOKEN") or os.environ.get(
        "GMAIL_REFRESH_TOKEN"
    )

    missing: list[str] = []
    if not client_id:
        missing.append("CALENDAR_CLIENT_ID or GMAIL_CLIENT_ID")
    if not client_secret:
        missing.append("CALENDAR_CLIENT_SECRET or GMAIL_CLIENT_SECRET")
    if not refresh_token:
        missing.append("CALENDAR_REFRESH_TOKEN or GMAIL_REFRESH_TOKEN")
    if missing:
        raise CredentialError(
            "Calendar integration requires the following env vars: "
            + ", ".join(missing)
        )

    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
        scopes=SCOPES,
    )
    creds.refresh(Request())
    return creds


def _to_rfc3339(dt: datetime) -> str:
    """Convert a datetime to RFC3339 string."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


# ---------------------------------------------------------------------------
# Integration class
# ---------------------------------------------------------------------------


class CalendarIntegration:
    """Create and list Google Calendar events.

    Usage::

        cal = CalendarIntegration()
        event = cal.create_event("Meeting", start_time, end_time)
        events = cal.list_events(time_min, time_max, max_results=10)
    """

    def __init__(self, credentials: Credentials | None = None) -> None:
        if not _HAS_GOOGLE:
            raise ImportError(
                "google-api-python-client is not installed. "
                "Install it with: pip install google-api-python-client google-auth-httplib2"
            )
        if credentials is None:
            credentials = build_credentials()
        self._service = build("calendar", "v3", credentials=credentials)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def create_event(
        self,
        summary: str,
        start_time: datetime,
        end_time: datetime,
    ) -> dict[str, Any]:
        """Create a calendar event.

        Args:
            summary: Event title.
            start_time: Start datetime (timezone-aware preferred; naive = UTC).
            end_time: End datetime.

        Returns:
            The created event dict (``id``, ``htmlLink``, ``summary``, …).

        Raises:
            CalendarAPIError: On API failure.
        """
        body: dict[str, Any] = {
            "summary": summary,
            "start": {
                "dateTime": _to_rfc3339(start_time),
                "timeZone": "UTC",
            },
            "end": {
                "dateTime": _to_rfc3339(end_time),
                "timeZone": "UTC",
            },
        }
        try:
            result = (
                self._service.events()
                .insert(calendarId="primary", body=body)
                .execute()
            )
        except Exception as exc:
            raise CalendarAPIError(f"Failed to create event: {exc}") from exc
        return result  # type: ignore[return-value]

    def list_events(
        self,
        time_min: datetime,
        time_max: datetime,
        max_results: int = 10,
    ) -> list[dict[str, Any]]:
        """List events in a time range.

        Args:
            time_min: Start of the time window.
            time_max: End of the time window.
            max_results: Maximum events to return (default 10).

        Returns:
            List of event dicts sorted by start time.

        Raises:
            CalendarAPIError: On API failure.
        """
        try:
            result = (
                self._service.events()
                .list(
                    calendarId="primary",
                    timeMin=_to_rfc3339(time_min),
                    timeMax=_to_rfc3339(time_max),
                    maxResults=max_results,
                    singleEvents=True,
                    orderBy="startTime",
                )
                .execute()
            )
        except Exception as exc:
            raise CalendarAPIError(f"Failed to list events: {exc}") from exc
        return result.get("items", [])  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# CLI convenience
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    try:
        cal = CalendarIntegration()
    except (CredentialError, ImportError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        sys.exit(1)

    action = sys.argv[1] if len(sys.argv) > 1 else "help"

    if action == "create":
        summary = sys.argv[2] if len(sys.argv) > 2 else input("Summary: ")
        start_str = (
            sys.argv[3]
            if len(sys.argv) > 3
            else input("Start time (ISO format): ")
        )
        end_str = (
            sys.argv[4]
            if len(sys.argv) > 4
            else input("End time (ISO format): ")
        )
        start = datetime.fromisoformat(start_str)
        end = datetime.fromisoformat(end_str)
        event = cal.create_event(summary, start, end)
        print(f"Created: {event.get('summary')} — {event.get('htmlLink')}")
    elif action == "list":
        from datetime import timedelta

        time_min = datetime.now(timezone.utc)
        time_max = time_min + timedelta(days=7)
        events = cal.list_events(time_min, time_max)
        print(f"Found {len(events)} events:")
        for ev in events:
            start_info = ev.get("start", {}).get("dateTime", ev.get("start", {}).get("date", "?"))
            print(f"  {ev.get('summary')} @ {start_info}")
    else:
        print("Usage: python calendar.py <create|list> [args...]")