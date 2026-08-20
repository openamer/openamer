"""Tests for the CI/CD Code Review Bot."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import pytest

from openamer_cli.code_review_bot import (
    CodeReviewBot,
    ReviewComment,
    ReviewResult,
    _check_hardcoded_secrets,
    _check_large_files,
    _check_missing_error_handling,
    _check_debug_code,
    _check_import_wildcards,
    _get_file_paths_from_diff,
    _parse_diff_hunks,
    get_github_token,
)


# ── Sample diff fixtures ─────────────────────────────────────────────────────


SAMPLE_DIFF_CLEAN = """\
--- a/foo.py
+++ b/foo.py
@@ -1,3 +1,4 @@
 def hello():
-    print("old")
+    print("new")
+    return True
"""

SAMPLE_DIFF_WITH_SECRETS = """\
--- a/bar.py
+++ b/bar.py
@@ -1,3 +1,4 @@
 import os
+API_KEY = "sk-123456789012345678901234"
+SECRET = "mysecretpassword123"
"""

SAMPLE_DIFF_WITH_DEBUG = """\
--- a/baz.py
+++ b/baz.py
@@ -1,3 +1,5 @@
 def compute():
+    print("debug")
+    # TODO: refactor this
     return 42
"""

SAMPLE_DIFF_WITH_BARE_EXCEPT = """\
--- a/qux.py
+++ b/qux.py
@@ -1,3 +1,5 @@
 def safe():
+    try:
+        pass
+    except:
+        pass
"""

SAMPLE_DIFF_WITH_WILDCARD = """\
--- a/mod.py
+++ b/mod.py
@@ -1,3 +1,4 @@
+from os import *
 import sys
"""

SAMPLE_DIFF_LARGE = """\
--- a/huge.py
+++ b/huge.py
@@ -1,301 +1,602 @@
 import sys
""" + "\n".join("+print({0})".format(i) for i in range(350))


# ── Test data models ─────────────────────────────────────────────────────────


class TestReviewComment:
    def test_dataclass(self) -> None:
        c = ReviewComment(path="foo.py", line=10, body="fix this", side="RIGHT")
        assert c.path == "foo.py"
        assert c.line == 10
        assert c.side == "RIGHT"

    def test_to_dict(self) -> None:
        c = ReviewComment(path="foo.py", line=5, body="issue", side="LEFT")
        d = c.to_dict()
        assert d["path"] == "foo.py"
        assert d["line"] == 5
        assert d["side"] == "LEFT"

    def test_default_side(self) -> None:
        c = ReviewComment(path="f.py", line=1, body="ok")
        assert c.side == "RIGHT"


class TestReviewResult:
    def test_defaults(self) -> None:
        r = ReviewResult(summary="ok", score=10)
        assert r.comments == []
        assert r.issues == []
        assert r.suggestions == []
        assert r.strengths == []

    def test_to_dict(self) -> None:
        r = ReviewResult(
            summary="good",
            score=8,
            comments=[ReviewComment(path="a.py", line=1, body="nice")],
            issues=["a.py:1 - warning"],
        )
        d = r.to_dict()
        assert d["score"] == 8
        assert len(d["comments"]) == 1
        assert d["comments"][0]["path"] == "a.py"


# ── Test diff helpers ────────────────────────────────────────────────────────


class TestParseDiffHunks:
    def test_parse_simple(self) -> None:
        hunks = _parse_diff_hunks(SAMPLE_DIFF_CLEAN)
        assert len(hunks) >= 1
        assert hunks[0]["old_start"] == 1
        assert hunks[0]["new_start"] == 1

    def test_parse_empty(self) -> None:
        assert _parse_diff_hunks("") == []


class TestGetFilePathsFromDiff:
    def test_single_file(self) -> None:
        paths = _get_file_paths_from_diff(SAMPLE_DIFF_CLEAN)
        assert "foo.py" in paths

    def test_multiple_files(self) -> None:
        diff = SAMPLE_DIFF_CLEAN + SAMPLE_DIFF_WITH_SECRETS
        paths = _get_file_paths_from_diff(diff)
        assert "foo.py" in paths
        assert "bar.py" in paths

    def test_empty_diff(self) -> None:
        assert _get_file_paths_from_diff("") == []


# ── Test check functions ─────────────────────────────────────────────────────


class TestCheckHardcodedSecrets:
    def test_detects_api_key(self) -> None:
        findings = _check_hardcoded_secrets(SAMPLE_DIFF_WITH_SECRETS)
        assert len(findings) >= 1
        # At least one finding should mention API key or secret
        messages = [msg for _, _, msg in findings]
        assert any("API key" in m or "secret" in m or "token" in m for m in messages)

    def test_clean_diff_no_findings(self) -> None:
        findings = _check_hardcoded_secrets(SAMPLE_DIFF_CLEAN)
        assert len(findings) == 0


class TestCheckLargeFiles:
    def test_detects_large_file(self) -> None:
        findings = _check_large_files(SAMPLE_DIFF_LARGE)
        assert len(findings) >= 1

    def test_small_file_ok(self) -> None:
        findings = _check_large_files(SAMPLE_DIFF_CLEAN)
        assert len(findings) == 0


class TestCheckMissingErrorHandling:
    def test_detects_bare_except(self) -> None:
        findings = _check_missing_error_handling(SAMPLE_DIFF_WITH_BARE_EXCEPT)
        assert len(findings) >= 1

    def test_clean_diff_ok(self) -> None:
        findings = _check_missing_error_handling(SAMPLE_DIFF_CLEAN)
        assert len(findings) == 0


class TestCheckDebugCode:
    def test_detects_print(self) -> None:
        findings = _check_debug_code(SAMPLE_DIFF_WITH_DEBUG)
        assert len(findings) >= 1
        messages = [msg for _, _, msg in findings]
        assert any("Debug artifact" in m for m in messages)

    def test_clean_diff_ok(self) -> None:
        findings = _check_debug_code(SAMPLE_DIFF_CLEAN)
        assert len(findings) == 0


class TestCheckImportWildcards:
    def test_detects_wildcard(self) -> None:
        findings = _check_import_wildcards(SAMPLE_DIFF_WITH_WILDCARD)
        assert len(findings) >= 1

    def test_clean_diff_ok(self) -> None:
        findings = _check_import_wildcards(SAMPLE_DIFF_CLEAN)
        assert len(findings) == 0


# ── Test get_github_token ────────────────────────────────────────────────────


class TestGetGithubToken:
    def test_raises_when_missing(self) -> None:
        # Temporarily remove tokens from env
        old_token = os.environ.pop("GITHUB_TOKEN", None)
        old_api_token = os.environ.pop("GITHUB_API_TOKEN", None)
        try:
            with pytest.raises(RuntimeError, match="GitHub token not found"):
                get_github_token()
        finally:
            if old_token is not None:
                os.environ["GITHUB_TOKEN"] = old_token
            if old_api_token is not None:
                os.environ["GITHUB_API_TOKEN"] = old_api_token

    def test_uses_token(self) -> None:
        os.environ["GITHUB_TOKEN"] = "test-token-123"
        try:
            assert get_github_token() == "test-token-123"
        finally:
            os.environ.pop("GITHUB_TOKEN", None)

    def test_uses_api_token_fallback(self) -> None:
        os.environ["GITHUB_API_TOKEN"] = "fallback-token"
        try:
            assert get_github_token() == "fallback-token"
        finally:
            os.environ.pop("GITHUB_API_TOKEN", None)


# ── Test CodeReviewBot ───────────────────────────────────────────────────────


class TestCodeReviewBotInit:
    def test_init_requires_token(self) -> None:
        """Without a token in env, init raises RuntimeError."""
        old_token = os.environ.pop("GITHUB_TOKEN", None)
        old_api_token = os.environ.pop("GITHUB_API_TOKEN", None)
        try:
            with pytest.raises(RuntimeError):
                CodeReviewBot()
        finally:
            if old_token is not None:
                os.environ["GITHUB_TOKEN"] = old_token
            if old_api_token is not None:
                os.environ["GITHUB_API_TOKEN"] = old_api_token

    def test_init_with_explicit_token(self) -> None:
        bot = CodeReviewBot(token="custom-token")
        assert bot.token == "custom-token"


class TestCodeReviewBotReviewDiff:
    def test_clean_diff(self) -> None:
        bot = CodeReviewBot(token="test-token")
        comments = bot.review_diff(SAMPLE_DIFF_CLEAN)
        assert len(comments) >= 1
        # Clean diffs get a positive comment per file
        assert any("No issues" in c.body for c in comments)

    def test_detects_secrets(self) -> None:
        bot = CodeReviewBot(token="test-token")
        comments = bot.review_diff(SAMPLE_DIFF_WITH_SECRETS)
        # Should have at least one secret-related comment
        bodies = [c.body for c in comments]
        has_secret = any("secrets" in b.lower() or "API" in b for b in bodies)
        assert has_secret

    def test_detects_debug_code(self) -> None:
        bot = CodeReviewBot(token="test-token")
        comments = bot.review_diff(SAMPLE_DIFF_WITH_DEBUG)
        bodies = [c.body for c in comments]
        has_debug = any("debug" in b.lower() for b in bodies)
        assert has_debug

    def test_detects_bare_except(self) -> None:
        bot = CodeReviewBot(token="test-token")
        comments = bot.review_diff(SAMPLE_DIFF_WITH_BARE_EXCEPT)
        bodies = [c.body for c in comments]
        has_except = any("error" in b.lower() for b in bodies)
        assert has_except

    def test_detects_wildcard_import(self) -> None:
        bot = CodeReviewBot(token="test-token")
        comments = bot.review_diff(SAMPLE_DIFF_WITH_WILDCARD)
        bodies = [c.body for c in comments]
        has_wildcard = any("wildcard" in b.lower() for b in bodies)
        assert has_wildcard

    def test_detects_large_file(self) -> None:
        bot = CodeReviewBot(token="test-token")
        comments = bot.review_diff(SAMPLE_DIFF_LARGE)
        bodies = [c.body for c in comments]
        has_large = any("large" in b.lower() for b in bodies)
        assert has_large


class TestCodeReviewBotGenerateReviewComments:
    def test_generates_from_comments_list(self) -> None:
        bot = CodeReviewBot(token="test-token")
        result = ReviewResult(
            summary="test",
            score=5,
            comments=[ReviewComment(path="a.py", line=1, body="issue")],
        )
        comments = bot.generate_review_comments(result.to_dict())
        assert len(comments) >= 1
        if comments:
            assert comments[0]["path"] == "a.py"

    def test_generates_from_issues(self) -> None:
        bot = CodeReviewBot(token="test-token")
        result = {
            "summary": "test",
            "score": 5,
            "comments": [],
            "issues": ["a.py:1 - Warning: something"],
            "suggestions": [],
            "strengths": [],
        }
        comments = bot.generate_review_comments(result)
        assert len(comments) >= 1

    def test_empty_review(self) -> None:
        bot = CodeReviewBot(token="test-token")
        comments = bot.generate_review_comments({
            "summary": "ok", "score": 10, "comments": [],
            "issues": [], "suggestions": [], "strengths": [],
        })
        assert comments == []


class TestCodeReviewBotRunCodeReviewCI:
    def test_no_event_no_ci(self) -> None:
        """Without CI env vars, returns a no-op result."""
        bot = CodeReviewBot(token="test-token")
        old_ci = os.environ.pop("CI", None)
        old_event = os.environ.pop("GITHUB_EVENT_PATH", None)
        try:
            result = bot.run_code_review_ci()
            assert isinstance(result, ReviewResult)
            assert result.score == 10
        finally:
            if old_ci is not None:
                os.environ["CI"] = old_ci
            if old_event is not None:
                os.environ["GITHUB_EVENT_PATH"] = old_event

    def test_with_git_diff_fallback(self) -> None:
        """If CI is true but no event, falls back to git diff."""
        bot = CodeReviewBot(token="test-token")
        os.environ["CI"] = "true"
        old_event = os.environ.pop("GITHUB_EVENT_PATH", None)
        try:
            result = bot.run_code_review_ci()
            # May fail or succeed depending on git context — but should not crash
            assert isinstance(result, ReviewResult)
            assert result.score >= 0
        finally:
            os.environ.pop("CI", None)
            if old_event is not None:
                os.environ["GITHUB_EVENT_PATH"] = old_event

    def test_with_event_file(self) -> None:
        """With a valid event file, it attempts to parse PR info."""
        bot = CodeReviewBot(token="test-token")
        # Create a fake event payload
        event_data = {
            "pull_request": {"number": 99},
            "repository": {"full_name": "test/repo"},
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(event_data, f)
            event_path = f.name

        os.environ["GITHUB_EVENT_PATH"] = event_path
        try:
            result = bot.run_code_review_ci()
            # Should attempt API call (will fail since token is fake)
            assert isinstance(result, ReviewResult)
        finally:
            os.unlink(event_path)
            os.environ.pop("GITHUB_EVENT_PATH", None)


class TestCodeReviewBotPostReview:
    def test_post_with_api_error(self) -> None:
        """Posting with a fake token should fail but return dict."""
        bot = CodeReviewBot(token="invalid-token")
        comments = [{"path": "a.py", "line": 1, "body": "test", "side": "RIGHT"}]
        # This will fail because token is invalid
        result = bot.post_review_to_github(comments, 1, "owner/repo")
        assert isinstance(result, dict)


# ── Edge cases ────────────────────────────────────────────────────────────────


class TestEdgeCases:
    def test_empty_diff_string(self) -> None:
        bot = CodeReviewBot(token="test-token")
        comments = bot.review_diff("")
        assert isinstance(comments, list)

    def test_diff_with_binary_files(self) -> None:
        diff = """\
--- a/image.png
+++ b/image.png
@@ -1,1 +1,1 @@
-Binary file
+Binary file
"""
        bot = CodeReviewBot(token="test-token")
        comments = bot.review_diff(diff)
        assert isinstance(comments, list)

    def test_diff_with_only_deletions(self) -> None:
        diff = """\
--- a/old.py
+++ /dev/null
@@ -1,3 +0,0 @@
-def old_func():
-    pass
"""
        bot = CodeReviewBot(token="test-token")
        comments = bot.review_diff(diff)
        assert isinstance(comments, list)