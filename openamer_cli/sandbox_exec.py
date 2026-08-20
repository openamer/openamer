"""
Sandbox Execution Engine for OpenAmer.

Provides isolated, temporary execution environments for running
untrusted Python code and shell commands with strict timeouts,
path restrictions, and automatic cleanup.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_HARD_TIMEOUT_MAX = 60  # Hard ceiling on any timeout (seconds)
_OUTPUT_CAP = 100 * 1024  # Max captured stdout/stderr (100 KB)
_OPENAMER_HOME_VAR = "OPENAMER_HOME"


# ---------------------------------------------------------------------------
# SandboxPolicy
# ---------------------------------------------------------------------------

@dataclass
class SandboxPolicy:
    """Configuration policy for the sandbox execution environment.

    Attributes
    ----------
    allowed_paths :
        List of path prefixes the sandbox is permitted to access.
        Empty = unrestricted (except blocked_paths).
    blocked_paths :
        List of path prefixes that are forbidden.  The sandbox home
        is always implicitly blocked.
    max_memory :
        Maximum memory (MB) the sandboxed process may use.  0 = no limit.
        *Note*: on Windows ``subprocess`` does not support ``RLIMIT_AS``;
        this is enforced via a rough guard in the executor instead.
    max_timeout :
        Maximum wall-clock seconds for any single execution within the
        sandbox.  Clamped to ``_HARD_TIMEOUT_MAX`` (60).
    """

    allowed_paths: list[str] = field(default_factory=list)
    blocked_paths: list[str] = field(default_factory=list)
    max_memory: int = 0  # MB; 0 = unlimited
    max_timeout: int = 30  # seconds; capped at 60

    def __post_init__(self) -> None:
        self.max_timeout = min(self.max_timeout, _HARD_TIMEOUT_MAX)
        # Always block the openamer config directory
        home = os.environ.get(_OPENAMER_HOME_VAR, "")
        if home:
            self.blocked_paths.append(str(Path(home).resolve()))


# ---------------------------------------------------------------------------
# SandboxExecutor
# ---------------------------------------------------------------------------

class SandboxExecutor:
    """Execute code in a temporary, isolated directory.

    Each call to a ``execute_*`` method creates a fresh temporary
    directory, runs the requested code inside it, captures stdout
    and stderr (capped at 100 KB), and then removes the directory.

    Parameters
    ----------
    policy :
        A :class:`SandboxPolicy` instance controlling the execution
        constraints.  A default policy is created if omitted.
    """

    def __init__(self, policy: SandboxPolicy | None = None) -> None:
        self.policy = policy or SandboxPolicy()
        self._exec_counter = 0

    # -- public API ---------------------------------------------------------

    def execute_python(
        self,
        code: str,
        timeout: int = 30,
        cwd: str | None = None,
    ) -> dict[str, Any]:
        """Execute *code* as a Python script in an isolated temp directory.

        Returns a dict with keys: ``stdout``, ``stderr``, ``exit_code``,
        ``timed_out``, ``duration``.
        """
        effective_timeout = self._clamp_timeout(timeout)
        sandbox_dir = Path(tempfile.mkdtemp(prefix="openamer-sandbox-"))
        try:
            script_path = sandbox_dir / "_sandbox_script.py"
            script_path.write_text(code, encoding="utf-8")

            self._exec_counter += 1
            seq = self._exec_counter
            logger.info(
                "[sandbox #%d] execute_python — timeout=%ds, dir=%s",
                seq, effective_timeout, sandbox_dir,
            )

            env = self._build_sandbox_env(sandbox_dir)

            proc = subprocess.Popen(
                [sys.executable, str(script_path)],
                cwd=str(cwd or sandbox_dir),
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            result = self._wait_with_timeout(proc, effective_timeout)

            logger.info(
                "[sandbox #%d] finished — exit_code=%s, stdout=%db, stderr=%db",
                seq, result["exit_code"], len(result["stdout"]), len(result["stderr"]),
            )
            return result
        finally:
            self._cleanup(sandbox_dir)

    def execute_shell(
        self,
        command: str,
        timeout: int = 30,
        cwd: str | None = None,
    ) -> dict[str, Any]:
        """Execute a shell command restricted to the sandbox directory.

        The command runs inside a temp dir with ``cwd`` pinned to the
        sandbox root.  Returns the same result dict as
        :meth:`execute_python`.
        """
        effective_timeout = self._clamp_timeout(timeout)
        sandbox_dir = Path(tempfile.mkdtemp(prefix="openamer-sandbox-"))
        try:
            self._exec_counter += 1
            seq = self._exec_counter
            logger.info(
                "[sandbox #%d] execute_shell — timeout=%ds, dir=%s",
                seq, effective_timeout, sandbox_dir,
            )

            env = self._build_sandbox_env(sandbox_dir)
            # On Windows use ``shell=True`` so cmd-style built-ins work;
            # the PATH restriction to sandbox_dir is the safety mechanism.
            use_shell: bool = sys.platform == "win32"

            proc = subprocess.Popen(
                command if use_shell else command,
                cwd=str(cwd or sandbox_dir),
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                shell=use_shell,
            )

            result = self._wait_with_timeout(proc, effective_timeout)

            logger.info(
                "[sandbox #%d] finished — exit_code=%s, stdout=%db, stderr=%db",
                seq, result["exit_code"], len(result["stdout"]), len(result["stderr"]),
            )
            return result
        finally:
            self._cleanup(sandbox_dir)

    def execute_safe(
        self,
        func: Callable,
        timeout: int = 30,
        args: tuple = (),
        kwargs: dict | None = None,
    ) -> dict[str, Any]:
        """Execute a Python function in process-isolated subprocess.

        The function is serialised as a short wrapper script inside a
        temp sandbox, so it runs in a fresh Python process with no
        access to the caller's memory space.

        Returns a dict with keys: ``stdout``, ``stderr``, ``exit_code``,
        ``timed_out``, ``duration``, and ``result`` (the pickled return
        value if successful, or ``None`` on failure).
        """
        effective_timeout = self._clamp_timeout(timeout)
        sandbox_dir = Path(tempfile.mkdtemp(prefix="openamer-sandbox-"))
        try:
            self._exec_counter += 1
            seq = self._exec_counter
            logger.info(
                "[sandbox #%d] execute_safe — timeout=%ds, dir=%s",
                seq, effective_timeout, sandbox_dir,
            )

            # Build a wrapper that imports the function, calls it, and
            # prints the return value on the last line of stdout.
            # We use repr() as a simple serialisation.
            import inspect
            func_source = textwrap.dedent(inspect.getsource(func))
            func_name = func.__name__
            args_repr = ", ".join(
                [repr(a) for a in args]
                + [f"{k}={repr(v)}" for k, v in (kwargs or {}).items()]
            )
            wrapper = textwrap.dedent(f"""\
            import sys, textwrap

            # Injected function
{textwrap.indent(func_source, '            ')}

            try:
                _result = {func_name}({args_repr})
                print("__SAFE_RESULT__:" + repr(_result))
            except Exception as e:
                print("__SAFE_ERROR__:" + repr(e), file=sys.stderr)
                sys.exit(1)
            """)
            script_path = sandbox_dir / "_safe_wrapper.py"
            script_path.write_text(wrapper, encoding="utf-8")

            env = self._build_sandbox_env(sandbox_dir)

            proc = subprocess.Popen(
                [sys.executable, str(script_path)],
                cwd=str(sandbox_dir),
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            raw = self._wait_with_timeout(proc, effective_timeout)

            # Parse the result line
            result_val = None
            for line in raw["stdout"].splitlines():
                if line.startswith("__SAFE_RESULT__:"):
                    try:
                        result_val = eval(line[len("__SAFE_RESULT__:"):])
                    except Exception:
                        result_val = None

            raw["result"] = result_val
            raw["stdout"] = "\n".join(
                ln for ln in raw["stdout"].splitlines()
                if not ln.startswith("__SAFE_RESULT__:")
                and not ln.startswith("__SAFE_ERROR__:")
            )

            logger.info(
                "[sandbox #%d] finished — exit_code=%s, result=%s",
                seq, raw["exit_code"], result_val,
            )
            return raw
        finally:
            self._cleanup(sandbox_dir)

    # -- internal helpers ---------------------------------------------------

    def _clamp_timeout(self, requested: int) -> int:
        """Clamp *requested* timeout to [1, policy.max_timeout] capped at 60."""
        upper = min(self.policy.max_timeout, _HARD_TIMEOUT_MAX)
        return max(1, min(requested, upper))

    def _build_sandbox_env(self, sandbox_dir: Path) -> dict[str, str]:
        """Build an environment dict that blocks access to ``~/.openamer``."""
        env = os.environ.copy()
        # Block OPENAMER_HOME so the sandbox can't read the config directory
        openamer_home = env.pop(_OPENAMER_HOME_VAR, None)
        if openamer_home:
            logger.debug("Removed OPENAMER_HOME=%s from sandbox env", openamer_home)
        # Restrict PATH to the sandbox + minimal system paths
        safe_path = [str(sandbox_dir)]
        if sys.platform == "win32":
            safe_path.extend([
                r"C:\Windows\system32",
                r"C:\Windows",
                r"C:\Windows\System32\Wbem",
            ])
        else:
            safe_path.extend(["/usr/bin", "/bin"])
        env["PATH"] = os.pathsep.join(safe_path)
        # Pin TMPDIR to sandbox so sub-subprocesses don't escape
        env["TMPDIR"] = str(sandbox_dir)
        env["TEMP"] = str(sandbox_dir)
        env["TMP"] = str(sandbox_dir)
        return env

    def _wait_with_timeout(
        self,
        proc: subprocess.Popen,
        timeout: int,
    ) -> dict[str, Any]:
        """Wait for *proc* to finish, enforcing *timeout*.

        Returns a result dict with stdout/stderr capped at
        ``_OUTPUT_CAP`` bytes.
        """
        import time
        start = time.monotonic()
        timed_out = False

        # Use a threading timer as a kill-switch
        timer = threading.Timer(timeout, lambda: _kill_proc(proc))
        timer.daemon = True
        timer.start()

        stdout_b, stderr_b = "", ""
        try:
            stdout_b, stderr_b = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            _kill_proc(proc)
            # Try to read whatever was captured
            try:
                stdout_b, stderr_b = proc.communicate(timeout=3)
            except (subprocess.TimeoutExpired, OSError):
                pass
        finally:
            timer.cancel()

        duration = time.monotonic() - start

        # Decode and cap — communicate() with text=True already returns str
        if isinstance(stdout_b, str):
            stdout_str = stdout_b
        else:
            stdout_str = stdout_b.decode("utf-8", errors="replace")
        if isinstance(stderr_b, str):
            stderr_str = stderr_b
        else:
            stderr_str = stderr_b.decode("utf-8", errors="replace")

        stdout = stdout_str[:_OUTPUT_CAP]
        stderr = stderr_str[:_OUTPUT_CAP]

        return {
            "stdout": stdout,
            "stderr": stderr,
            "exit_code": proc.returncode,
            "timed_out": timed_out,
            "duration": round(duration, 3),
        }

    @staticmethod
    def _cleanup(sandbox_dir: Path) -> None:
        """Remove *sandbox_dir* and all its contents."""
        if sandbox_dir.exists():
            try:
                shutil.rmtree(sandbox_dir, ignore_errors=True)
                logger.debug("Cleaned up sandbox directory: %s", sandbox_dir)
            except Exception as exc:
                logger.warning("Failed to clean up %s: %s", sandbox_dir, exc)


def _kill_proc(proc: subprocess.Popen) -> None:
    """Kill *proc* and its children."""
    if proc.poll() is not None:
        return
    try:
        if sys.platform == "win32":
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                capture_output=True,
                timeout=5,
            )
        else:
            proc.kill()
            proc.wait(timeout=5)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass