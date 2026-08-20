"""
Gmail Integration — send and read emails via the Gmail API.

Uses OAuth 2.0 via ``google.oauth2.credentials`` and the Google
Discovery-based API client (``googleapiclient``). Credentials are loaded
from environment variables:

* ``GMAIL_CLIENT_ID``
* ``GMAIL_CLIENT_SECRET``
* ``GMAIL_REFRESH_TOKEN``

A helper :func:`build_credentials` assembles the credentials object from
those env vars, and each method refreshes the token automatically when
the underlying HTTP 401s.
"""

from __future__ import annotations

import json
import os
from typing import Any

try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    _HAS_GOOGLE = True
except ImportError:
    _HAS_GOOGLE = False

    # Stubs so the module can be imported without google-api-python-client.
    class Credentials:  # type: ignore[no-redef]
        pass

    def build(*args: Any, **kwargs: Any) -> Any:  # type: ignore[misc]
        raise ImportError(
            "google-api-python-client is required for Gmail integration. "
            "Install it with: pip install google-api-python-client google-auth-httplib2"
        )


# ---------------------------------------------------------------------------
# Error types
# ---------------------------------------------------------------------------


class CredentialError(Exception):
    """Raised when a required credential is missing or invalid."""


class GmailAPIError(Exception):
    """Raised when the Gmail API returns an error."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _require_env(name: str) -> str:
    """Return *name* from the environment or raise :class:`CredentialError`."""
    val = os.environ.get(name)
    if not val:
        raise CredentialError(
            f"Gmail integration requires {name!r} to be set in the environment. "
            f"Set it in your .env file or export it before running OpenAmer."
        )
    return val


SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]


def build_credentials() -> Credentials:
    """Build OAuth2 :class:`Credentials` from environment variables.

    Raises :class:`CredentialError` when any of ``GMAIL_CLIENT_ID``,
    ``GMAIL_CLIENT_SECRET``, or ``GMAIL_REFRESH_TOKEN`` is missing.
    """
    client_id = _require_env("GMAIL_CLIENT_ID")
    client_secret = _require_env("GMAIL_CLIENT_SECRET")
    refresh_token = _require_env("GMAIL_REFRESH_TOKEN")

    creds = Credentials(
        token=None,  # no access token yet — refresh will set it
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
        scopes=SCOPES,
    )
    # Immediately refresh to get a valid access token.
    creds.refresh(Request())
    return creds


# ---------------------------------------------------------------------------
# Integration class
# ---------------------------------------------------------------------------


class GmailIntegration:
    """Send and read emails via the Gmail API.

    Usage::

        gmail = GmailIntegration()
        msg = gmail.send_email("user@example.com", "Subject", "Body")
        threads = gmail.read_emails("is:unread", max_results=5)
        results = gmail.search_emails("from:someone subject:hello")
    """

    def __init__(self, credentials: Credentials | None = None) -> None:
        if not _HAS_GOOGLE:
            raise ImportError(
                "google-api-python-client is not installed. "
                "Install it with: pip install google-api-python-client google-auth-httplib2"
            )
        if credentials is None:
            credentials = build_credentials()
        self._service = build("gmail", "v1", credentials=credentials)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def send_email(self, to: str, subject: str, body: str) -> dict[str, Any]:
        """Send an email via the Gmail API.

        Args:
            to: Recipient email address.
            subject: Email subject line.
            body: Plain-text email body.

        Returns:
            The API response dict (contains ``id``, ``threadId``, ``labelIds``).

        Raises:
            GmailAPIError: On API failure.
        """
        import base64
        from email.mime.text import MIMEText

        message = MIMEText(body)
        message["to"] = to
        message["subject"] = subject

        raw = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
        try:
            result = (
                self._service.users()
                .messages()
                .send(userId="me", body={"raw": raw})
                .execute()
            )
        except Exception as exc:
            raise GmailAPIError(f"Failed to send email: {exc}") from exc
        return result  # type: ignore[return-value]

    def read_emails(
        self, query: str = "", max_results: int = 10
    ) -> list[dict[str, Any]]:
        """Read emails matching *query*.

        Args:
            query: Gmail search query string (same as the web search box).
            max_results: Maximum number of messages to return (default 10).

        Returns:
            A list of message dicts with ``id``, ``threadId``, ``snippet``,
            and ``payload`` headers.

        Raises:
            GmailAPIError: On API failure.
        """
        try:
            response = (
                self._service.users()
                .messages()
                .list(userId="me", q=query, maxResults=max_results)
                .execute()
            )
        except Exception as exc:
            raise GmailAPIError(f"Failed to list emails: {exc}") from exc

        messages = response.get("messages", [])
        results: list[dict[str, Any]] = []
        for msg in messages:
            try:
                detail = (
                    self._service.users()
                    .messages()
                    .get(userId="me", id=msg["id"])
                    .execute()
                )
                results.append(detail)
            except Exception:
                pass  # skip individual message fetch failures
        return results

    def search_emails(self, query: str) -> list[dict[str, Any]]:
        """Search emails and return full message details.

        Delegates to :meth:`read_emails` with an explicit query.

        Args:
            query: Gmail search query (same syntax as Gmail web search).

        Returns:
            List of matching message dicts.
        """
        return self.read_emails(query=query, max_results=20)


# ---------------------------------------------------------------------------
# CLI convenience
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    try:
        gmail = GmailIntegration()
    except (CredentialError, ImportError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        sys.exit(1)

    action = sys.argv[1] if len(sys.argv) > 1 else "help"

    if action == "send":
        to = sys.argv[2] if len(sys.argv) > 2 else input("To: ")
        subject = sys.argv[3] if len(sys.argv) > 3 else input("Subject: ")
        body = sys.argv[4] if len(sys.argv) > 4 else input("Body: ")
        result = gmail.send_email(to, subject, body)
        print(f"Sent: {result.get('id')}")
    elif action == "read":
        query = sys.argv[2] if len(sys.argv) > 2 else ""
        results = gmail.read_emails(query=query)
        print(f"Found {len(results)} messages:")
        for msg in results:
            print(f"  {msg.get('id')}: {msg.get('snippet', '')[:80]}")
    elif action == "search":
        query = sys.argv[2] if len(sys.argv) > 2 else input("Query: ")
        results = gmail.search_emails(query)
        print(f"Found {len(results)} messages:")
        for msg in results:
            print(f"  {msg.get('id')}: {msg.get('snippet', '')[:80]}")
    else:
        print("Usage: python gmail.py <send|read|search> [args...]")