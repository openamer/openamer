"""
openamer_cli.integrations — Enterprise Integration connectors.

Provides OAuth2 / API-key-based integrations for Gmail, Jira, Linear,
and Calendar services. Each integration class detects missing credentials
at instantiation time and raises a clear, actionable :class:`CredentialError`.

Usage::

    from openamer_cli.integrations import GmailIntegration, JiraIntegration
    gmail = GmailIntegration()  # raises if env vars not set
    gmail.send_email(to="user@example.com", subject="Hello", body="World")
"""

from __future__ import annotations

from openamer_cli.integrations.calendar import CalendarIntegration
from openamer_cli.integrations.gmail import GmailIntegration
from openamer_cli.integrations.jira import JiraIntegration
from openamer_cli.integrations.linear import LinearIntegration

__all__ = [
    "GmailIntegration",
    "JiraIntegration",
    "LinearIntegration",
    "CalendarIntegration",
]