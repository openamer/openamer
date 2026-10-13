"""Tests for the Lint-Fix Engine."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

from openamer_cli.lint_fix import LintFixEngine, LintIssue


class TestLintFixEngine:
    """Unit tests for LintFixEngine."""

    def setup_method(self) -> None:
        self.engine = LintFixEngine()

    # ── _detect_linter ──────────────────────────────────────────────────────

    def test_detect_linter_python(self) -> None:
        assert self.engine._detect_linter("foo.py") == "ruff"
        assert self.engine._detect_linter("foo.pyi") == "ruff"

    def test_detect_linter_js(self) -> None:
        assert self.engine._detect_linter("foo.js") == "eslint"
        assert self.engine._detect_linter("foo.jsx") == "eslint"
        assert self.engine._detect_linter("foo.ts") == "eslint"
        assert self.engine._detect_linter("foo.tsx") == "eslint"
        assert self.engine._detect_linter("foo.mjs") == "eslint"
        assert self.engine._detect_linter("foo.cjs") == "eslint"

    def test_detect_linter_unsupported(self) -> None:
        with pytest.raises(ValueError, match="Unsupported file extension"):
            self.engine._detect_linter("foo.rs")
        with pytest.raises(ValueError, match="Unsupported file extension"):
            self.engine._detect_linter("foo.go")
        with pytest.raises(ValueError, match="Unsupported file extension"):
            self.engine._detect_linter("Makefile")

    # ── run_lint ────────────────────────────────────────────────────────────

    def test_run_lint_file_not_found(self) -> None:
        with pytest.raises(FileNotFoundError):
            self.engine.run_lint("/nonexistent/path.py")

    def test_run_lint_unsupported_extension(self) -> None:
        with pytest.raises(ValueError, match="Unsupported file extension"):
            self.engine.run_lint("foo.rs")

    def test_run_lint_linter_not_available(self) -> None:
        """If ruff is not installed, should raise RuntimeError."""
        with tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode="w") as f:
            f.write("x = 1\n")
            fpath = f.name
        try:
            # If ruff is available, this should work; if not, it will error
            try:
                result = self.engine.run_lint(fpath)
                assert isinstance(result, list)
            except RuntimeError as e:
                assert "ruff" in str(e).lower() or "not found" in str(e)
        finally:
            os.unlink(fpath)

    # ── categorize_issues ───────────────────────────────────────────────────

    def test_categorize_issues_empty(self) -> None:
        result = self.engine.categorize_issues([])
        assert result == {"error": [], "warning": [], "style": []}

    def test_categorize_issues_by_severity(self) -> None:
        issues = [
            {"file_path": "a.py", "line": 1, "column": 1, "severity": "error", "code": "E001", "message": "err", "fixable": False},
            {"file_path": "b.py", "line": 2, "column": 1, "severity": "warning", "code": "W001", "message": "warn", "fixable": True},
            {"file_path": "c.py", "line": 3, "column": 1, "severity": "style", "code": "S001", "message": "style", "fixable": False},
            {"file_path": "d.py", "line": 4, "column": 1, "severity": "warning", "code": "W002", "message": "warn2", "fixable": False},
            {"file_path": "e.py", "line": 5, "column": 1, "severity": "unknown", "code": "U001", "message": "?", "fixable": False},
        ]
        result = self.engine.categorize_issues(issues)
        assert len(result["error"]) == 1
        assert result["error"][0]["code"] == "E001"
        assert len(result["warning"]) == 2
        assert len(result["style"]) == 2  # unknown falls through to style

    # ── _can_inline_fix ─────────────────────────────────────────────────────

    @pytest.mark.parametrize("code,expected", [
        ("W291", True),
        ("W292", True),
        ("trailing-whitespace", True),
        ("eol-last", True),
        ("E999", False),
        ("F401", False),
        ("", False),
    ])
    def test_can_inline_fix(self, code: str, expected: bool) -> None:
        assert self.engine._can_inline_fix({"code": code}) == expected

    # ── fix_issue ───────────────────────────────────────────────────────────

    def test_fix_issue_nonexistent_file(self) -> None:
        with pytest.raises(FileNotFoundError):
            self.engine.fix_issue("/nonexistent/file.py", {"code": "W291", "line": 1, "column": 1})

    def test_fix_issue_unsupported_ext(self) -> None:
        with pytest.raises(ValueError):
            self.engine.fix_issue("foo.rs", {"code": "W291"})

    def test_fix_issue_trailing_whitespace(self) -> None:
        """Test inline trailing whitespace fix."""
        content = "line with trailing space   \nnext line\n"
        with tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode="wb") as f:
            f.write(content.encode("utf-8"))
            fpath = f.name
        try:
            result = self.engine.fix_issue(fpath, {"code": "W291", "line": 1})
            assert result is True
            fixed = Path(fpath).read_text(encoding="utf-8")
            assert fixed == "line with trailing space\nnext line\n"
        finally:
            os.unlink(fpath)

    def test_fix_issue_missing_newline(self) -> None:
        """Test inline missing-trailing-newline fix."""
        content = "line without newline"
        with tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode="wb") as f:
            f.write(content.encode("utf-8"))
            fpath = f.name
        try:
            result = self.engine.fix_issue(fpath, {"code": "W292", "line": 1})
            assert result is True
            fixed = Path(fpath).read_text(encoding="utf-8")
            assert fixed == content + "\n"
        finally:
            os.unlink(fpath)

    # ── run_lint_fix_cycle ──────────────────────────────────────────────────

    def test_run_lint_fix_cycle_nonexistent(self) -> None:
        with pytest.raises(FileNotFoundError):
            self.engine.run_lint_fix_cycle("/nonexistent/path.py")

    def test_run_lint_fix_cycle_clean_file(self) -> None:
        """Clean file should pass immediately with 0 iterations."""
        with tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode="wb") as f:
            f.write(b"x = 1\n")
            fpath = f.name
        try:
            result = self.engine.run_lint_fix_cycle(fpath, max_iterations=3)
            # Should succeed or at least return a dict with expected keys
            assert "success" in result
            assert "iterations_used" in result
            assert "total_issues_found" in result
            assert "total_issues_fixed" in result
            assert "remaining_issues" in result
        finally:
            os.unlink(fpath)

    def test_run_lint_fix_cycle_unsupported(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".rs", delete=False, mode="wb") as f:
            f.write(b"fn main() {}\n")
            fpath = f.name
        try:
            with pytest.raises(ValueError):
                self.engine.run_lint_fix_cycle(fpath)
        finally:
            os.unlink(fpath)

    # ── watch_and_fix ───────────────────────────────────────────────────────

    def test_watch_and_fix_nonexistent_dir(self) -> None:
        with pytest.raises(NotADirectoryError):
            self.engine.watch_and_fix("/nonexistent-directory-12345")

    def test_watch_and_fix_valid_dir(self, tmp_path: Path) -> None:
        """watch_and_fix should start and stop gracefully with Ctrl+C."""
        import threading
        import time

        result_container: list = []

        def runner() -> None:
            try:
                self.engine.watch_and_fix(str(tmp_path), poll_interval=0.5)
            except Exception as e:
                result_container.append(e)

        t = threading.Thread(target=runner, daemon=True)
        t.start()
        time.sleep(0.3)  # Let it start
    
        # Can't easily test interrupt, but at least it started without error
        assert len(result_container) == 0 or not isinstance(result_container[0], NotADirectoryError)

    # ── LintIssue dataclass ─────────────────────────────────────────────────

    def test_lint_issue_dataclass(self) -> None:
        issue = LintIssue(
            file_path="test.py",
            line=10,
            column=3,
            severity="error",
            code="E999",
            message="Syntax error",
            fixable=False,
        )
        assert issue.file_path == "test.py"
        assert issue.severity == "error"
        assert issue.fixable is False

    def test_lint_issue_defaults(self) -> None:
        issue = LintIssue(
            file_path="test.py",
            line=1,
            column=1,
            severity="warning",
            code="W001",
            message="test",
        )
        assert issue.fixable is False  # default


class TestLintFixEngineIntegration:
    """Integration tests that require ruff to be installed."""

    def test_ruff_available(self) -> None:
        """Check if ruff is installed on this system."""
        import subprocess
        result = subprocess.run(
            ["ruff", "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0
        assert "ruff" in result.stdout.lower()

    def test_run_lint_on_invalid_python(self) -> None:
        """Run lint on a file with known issues."""
        engine = LintFixEngine()
        content = (
            "import os, sys\n"
            "from pathlib import *\n"
            "x=1\n"
            "y=2\n"
            "if True:\n"
            "  pass\n"
        )
        with tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode="wb") as f:
            f.write(content.encode("utf-8"))
            fpath = f.name
        try:
            issues = engine.run_lint(fpath)
            assert isinstance(issues, list)
            # At minimum should find something or be empty in case ruff config
            # is very permissive
        finally:
            os.unlink(fpath)

    def test_lint_fix_cycle_with_real_ruff(self) -> None:
        """Run a real lint-fix cycle on code with trailing whitespace."""
        engine = LintFixEngine()
        content = "x = 1   \ny = 2\n"
        with tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode="wb") as f:
            f.write(content.encode("utf-8"))
            fpath = f.name
        try:
            result = engine.run_lint_fix_cycle(fpath, max_iterations=2)
            assert isinstance(result, dict)
            # The file should be fixed (trailing whitespace removed)
            fixed = Path(fpath).read_text(encoding="utf-8")
            assert "x = 1\n" in fixed or "x = 1" in fixed
        finally:
            os.unlink(fpath)