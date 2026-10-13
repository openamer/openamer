"""
Linear Integration — create and query Linear issues via the Linear GraphQL API.

Uses a Personal API Key from the environment variable ``LINEAR_API_KEY``.
You can generate one at https://linear.app/settings/api.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

# ---------------------------------------------------------------------------
# Error types
# ---------------------------------------------------------------------------


class CredentialError(Exception):
    """Raised when a required credential is missing or invalid."""


class LinearAPIError(Exception):
    """Raised when the Linear API returns an error."""


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

LINEAR_API_URL = "https://api.linear.app/graphql"


def _require_env(name: str) -> str:
    """Return *name* from the environment or raise :class:`CredentialError`."""
    val = os.environ.get(name)
    if not val:
        raise CredentialError(
            f"Linear integration requires {name!r} to be set in the environment. "
            f"Set it in your .env file or export it before running OpenAmer."
        )
    return val


# ---------------------------------------------------------------------------
# Integration class
# ---------------------------------------------------------------------------


class LinearIntegration:
    """Create and query Linear issues via the Linear GraphQL API.

    Usage::

        linear = LinearIntegration()
        issue = linear.create_issue("TEAM_ID", "Title", "Description")
        info = linear.get_issue("ISSUE_ID")
        issues = linear.list_issues("TEAM_ID")
    """

    def __init__(self) -> None:
        self._api_key = _require_env("LINEAR_API_KEY")
        self._headers = {
            "Authorization": self._api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _graphql(self, query: str, variables: dict[str, Any] | None = None) -> Any:
        """Execute a GraphQL query/mutation and return the parsed response.

        Raises :class:`LinearAPIError` on HTTP/GraphQL errors.
        """
        body = {"query": query}
        if variables:
            body["variables"] = variables

        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            LINEAR_API_URL, data=data, headers=self._headers, method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = ""
            try:
                detail = exc.read().decode("utf-8", errors="replace")
            except Exception:
                detail = str(exc)
            raise LinearAPIError(
                f"Linear API error {exc.code}: {detail}"
            ) from exc
        except urllib.error.URLError as exc:
            raise LinearAPIError(
                f"Failed to reach Linear API: {exc.reason}"
            ) from exc

        if "errors" in result:
            msgs = "; ".join(e.get("message", str(e)) for e in result["errors"])
            raise LinearAPIError(f"Linear GraphQL error(s): {msgs}")

        return result.get("data")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def create_issue(
        self,
        team_id: str,
        title: str,
        description: str,
    ) -> dict[str, Any]:
        """Create a Linear issue.

        Args:
            team_id: Linear team ID (e.g. ``\"TEA-123\"`` or UUID).
            title: Issue title.
            description: Issue description (markdown supported).

        Returns:
            The created issue node (``id``, ``title``, ``identifier``, ``url``).

        Raises:
            LinearAPIError: On API failure.
        """
        query = """
        mutation CreateIssue($teamId: String!, $title: String!, $description: String!) {
            issueCreate(input: {
                teamId: $teamId,
                title: $title,
                description: $description
            }) {
                success
                issue {
                    id
                    title
                    identifier
                    url
                }
            }
        }
        """
        variables = {
            "teamId": team_id,
            "title": title,
            "description": description,
        }
        data = self._graphql(query, variables)
        issue_create = data.get("issueCreate", {}) if data else {}
        if not issue_create.get("success"):
            raise LinearAPIError("Failed to create Linear issue")
        return issue_create.get("issue", {})  # type: ignore[return-value]

    def get_issue(self, id: str) -> dict[str, Any]:
        """Get a Linear issue by its ID.

        Args:
            id: The issue UUID or identifier.

        Returns:
            Issue node dict with ``id``, ``title``, ``description``,
            ``identifier``, ``url``, and ``state`` info.

        Raises:
            LinearAPIError: On API failure.
        """
        query = """
        query GetIssue($id: String!) {
            issue(id: $id) {
                id
                title
                description
                identifier
                url
                state {
                    id
                    name
                    type
                }
                assignee {
                    id
                    name
                    email
                }
                priority
                createdAt
                updatedAt
            }
        }
        """
        variables = {"id": id}
        data = self._graphql(query, variables)
        return data.get("issue", {}) if data else {}  # type: ignore[return-value]

    def list_issues(self, team_id: str) -> list[dict[str, Any]]:
        """List all issues in a Linear team.

        Args:
            team_id: Linear team ID (UUID).

        Returns:
            List of issue node dicts.

        Raises:
            LinearAPIError: On API failure.
        """
        query = """
        query ListIssues($teamId: String!) {
            team(id: $teamId) {
                issues(first: 50) {
                    nodes {
                        id
                        title
                        identifier
                        url
                        state {
                            id
                            name
                            type
                        }
                        priority
                        createdAt
                        updatedAt
                    }
                }
            }
        }
        """
        variables = {"teamId": team_id}
        data = self._graphql(query, variables)
        if data and data.get("team"):
            return data["team"].get("issues", {}).get("nodes", [])
        return []


# ---------------------------------------------------------------------------
# CLI convenience
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    try:
        linear = LinearIntegration()
    except CredentialError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        sys.exit(1)

    action = sys.argv[1] if len(sys.argv) > 1 else "help"

    if action == "create":
        team_id = sys.argv[2] if len(sys.argv) > 2 else input("Team ID: ")
        title = sys.argv[3] if len(sys.argv) > 3 else input("Title: ")
        description = sys.argv[4] if len(sys.argv) > 4 else input("Description: ")
        issue = linear.create_issue(team_id, title, description)
        print(f"Created: {issue.get('identifier')} — {issue.get('url')}")
    elif action == "get":
        issue_id = sys.argv[2] if len(sys.argv) > 2 else input("Issue ID: ")
        issue = linear.get_issue(issue_id)
        print(json.dumps(issue, indent=2, default=str))
    elif action == "list":
        team = sys.argv[2] if len(sys.argv) > 2 else input("Team ID: ")
        issues = linear.list_issues(team)
        print(f"Found {len(issues)} issues:")
        for iss in issues:
            print(f"  {iss.get('identifier')}: {iss.get('title')}")
    else:
        print("Usage: python linear.py <create|get|list> [args...]")