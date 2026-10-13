"""
Tests for the Sandbox Execution Engine.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import pytest

from openamer_cli.sandbox_exec import (
    SandboxExecutor,
    SandboxPolicy,
    _HARD_TIMEOUT_MAX,
    _OUTPUT_CAP,
)


# ---------------------------------------------------------------------------
# SandboxPolicy
# ---------------------------------------------------------------------------

class TestSandboxPolicy:
    def test_default_policy(self) -> None:
        policy = SandboxPolicy()
        assert policy.max_timeout == 30
        assert policy.max_memory == 0
        assert policy.allowed_paths == []
        # blocked_paths should include OPENAMER_HOME if set
        home = os.environ.get("OPENAMER_HOME", "")
        if home:
            assert str(Path(home).resolve()) in policy.blocked_paths

    def test_timeout_clamped_to_hard_max(self) -> None:
        policy = SandboxPolicy(max_timeout=120)
        assert policy.max_timeout == _HARD_TIMEOUT_MAX  # 60

    def test_timeout_no_clamp_when_under_limit(self) -> None:
        policy = SandboxPolicy(max_timeout=45)
        assert policy.max_timeout == 45  # no change


# ---------------------------------------------------------------------------
# SandboxExecutor — execute_python
# ---------------------------------------------------------------------------

class TestExecutePython:
    def setup_method(self) -> None:
        self.executor = SandboxExecutor()

    def test_simple_print(self) -> None:
        """A simple Python script that prints to stdout."""
        result = self.executor.execute_python('print("hello sandbox")')
        assert result["exit_code"] == 0
        assert "hello sandbox" in result["stdout"]
        assert result["timed_out"] is False
        assert result["duration"] > 0

    def test_stderr_capture(self) -> None:
        """Stderr is captured separately from stdout."""
        code = """
import sys
print("stdout line")
print("stderr line", file=sys.stderr)
"""
        result = self.executor.execute_python(code)
        assert result["exit_code"] == 0
        assert "stdout line" in result["stdout"]
        assert "stderr line" in result["stderr"]

    def test_non_zero_exit(self) -> None:
        """A script that exits with non-zero code."""
        result = self.executor.execute_python("exit(42)")
        assert result["exit_code"] == 42

    def test_exception_raises_non_zero(self) -> None:
        """An unhandled exception results in a non-zero exit code."""
        result = self.executor.execute_python("raise RuntimeError('boom')")
        assert result["exit_code"] != 0
        assert "RuntimeError" in result["stderr"]

    def test_sandbox_dir_is_cleaned_up(self) -> None:
        """The temporary sandbox directory should be removed after execution."""
        # We cannot easily monkey-patch here — we rely on the fact that
        # the temp dir is created in the system temp directory.
        temp_root = Path(tempfile.gettempdir())
        before = set(temp_root.iterdir())
        self.executor.execute_python("print('cleanup test')")
        after = set(temp_root.iterdir())
        # At a minimum, no new openamer-sandbox dirs should remain
        new_dirs = after - before
        sandbox_dirs = [d for d in new_dirs if "openamer-sandbox" in d.name]
        assert len(sandbox_dirs) == 0, f"Leftover sandbox dirs: {sandbox_dirs}"

    def test_timeout_respected(self) -> None:
        """A script that sleeps longer than the timeout should be killed."""
        result = self.executor.execute_python(
            "import time; time.sleep(10)",
            timeout=1,
        )
        assert result["timed_out"] is True
        assert result["exit_code"] != 0 or result["exit_code"] is None

    def test_output_capped(self) -> None:
        """Very long output should be capped at _OUTPUT_CAP bytes."""
        # Generate more than 100KB of output
        long_print_code = "print('x' * 200_000)"
        result = self.executor.execute_python(long_print_code)
        assert len(result["stdout"]) <= _OUTPUT_CAP + 100  # small fudge for newline

    def test_code_with_imports(self) -> None:
        """Code should be able to import standard library modules."""
        code = "import json; print(json.dumps({'key': 'value'}))"
        result = self.executor.execute_python(code)
        assert result["exit_code"] == 0
        assert '"key": "value"' in result["stdout"]


# ---------------------------------------------------------------------------
# SandboxExecutor — execute_shell
# ---------------------------------------------------------------------------

class TestExecuteShell:
    def setup_method(self) -> None:
        self.executor = SandboxExecutor()

    def test_simple_command(self) -> None:
        """Run a simple shell command."""
        if sys.platform == "win32":
            result = self.executor.execute_shell("echo hello_sandbox")
        else:
            result = self.executor.execute_shell("echo hello_sandbox")
        assert result["exit_code"] == 0
        assert "hello_sandbox" in result["stdout"]

    def test_non_zero_exit(self) -> None:
        """Shell command that fails should return non-zero."""
        if sys.platform == "win32":
            result = self.executor.execute_shell("cmd /c exit 1")
        else:
            result = self.executor.execute_shell("false")
        assert result["exit_code"] != 0

    def test_stderr_capture(self) -> None:
        """Shell stderr should be captured."""
        if sys.platform == "win32":
            result = self.executor.execute_shell(
                'cmd /c "echo stderr_line 1>&2"'
            )
        else:
            result = self.executor.execute_shell(
                'echo "stderr_line" >&2'
            )
        assert "stderr_line" in result["stderr"]


# ---------------------------------------------------------------------------
# SandboxExecutor — execute_safe (process-isolated function call)
# ---------------------------------------------------------------------------

class TestExecuteSafe:
    def setup_method(self) -> None:
        self.executor = SandboxExecutor()

    def test_simple_function(self) -> None:
        """A simple function should return the expected value."""
        def add(a: int, b: int) -> int:
            return a + b

        result = self.executor.execute_safe(add, args=(3, 4))
        assert result["exit_code"] == 0
        assert result["result"] == 7

    def test_function_with_exception(self) -> None:
        """A function that raises should be reported as an error."""
        def broken() -> None:
            raise ValueError("oh no")

        result = self.executor.execute_safe(broken)
        assert result["exit_code"] != 0

    def test_isolation_from_caller(self) -> None:
        """The sandboxed function should not see the caller's globals."""
        # Define a function that tries to access a variable that exists
        # only in this test's scope
        def check_variable() -> str:
            return str(result)  # noqa: F821 — not yet defined when function runs

        # result doesn't exist inside the subprocess, so it should error
        res = self.executor.execute_safe(check_variable)
        assert res["exit_code"] != 0


# ---------------------------------------------------------------------------
# Policy interaction with executor
# ---------------------------------------------------------------------------

class TestPolicyIntegration:
    def test_policy_limits_timeout(self) -> None:
        """Policy.max_timeout should cap the effective timeout."""
        policy = SandboxPolicy(max_timeout=5)
        executor = SandboxExecutor(policy=policy)

        # Even with high timeout, clamped to 5
        result = executor.execute_python("print('ok')", timeout=999)
        assert result["exit_code"] == 0

        # Actually verify the clamping via the internal method
        assert executor._clamp_timeout(999) == 5

    def test_policy_max_timeout_at_zero_uses_default(self) -> None:
        """A policy with max_timeout=1 should still allow quick runs."""
        policy = SandboxPolicy(max_timeout=1)
        executor = SandboxExecutor(policy=policy)
        # Very quick code — should finish within 1s
        result = executor.execute_python("print('fast')")
        assert result["exit_code"] == 0
        assert "fast" in result["stdout"]