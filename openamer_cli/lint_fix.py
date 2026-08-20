"""
Lint-and-Fix Engine — run linters, categorize issues, auto-fix, and watch.

Provides the ``LintFixEngine`` class that:
- Detects file type by extension and selects the appropriate linter
  (ruff for Python, eslint for JavaScript/TypeScript).
- Runs the linter and parses structured output.
- Categorizes issues by severity (error, warning, style).
- Attempts auto-fix for known fixable categories.
- Runs the full lint-fix cycle with configurable iteration limit.
- Watch mode: polls a directory for file changes and auto-fixes.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional


# ── Data models ──────────────────────────────────────────────────────────────


@dataclass
class LintIssue:
    """A single issue reported by a linter."""

    file_path: str
    line: int
    column: int
    severity: str  # "error" | "warning" | "style"
    code: str
    message: str
    fixable: bool = False


# ── Linter implementations ────────────────────────────────────────────────────


def _run_ruff(file_path: str) -> List[dict]:
    """Run ``ruff check --output-format json`` and return parsed issues."""
    try:
        result = subprocess.run(
            ["ruff", "check", "--output-format", "json", file_path],
            capture_output=True,
            text=True,
            timeout=60,
        )
    except FileNotFoundError:
        raise RuntimeError(
            "ruff not found. Install it with: pip install ruff"
        ) from None
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"ruff timed out on {file_path}") from None

    if not result.stdout.strip():
        return []

    try:
        raw = json.loads(result.stdout)
    except json.JSONDecodeError:
        return []

    issues = []
    for item in raw:
        severity = item.get("fix_availability", "")
        fixable = severity in ("fix_available", "applies_automatic_fix")

        # Map ruff severity codes
        code = item.get("code", "")
        raw_sev = item.get("severity", "warning")
        if raw_sev == "error":
            sev = "error"
        elif raw_sev == "warning":
            sev = "warning"
        else:
            sev = "style"

        issues.append(
            {
                "file_path": item.get("filename", file_path),
                "line": item.get("location", {}).get("row", 1),
                "column": item.get("location", {}).get("column", 1),
                "severity": sev,
                "code": code,
                "message": item.get("message", ""),
                "fixable": fixable,
            }
        )
    return issues


def _run_eslint(file_path: str) -> List[dict]:
    """Run ``eslint --format json`` and return parsed issues."""
    try:
        result = subprocess.run(
            ["eslint", "--format", "json", file_path],
            capture_output=True,
            text=True,
            timeout=60,
        )
    except FileNotFoundError:
        raise RuntimeError(
            "eslint not found. Install it with: npm install -g eslint"
        ) from None
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"eslint timed out on {file_path}") from None

    if not result.stdout.strip():
        return []

    try:
        raw = json.loads(result.stdout)
    except json.JSONDecodeError:
        return []

    issues = []
    for report in raw:
        file_path_from_report = report.get("filePath", file_path)
        for msg in report.get("messages", []):
            sev = msg.get("severity", 1)
            if sev == 2:
                severity = "error"
            elif sev == 1:
                severity = "warning"
            else:
                severity = "style"

            fixable = bool(msg.get("fix")) or bool(msg.get("suggestions"))
            issues.append(
                {
                    "file_path": file_path_from_report,
                    "line": msg.get("line", 1),
                    "column": msg.get("column", 1),
                    "severity": severity,
                    "code": msg.get("ruleId", ""),
                    "message": msg.get("message", ""),
                    "fixable": fixable,
                }
            )
    return issues


# ── Fix implementations ───────────────────────────────────────────────────────


def _apply_ruff_fix(file_path: str, issue: dict) -> bool:
    """Attempt to fix a ruff issue using ``ruff check --fix``.

    Returns True if ruff reported success (exit code 0), False otherwise.
    """
    try:
        result = subprocess.run(
            ["ruff", "check", "--fix", file_path],
            capture_output=True,
            text=True,
            timeout=60,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _apply_eslint_fix(file_path: str, issue: dict) -> bool:
    """Attempt to fix an eslint issue using ``eslint --fix``.

    Returns True if eslint reported success (exit code 0), False otherwise.
    """
    try:
        result = subprocess.run(
            ["eslint", "--fix", file_path],
            capture_output=True,
            text=True,
            timeout=60,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _apply_inline_fix(file_path: str, issue: dict) -> bool:
    """Inline file-fix for simple patterns that linter auto-fix can't handle.

    Covers:
    - Trailing whitespace
    - Missing trailing newline
    """
    try:
        path = Path(file_path)
        if not path.exists():
            return False
        original = path.read_text(encoding="utf-8")

        # Trailing whitespace on the offending line
        if issue.get("code") in ("W291", "trailing-whitespace"):
            lines = original.splitlines(keepends=True)
            lineno = max(0, issue.get("line", 1) - 1)
            if lineno < len(lines):
                lines[lineno] = lines[lineno].rstrip() + "\n"
            path.write_text("".join(lines), encoding="utf-8")
            return True

        # Missing trailing newline
        if issue.get("code") in ("W292", "eol-last"):
            if not original.endswith("\n"):
                path.write_text(original + "\n", encoding="utf-8")
                return True

        return False
    except (OSError, UnicodeDecodeError):
        return False


# ── Public API ────────────────────────────────────────────────────────────────


class LintFixEngine:
    """Engine that runs lint-and-fix cycles on source files.

    Detects linter based on file extension:
        .py      → ruff
        .js, .jsx, .ts, .tsx, .mjs, .cjs → eslint
        .pyi     → ruff
    """

    def __init__(self) -> None:
        self._linter_map: Dict[str, str] = {
            ".py": "ruff",
            ".pyi": "ruff",
            ".js": "eslint",
            ".jsx": "eslint",
            ".ts": "eslint",
            ".tsx": "eslint",
            ".mjs": "eslint",
            ".cjs": "eslint",
        }

    def _detect_linter(self, file_path: str) -> str:
        """Return the linter name for *file_path*, or raise ValueError."""
        ext = Path(file_path).suffix.lower()
        linter = self._linter_map.get(ext)
        if linter is None:
            raise ValueError(
                f"Unsupported file extension '{ext}' for '{file_path}'. "
                f"Supported: {', '.join(sorted(self._linter_map))}"
            )
        return linter

    def run_lint(self, file_path: str) -> List[dict]:
        """Run the appropriate linter on *file_path* and return the issue list.

        Returns:
            A list of issue dicts, each with keys:
            file_path, line, column, severity, code, message, fixable.

        Raises:
            RuntimeError: If the linter is not installed or times out.
            ValueError: If the file extension is unsupported.
        """
        # Check extension first so unsupported extensions fail with a clear
        # message even when the file doesn't exist.
        linter = self._detect_linter(file_path)
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        if linter == "ruff":
            return _run_ruff(file_path)
        elif linter == "eslint":
            return _run_eslint(file_path)
        else:
            raise ValueError(f"No handler for linter: {linter}")

    def categorize_issues(self, issues: List[dict]) -> Dict[str, List[dict]]:
        """Categorize a list of issues by severity.

        Returns:
            A dict with keys ``'error'``, ``'warning'``, ``'style'``, each
            containing the corresponding list of issues.
        """
        categories: Dict[str, List[dict]] = {
            "error": [],
            "warning": [],
            "style": [],
        }
        for issue in issues:
            sev = issue.get("severity", "style")
            if sev in categories:
                categories[sev].append(issue)
            else:
                categories["style"].append(issue)
        return categories

    def fix_issue(self, file_path: str, issue: dict) -> bool:
        """Attempt to auto-fix *issue* in *file_path*.

        First attempts the linter's own auto-fix (--fix flag), then falls
        back to inline fix patterns for common-but-trivial issues.

        Returns:
            True if the fix was applied successfully, False otherwise.
        """
        linter = self._detect_linter(file_path)

        # Try linter auto-fix first
        if linter == "ruff" and _apply_ruff_fix(file_path, issue):
            return True
        if linter == "eslint" and _apply_eslint_fix(file_path, issue):
            return True

        # Fall back to inline fix
        return _apply_inline_fix(file_path, issue)

    def run_lint_fix_cycle(
        self, file_path: str, max_iterations: int = 3
    ) -> Dict[str, Any]:
        """Run the full lint-fix cycle: lint → categorize → fix → repeat.

        Stops when no issues remain or *max_iterations* is reached.

        Returns:
            A dict with keys:
            - success: True if all issues were resolved
            - iterations_used: number of iterations run
            - total_issues_found: cumulative issues found
            - total_issues_fixed: cumulative issues fixed
            - remaining_issues: list of unfixed issues (last pass)
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        total_found = 0
        total_fixed = 0
        remaining: List[dict] = []

        for iteration in range(1, max_iterations + 1):
            issues = self.run_lint(file_path)
            if not issues:
                return {
                    "success": True,
                    "iterations_used": iteration - 1,
                    "total_issues_found": total_found,
                    "total_issues_fixed": total_fixed,
                    "remaining_issues": [],
                }

            categorized = self.categorize_issues(issues)
            total_found += len(issues)

            # Fix by priority: errors first, then warnings, then style
            priority_order = ["error", "warning", "style"]
            fixed_this_round = 0
            unfixed: List[dict] = []

            for sev in priority_order:
                for issue in categorized.get(sev, []):
                    if issue.get("fixable", False) or self._can_inline_fix(issue):
                        if self.fix_issue(file_path, issue):
                            fixed_this_round += 1
                        else:
                            unfixed.append(issue)
                    else:
                        unfixed.append(issue)

            total_fixed += fixed_this_round

            if fixed_this_round == 0:
                # No progress — stop to avoid infinite loop
                return {
                    "success": False,
                    "iterations_used": iteration,
                    "total_issues_found": total_found,
                    "total_issues_fixed": total_fixed,
                    "remaining_issues": unfixed or issues,
                }

            remaining = unfixed

        # Exhausted iterations
        return {
            "success": len(remaining) == 0,
            "iterations_used": max_iterations,
            "total_issues_found": total_found,
            "total_issues_fixed": total_fixed,
            "remaining_issues": remaining,
        }

    def _can_inline_fix(self, issue: dict) -> bool:
        """Check if an issue can be fixed inline."""
        return issue.get("code") in ("W291", "W292", "trailing-whitespace", "eol-last")

    def watch_and_fix(
        self,
        directory: str,
        poll_interval: float = 2.0,
        max_iterations: int = 3,
    ) -> None:
        """Watch *directory* for file changes and auto-fix them.

        Polls the directory every *poll_interval* seconds. When a file
        matching a supported extension is modified, runs a lint-fix cycle
        on it.

        Runs indefinitely (Ctrl+C to stop).
        """
        import hashlib

        watch_dir = Path(directory).resolve()
        if not watch_dir.is_dir():
            raise NotADirectoryError(f"Not a directory: {directory}")

        # Build initial checksums
        checksums: Dict[str, str] = {}
        for pattern in self._linter_map:
            for fpath in watch_dir.rglob(f"*{pattern}"):
                if fpath.is_file():
                    checksums[str(fpath)] = self._hash_file(str(fpath))

        print(f"👀 Watching {watch_dir} for changes (poll every {poll_interval}s)...")
        print("Press Ctrl+C to stop.")

        try:
            while True:
                time.sleep(poll_interval)
                for pattern in self._linter_map:
                    for fpath in watch_dir.rglob(f"*{pattern}"):
                        if not fpath.is_file():
                            continue
                        fpath_str = str(fpath)
                        new_hash = self._hash_file(fpath_str)
                        old_hash = checksums.get(fpath_str)
                        if new_hash != old_hash:
                            checksums[fpath_str] = new_hash
                            if old_hash is not None:
                                print(f"🔄 Change detected: {fpath_str}")
                                result = self.run_lint_fix_cycle(
                                    fpath_str, max_iterations=max_iterations
                                )
                                if result["success"]:
                                    print(f"   ✅ Fixed ({result['total_issues_fixed']} issues)")
                                else:
                                    print(
                                        f"   ⚠️  {result['total_issues_fixed']} fixed, "
                                        f"{len(result['remaining_issues'])} remaining"
                                    )
        except KeyboardInterrupt:
            print("\n👋 Watch stopped.")

    @staticmethod
    def _hash_file(file_path: str) -> str:
        """Return an MD5 hex digest of *file_path*."""
        import hashlib
        hasher = hashlib.md5()
        try:
            with open(file_path, "rb") as fh:
                for chunk in iter(lambda: fh.read(65536), b""):
                    hasher.update(chunk)
        except OSError:
            return ""
        return hasher.hexdigest()