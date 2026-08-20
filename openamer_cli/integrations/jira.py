"""
Jira Integration — create and query Jira issues via the Jira REST API.

Uses HTTP Basic Auth or Personal Access Token from environment variables:

* ``JIRA_BASE_URL`` — e.g. ``https://your-domain.atlassian.net``
* ``JIRA_EMAIL`` — email used for Basic Auth
* ``JIRA_API_TOKEN`` — Jira API token (Atlassian account → API tokens)
  OR ``JIRA_PAT`` — Jira Personal Access Token (for Jira Cloud / Data Center)
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

# ---------------------------------------------------------------------------
# Error types
# ---------------------------------------------------------------------------


class CredentialError(Exception):
    """Raised when a required credential is missing or invalid."""


class JiraAPIError(Exception):
    """Raised when the Jira API returns an error."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _require_env(name: str) -> str:
    """Return *name* from the environment or raise :class:`CredentialError`."""
    val = os.environ.get(name)
    if not val:
        raise CredentialError(
            f"Jira integration requires {name!r} to be set in the environment. "
            f"Set it in your .env file or export it before running OpenAmer."
        )
    return val


def _build_headers() -> dict[str, str]:
    """Build HTTP Authorization header from env vars.

    Prefers ``JIRA_PAT`` (Personal Access Token) when set; falls back to
    ``JIRA_EMAIL`` + ``JIRA_API_TOKEN`` (Basic Auth).
    """
    base_url = _require_env("JIRA_BASE_URL")
    pat = os.environ.get("JIRA_PAT")
    if pat:
        return {
            "Authorization": f"Bearer {pat}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
    email = _require_env("JIRA_EMAIL")
    api_token = _require_env("JIRA_API_TOKEN")
    import base64

    token = base64.b64encode(f"{email}:{api_token}".encode()).decode("ascii")
    return {
        "Authorization": f"Basic {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


# ---------------------------------------------------------------------------
# Integration class
# ---------------------------------------------------------------------------


class JiraIntegration:
    """Create and query Jira issues via the Jira REST API.

    Usage::

        jira = JiraIntegration()
        issue = jira.create_issue("PROJ", "Summary", "Description")
        info = jira.get_issue("PROJ-123")
        results = jira.search_issues("project = PROJ AND status != Done")
    """

    def __init__(self) -> None:
        self._base_url = _require_env("JIRA_BASE_URL").rstrip("/")
        self._headers = _build_headers()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _request(
        self, method: str, path: str, body: dict[str, Any] | None = None
    ) -> Any:
        """Perform a JSON API request and return the parsed response."""
        url = f"{self._base_url}{path}"
        data = json.dumps(body).encode("utf-8") if body is not None else None
        req = urllib.request.Request(
            url, data=data, headers=self._headers, method=method
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = ""
            try:
                detail = exc.read().decode("utf-8", errors="replace")
            except Exception:
                detail = str(exc)
            raise JiraAPIError(
                f"Jira API error {exc.code} on {method} {path}: {detail}"
            ) from exc
        except urllib.error.URLError as exc:
            raise JiraAPIError(
                f"Failed to reach Jira at {self._base_url}: {exc.reason}"
            ) from exc

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def create_issue(
        self,
        project: str,
        summary: str,
        description: str,
        issue_type: str = "Task",
    ) -> dict[str, Any]:
        """Create a Jira issue.

        Args:
            project: Project key (e.g. ``\"PROJ\"``).
            summary: Issue summary / title.
            description: Issue description (Atlassian Document Format or plain text).
            issue_type: Issue type name (default ``\"Task\"``).

        Returns:
            The created issue dict with ``id``, ``key``, and ``self`` links.

        Raises:
            JiraAPIError: On API failure.
        """
        body: dict[str, Any] = {
            "fields": {
                "project": {"key": project},
                "summary": summary,
                "description": {
                    "type": "doc",
                    "version": 1,
                    "content": [
                        {
                            "type": "paragraph",
                            "content": [
                                {"type": "text", "text": description}
                            ],
                        }
                    ],
                },
                "issuetype": {"name": issue_type},
            }
        }
        result = self._request("POST", "/rest/api/3/issue", body=body)
        return result  # type: ignore[return-value]

    def get_issue(self, key: str) -> dict[str, Any]:
        """Get a Jira issue by its key (e.g. ``\"PROJ-123\"``).

        Args:
            key: Issue key.

        Returns:
            The full issue dict (all fields).

        Raises:
            JiraAPIError: On API failure.
        """
        result = self._request("GET", f"/rest/api/3/issue/{key}")
        return result  # type: ignore[return-value]

    def search_issues(self, jql_query: str) -> list[dict[str, Any]]:
        """Search issues using JQL.

        Args:
            jql_query: JQL query string (e.g. ``\"project = PROJ AND status != Done\"``).

        Returns:
            List of matching issue dicts.

        Raises:
            JiraAPIError: On API failure.
        """
        body = {"jql": jql_query, "maxResults": 50}
        result = self._request("POST", "/rest/api/3/search", body=body)
        return result.get("issues", [])  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# CLI convenience
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    try:
        jira = JiraIntegration()
    except CredentialError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        sys.exit(1)

    action = sys.argv[1] if len(sys.argv) > 1 else "help"

    if action == "create":
        project = sys.argv[2] if len(sys.argv) > 2 else input("Project: ")
        summary = sys.argv[3] if len(sys.argv) > 3 else input("Summary: ")
        description = sys.argv[4] if len(sys.argv) > 4 else input("Description: ")
        issue_type = sys.argv[5] if len(sys.argv) > 5 else "Task"
        issue = jira.create_issue(project, summary, description, issue_type)
        print(f"Created: {issue.get('key')} — {issue.get('self')}")
    elif action == "get":
        key = sys.argv[2] if len(sys.argv) > 2 else input("Issue key: ")
        issue = jira.get_issue(key)
        print(json.dumps(issue, indent=2, default=str))
    elif action == "search":
        jql = sys.argv[2] if len(sys.argv) > 2 else input("JQL: ")
        issues = jira.search_issues(jql)
        for iss in issues:
            print(f"  {iss.get('key')}: {iss.get('fields', {}).get('summary', '')}")
    else:
        print("Usage: python jira.py <create|get|search> [args...]")