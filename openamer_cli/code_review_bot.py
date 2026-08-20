"""
CI/CD Code Review Bot — reviews GitHub PRs and diffs programmatically.

Provides the ``CodeReviewBot`` class that can:
- Fetch PR diffs from GitHub via the GitHub API.
- Review a raw diff text for common issues.
- Generate structured review comments (inline code review).
- Post review comments as a PR review via the GitHub API.
- Run in CI mode reading GitHub Actions event data.

Environment variables used:
    GITHUB_TOKEN / GITHUB_API_TOKEN — GitHub personal access token.
    GH_EVENT_PATH                  — Local path to the GitHub event payload
                                    (GitHub Actions GITHUB_EVENT_PATH).
    CI                             — Set to 'true' in CI; enables CI mode.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote


# ── Data models ──────────────────────────────────────────────────────────────


@dataclass
class ReviewComment:
    """An inline review comment on a specific line of a diff."""

    path: str
    line: int
    body: str
    side: str = "RIGHT"  # LEFT (old) or RIGHT (new) side of the diff

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ReviewResult:
    """Result of a full PR review."""

    summary: str
    score: int  # 0-10, 10 = clean
    comments: List[ReviewComment] = field(default_factory=list)
    issues: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    strengths: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "summary": self.summary,
            "score": self.score,
            "comments": [c.to_dict() for c in self.comments],
            "issues": self.issues,
            "suggestions": self.suggestions,
            "strengths": self.strengths,
        }


# ── Diff parsing helpers ─────────────────────────────────────────────────────


def _parse_diff_hunks(diff_text: str) -> List[dict]:
    """Parse a unified diff into hunks with line numbers."""
    hunks: List[dict] = []
    current_hunk: Optional[dict] = None

    for line in diff_text.splitlines(keepends=True):
        hunk_match = re.match(r"^@@ -(\d+),?(\d*) \+(\d+),?(\d*) @@", line)
        if hunk_match:
            if current_hunk and current_hunk["lines"]:
                hunks.append(current_hunk)
            old_start = int(hunk_match.group(1))
            old_count = int(hunk_match.group(2)) if hunk_match.group(2) else 1
            new_start = int(hunk_match.group(3))
            new_count = int(hunk_match.group(4)) if hunk_match.group(4) else 1
            current_hunk = {
                "old_start": old_start,
                "old_count": old_count,
                "new_start": new_start,
                "new_count": new_count,
                "lines": [],
            }
            continue

        if current_hunk is not None:
            if line.startswith("+") and not line.startswith("+++"):
                current_hunk["lines"].append(("+", line[1:]))
            elif line.startswith("-") and not line.startswith("---"):
                current_hunk["lines"].append(("-", line[1:]))
            elif not line.startswith("---") and not line.startswith("+++"):
                current_hunk["lines"].append((" ", line))

    if current_hunk and current_hunk["lines"]:
        hunks.append(current_hunk)

    return hunks


def _get_file_paths_from_diff(diff_text: str) -> List[str]:
    """Extract file paths from a diff header (--- a/... / +++ b/...)."""
    paths: List[str] = []
    for line in diff_text.splitlines():
        if line.startswith("+++ b/"):
            path = line[6:].strip()
            if path and path != "/dev/null":
                paths.append(path)
    return paths


# ── Review rules ──────────────────────────────────────────────────────────────


def _check_hardcoded_secrets(diff_text: str) -> List[Tuple[str, int, str]]:
    """Check for potential secrets leaked in a diff."""
    findings: List[Tuple[str, int, str]] = []
    secret_patterns = [
        ('(?i)(api[_-]?key|apikey)\\s*[:=]\\s*["\'].{8,}["\']', "Possible API key leak"),
        ('(?i)(password|passwd|secret)\\s*[:=]\\s*["\'].{4,}["\']', "Possible password/secret leak"),
        ('(?i)(token|auth_token|bearer)\\s*[:=]\\s*["\'].{8,}["\']', "Possible token leak"),
        ('(?i)(-----BEGIN\\s+(RSA\\s+)?PRIVATE\\s+KEY-----)', "Private key embedded in code"),
        ('(?i)(ghp_|gho_|github_pat_)[a-zA-Z0-9]{36,}', "GitHub token pattern detected"),
        ('(?i)(sk-[a-zA-Z0-9]{20,})', "OpenAI API key pattern detected"),
    ]

    current_file = ""
    for i, line in enumerate(diff_text.splitlines(), 1):
        if line.startswith("+++ b/"):
            current_file = line[6:].strip()
        if line.startswith("+") and not line.startswith("+++"):
            for pattern, msg in secret_patterns:
                if re.search(pattern, line):
                    findings.append((current_file, i, msg))
                    break
    return findings


def _check_large_files(diff_text: str) -> List[Tuple[str, int, str]]:
    """Flag files that change more than a reasonable number of lines."""
    findings: List[Tuple[str, int, str]] = []
    current_file = ""
    added = 0

    for line in diff_text.splitlines():
        if line.startswith("+++ b/"):
            if current_file and added > 300:
                findings.append(
                    (current_file, 0, "Large diff: {0} lines added (consider splitting up)".format(added))
                )
            current_file = line[6:].strip()
            added = 0
        elif line.startswith("+") and not line.startswith("+++"):
            added += 1

    if current_file and added > 300:
        findings.append(
            (current_file, 0, "Large diff: {0} lines added (consider splitting up)".format(added))
        )
    return findings


def _check_missing_error_handling(diff_text: str) -> List[Tuple[str, int, str]]:
    """Flag bare ``except:`` and bare ``assert`` patterns."""
    findings: List[Tuple[str, int, str]] = []
    current_file = ""
    for i, line in enumerate(diff_text.splitlines(), 1):
        if line.startswith("+++ b/"):
            current_file = line[6:].strip()
        added = line.startswith("+") and not line.startswith("+++")
        if added:
            stripped = line.lstrip("+").strip()
            if re.match(r"^except\s*:", stripped):
                findings.append((current_file, i, "Bare except: catches all exceptions silently"))
            if re.match(r"^except\s+Exception\s*,\s*e\s*:\s*pass$", stripped):
                findings.append((current_file, i, "Silent pass in exception handler"))
            if re.match(r"^assert\s+", stripped) and "TODO" in stripped:
                findings.append((current_file, i, "Assertion marked as TODO"))
    return findings


def _check_debug_code(diff_text: str) -> List[Tuple[str, int, str]]:
    """Flag leftover debug print/log statements."""
    findings: List[Tuple[str, int, str]] = []
    current_file = ""
    debug_patterns = [
        r'\bprint\s*\(',
        r'\bconsole\.log\s*\(',
        r'\bconsole\.debug\s*\(',
        r'\bconsole\.dir\s*\(',
        r'\bpprint\s*\(',
        r'\blogger\.debug\s*\(',
        r'#\s*TODO\b',
        r'FIXME\b',
        r'\bimport\s+pdb\b',
        r'\bpdb\.set_trace\b',
        r'\bdebugger\b',
    ]
    for i, line in enumerate(diff_text.splitlines(), 1):
        if line.startswith("+++ b/"):
            current_file = line[6:].strip()
        added = line.startswith("+") and not line.startswith("+++")
        if added and not _is_comment_only(line):
            for pattern in debug_patterns:
                if re.search(pattern, line):
                    pname = pattern.replace("\\b", "").replace("\\\\b", "")
                    findings.append((current_file, i, "Debug artifact: {0}".format(pname)))
                    break
    return findings


def _is_comment_only(line: str) -> bool:
    """Check if a line (stripped) is just a comment."""
    stripped = line.lstrip("+ ").strip()
    return stripped.startswith("#") or stripped.startswith("//") or stripped.startswith("/*")


def _check_import_wildcards(diff_text: str) -> List[Tuple[str, int, str]]:
    """Flag wildcard imports (from module import *)."""
    findings: List[Tuple[str, int, str]] = []
    current_file = ""
    for i, line in enumerate(diff_text.splitlines(), 1):
        if line.startswith("+++ b/"):
            current_file = line[6:].strip()
        if line.startswith("+") and not line.startswith("+++"):
            if re.search(r"^\s*from\s+\S+\s+import\s+\*\s*$", line.lstrip("+"), re.IGNORECASE):
                findings.append((current_file, i, "Wildcard import - pollutes namespace"))
    return findings


# ── GitHub API helpers ────────────────────────────────────────────────────────


def get_github_token() -> str:
    """Return a GitHub API token from environment.

    Raises:
        RuntimeError: If no token is found.
    """
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GITHUB_API_TOKEN") or ""
    if not token:
        raise RuntimeError(
            "GitHub token not found. Set GITHUB_TOKEN or GITHUB_API_TOKEN."
        )
    return token


def _github_api_get(url: str, token: str) -> Any:
    """Perform a GET request to the GitHub API using curl."""
    try:
        result = subprocess.run(
            [
                "curl", "-s",
                "-H", "Authorization: Bearer {0}".format(token),
                "-H", "Accept: application/vnd.github.v3.diff",
                url,
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            raise RuntimeError("curl failed (exit {0}): {1}".format(result.returncode, result.stderr))
        return result.stdout
    except FileNotFoundError:
        raise RuntimeError("curl not found - required for GitHub API calls") from None
    except subprocess.TimeoutExpired:
        raise RuntimeError("GitHub API request timed out") from None


def _github_api_post(url: str, token: str, data: dict) -> Any:
    """Perform a POST request to the GitHub API using curl."""
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
    try:
        json.dump(data, tmp)
        tmp.close()
        result = subprocess.run(
            [
                "curl", "-s", "-X", "POST",
                "-H", "Authorization: Bearer {0}".format(token),
                "-H", "Accept: application/vnd.github.v3+json",
                "-H", "Content-Type: application/json",
                "-d", "@{0}".format(tmp.name),
                url,
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.stdout
    finally:
        os.unlink(tmp.name)


# ── Public API ────────────────────────────────────────────────────────────────


class CodeReviewBot:
    """Reviews GitHub PRs and diffs, generating structured code review feedback.

    Usage:
        bot = CodeReviewBot()
        result = bot.review_pr(42, "owner/repo")
        comments = bot.generate_review_comments(result.to_dict())
        bot.post_review_to_github(comments, 42, "owner/repo")
    """

    def __init__(self, token: Optional[str] = None) -> None:
        self.token = token or get_github_token()
        self._engine: Any = None
        try:
            from openamer_cli.lint_fix import LintFixEngine
            self._engine = LintFixEngine()
        except ImportError:
            pass

    def review_pr(self, pr_number: int, repo: str) -> ReviewResult:
        """Fetch PR diff from GitHub and return a full review.

        Args:
            pr_number: The PR number (e.g. 42).
            repo: Repository in ``owner/name`` format (e.g. ``openamer/openamer``).

        Returns:
            A ``ReviewResult`` with summary, score, comments, issues, suggestions,
            and strengths.
        """
        diff_url = "https://api.github.com/repos/{0}/pulls/{1}".format(repo, pr_number)
        full_token = self.token

        try:
            result = subprocess.run(
                [
                    "curl", "-s",
                    "-H", "Authorization: Bearer {0}".format(full_token),
                    "-H", "Accept: application/vnd.github.v3.diff",
                    diff_url,
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode != 0:
                raise RuntimeError("curl failed (exit {0}): {1}".format(result.returncode, result.stderr))
            diff_text = result.stdout
        except FileNotFoundError:
            raise RuntimeError("curl not found - required for GitHub API calls") from None
        except subprocess.TimeoutExpired:
            raise RuntimeError("GitHub API request timed out") from None

        if not diff_text.strip() or diff_text.strip().startswith("{"):
            try:
                err = json.loads(diff_text)
                msg = err.get("message", "Unknown GitHub API error")
                raise RuntimeError("GitHub API error: {0}".format(msg))
            except json.JSONDecodeError:
                pass

        file_paths = _get_file_paths_from_diff(diff_text)
        if not file_paths:
            return ReviewResult(
                summary="No changes detected or diff is empty.",
                score=10,
            )

        comments = self.review_diff(diff_text)
        issues: List[str] = []
        suggestions: List[str] = []
        strengths: List[str] = []

        lint_info: List[str] = []
        for fp in file_paths:
            try:
                full_path = "/tmp/" + fp
                if self._engine and Path(full_path).exists():
                    lint_issues = self._engine.run_lint(full_path)
                    if lint_issues:
                        lint_info.append("{0}: {1} lint issue(s)".format(fp, len(lint_issues)))
            except (ValueError, RuntimeError, FileNotFoundError):
                pass

        for c in comments:
            body = c.body
            if body.startswith("\u26a0\ufe0f") or body.startswith("\U0001f534"):
                issues.append("{0}:{1} - {2}".format(c.path, c.line, body))
            elif body.startswith("\U0001f4a1"):
                suggestions.append("{0}:{1} - {2}".format(c.path, c.line, body))
            elif body.startswith("\u2705") or body.startswith("\U0001f44d"):
                strengths.append("{0}:{1} - {2}".format(c.path, c.line, body))

        total_issues = len(issues)
        total_suggestions = len(suggestions)
        score = max(0, min(10, 10 - total_issues // 2))
        fnames = ", ".join(fp.split("/")[-1] for fp in file_paths[:5])
        summary_parts = [
            "Reviewed {0} file(s): {1}.".format(len(file_paths), fnames),
        ]
        if total_issues:
            summary_parts.append("{0} issue(s) found.".format(total_issues))
        if total_suggestions:
            summary_parts.append("{0} suggestion(s).".format(total_suggestions))
        if lint_info:
            summary_parts.append("Lint: {0}".format("; ".join(lint_info)))

        return ReviewResult(
            summary=" ".join(summary_parts),
            score=score,
            comments=comments,
            issues=issues,
            suggestions=suggestions,
            strengths=strengths,
        )

    def review_diff(self, diff_text: str) -> List[ReviewComment]:
        """Review a raw diff text and return inline comments.

        Applies pattern-based checks:

        Returns:
            A list of ``ReviewComment`` objects with path, line, body, and side.
        """
        comments: List[ReviewComment] = []

        checks = [
            ("secrets", _check_hardcoded_secrets(diff_text)),
            ("large_files", _check_large_files(diff_text)),
            ("error_handling", _check_missing_error_handling(diff_text)),
            ("debug_code", _check_debug_code(diff_text)),
            ("wildcard_imports", _check_import_wildcards(diff_text)),
        ]

        for check_name, findings in checks:
            for path, line, msg in findings:
                if check_name == "secrets":
                    emoji = "\U0001f534"
                elif check_name in ("debug_code", "wildcard_imports"):
                    emoji = "\U0001f4a1"
                else:
                    emoji = "\u26a0\ufe0f"

                comments.append(ReviewComment(
                    path=path or "unknown",
                    line=max(1, line),
                    body="{0} **{1}**: {2}".format(
                        emoji, check_name.replace("_", " ").title(), msg
                    ),
                    side="RIGHT",
                ))

        if not comments:
            file_paths = _get_file_paths_from_diff(diff_text)
            for fp in file_paths:
                comments.append(ReviewComment(
                    path=fp,
                    line=1,
                    body="\u2705 No issues detected in this file.",
                    side="RIGHT",
                ))

        return comments

    def generate_review_comments(self, review: dict) -> List[dict]:
        """Convert a ``ReviewResult`` dict into GitHub API-compatible review comments.

        Each comment dict has keys: path, line, body, side.
        """
        comments: List[dict] = []
        raw_comments = review.get("comments", [])
        if isinstance(raw_comments, list) and raw_comments:
            for c in raw_comments:
                if isinstance(c, dict):
                    comments.append(c)
                elif hasattr(c, "to_dict"):
                    comments.append(c.to_dict())
        else:
            for issue in review.get("issues", []):
                parts = issue.split(" - ", 1)
                if len(parts) == 2:
                    location, body = parts
                    if ":" in location:
                        path, line_str = location.rsplit(":", 1)
                        comments.append({
                            "path": path,
                            "line": int(line_str) if line_str.isdigit() else 1,
                            "body": body,
                            "side": "RIGHT",
                        })
            for suggestion in review.get("suggestions", []):
                parts = suggestion.split(" - ", 1)
                if len(parts) == 2:
                    location, body = parts
                    if ":" in location:
                        path, line_str = location.rsplit(":", 1)
                        comments.append({
                            "path": path,
                            "line": int(line_str) if line_str.isdigit() else 1,
                            "body": "Suggestion: {0}".format(body),
                            "side": "RIGHT",
                        })

        return comments

    def post_review_to_github(
        self, comments: List[dict], pr_number: int, repo: str
    ) -> dict:
        """Post a review with inline comments via the GitHub API.

        Uses the ``repos/{repo}/pulls/{pr_number}/reviews`` endpoint.

        Returns:
            The parsed JSON response from GitHub.
        """
        url = "https://api.github.com/repos/{0}/pulls/{1}/reviews".format(repo, pr_number)

        body_lines = [
            "## OpenAmer Code Review Bot",
        ]
        if comments:
            body_lines.append("Found **{0}** item(s) to review.".format(len(comments)))
        else:
            body_lines.append("No issues detected - code looks clean!")

        review_body = "\n".join(body_lines)

        payload: dict = {
            "event": "COMMENT",
            "body": review_body,
        }

        if comments:
            payload["comments"] = []
            for cmt in comments:
                gh_comment = {
                    "path": cmt.get("path", "unknown"),
                    "body": cmt.get("body", ""),
                    "line": cmt.get("line", 1),
                }
                side = cmt.get("side", "RIGHT")
                if side in ("LEFT", "RIGHT"):
                    gh_comment["side"] = side
                payload["comments"].append(gh_comment)

        raw = _github_api_post(url, self.token, payload)
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {"raw_response": raw, "note": "Non-JSON response from GitHub API"}

    def run_code_review_ci(self) -> ReviewResult:
        """Run code review in CI mode.

        Reads environment variables set by GitHub Actions:
            - GITHUB_EVENT_PATH: path to the event payload JSON
            - CI: should be 'true'

        If GITHUB_EVENT_PATH is set and points to a pull_request event,
        it extracts the PR number and reviews that PR automatically.

        If no PR event is found, reviews the diff against the working tree
        using ``git diff``.

        Returns:
            A ``ReviewResult``.
        """
        event_path = os.environ.get("GITHUB_EVENT_PATH", "")
        is_ci = os.environ.get("CI", "").lower() in ("true", "1", "yes")

        if event_path and Path(event_path).exists():
            try:
                with open(event_path, "r") as fh:
                    event = json.load(fh)
            except (json.JSONDecodeError, OSError):
                event = {}

            pr_number = None
            repo_full = ""
            if "pull_request" in event:
                pr_number = event["pull_request"].get("number")
                repo_full = (
                    event.get("repository", {}).get("full_name", "")
                    or os.environ.get("GITHUB_REPOSITORY", "")
                )
            elif "issue" in event and "pull_request" in event.get("issue", {}):
                pr_number = event["issue"].get("number")
                repo_full = (
                    event.get("repository", {}).get("full_name", "")
                    or os.environ.get("GITHUB_REPOSITORY", "")
                )

            if pr_number and repo_full:
                return self.review_pr(pr_number, repo_full)

        if is_ci or event_path:
            try:
                result = subprocess.run(
                    ["git", "diff", "HEAD~1", "--"],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                if result.returncode == 0 and result.stdout.strip():
                    comments = self.review_diff(result.stdout)
                    file_paths = _get_file_paths_from_diff(result.stdout)
                    issues = []
                    for c in comments:
                        issues.append("{0}:{1} - {2}".format(c.path, c.line, c.body))
                    score = max(0, min(10, 10 - len(issues) // 2))
                    return ReviewResult(
                        summary="Reviewed {0} file(s) from local diff. {1} item(s) found.".format(
                            len(file_paths), len(issues)
                        ),
                        score=score,
                        comments=comments,
                        issues=issues,
                    )
                else:
                    return ReviewResult(
                        summary="No diff found to review (empty or no previous commit).",
                        score=10,
                    )
            except (FileNotFoundError, subprocess.TimeoutExpired):
                return ReviewResult(
                    summary="Could not run git diff - not in a git repo or git not available.",
                    score=10,
                )

        return ReviewResult(
            summary="CI mode: no GitHub event payload and no local diff available.",
            score=10,
        )