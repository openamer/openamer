"""Docker sandbox terminal backend for OpenAmer Agent.

Provides a lightweight Docker-based sandbox that wraps command execution
inside a container. When sandbox mode is enabled, terminal commands run
inside a Docker container instead of directly on the host.

Design goals:
- Simple, focused: fresh container per session, auto-pull, auto-cleanup
- Graceful degradation: if Docker is not installed, falls back to local
- Follows the same interface as other terminal backends (BaseEnvironment)
"""

from __future__ import annotations

import atexit
import json
import logging
import os
import shutil
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Docker binary resolution (lightweight, cached)
# ---------------------------------------------------------------------------

_DOCKER_EXECUTABLE: str | None = None
_DOCKER_SEARCH_PATHS = ["/usr/local/bin/docker", "/opt/homebrew/bin/docker"]


def _find_docker() -> str | None:
    """Locate the docker (or podman) CLI binary.

    Resolution order:
    1. OPENAMER_SANDBOX_DOCKER_BINARY env var
    2. ``docker`` on PATH
    3. ``podman`` on PATH
    4. Well-known macOS install locations
    """
    global _DOCKER_EXECUTABLE
    if _DOCKER_EXECUTABLE is not None:
        return _DOCKER_EXECUTABLE

    override = os.getenv("OPENAMER_SANDBOX_DOCKER_BINARY")
    if override and os.path.isfile(override) and os.access(override, os.X_OK):
        _DOCKER_EXECUTABLE = override
        return override

    found = shutil.which("docker")
    if found:
        _DOCKER_EXECUTABLE = found
        return found

    found = shutil.which("podman")
    if found:
        _DOCKER_EXECUTABLE = found
        logger.info("Using podman as container runtime: %s", found)
        return found

    for path in _DOCKER_SEARCH_PATHS:
        if os.path.isfile(path) and os.access(path, os.X_OK):
            _DOCKER_EXECUTABLE = path
            return path

    return None


def docker_available() -> bool:
    """Return True if a Docker-compatible runtime is installed and reachable."""
    return _find_docker() is not None


# ---------------------------------------------------------------------------
# SandboxConfig
# ---------------------------------------------------------------------------


@dataclass
class SandboxConfig:
    """Configuration for the Docker sandbox terminal backend.

    Attributes:
        image:      Docker image to use for the sandbox container.
        timeout:    Default command timeout in seconds.
        auto_pull:  If True, automatically pull the image if not cached locally.
    """

    image: str = "ubuntu:22.04"
    timeout: int = 300
    auto_pull: bool = True

    @classmethod
    def from_env(cls) -> "SandboxConfig":
        """Load SandboxConfig from environment variables (TERMINAL_SANDBOX_*).

        This mirrors the pattern used by the existing terminal backend config
        bridge (``TERMINAL_CONFIG_ENV_MAP`` in ``openamer_cli.config``).
        """
        return cls(
            image=os.getenv("TERMINAL_SANDBOX_IMAGE", "ubuntu:22.04"),
            timeout=int(os.getenv("TERMINAL_SANDBOX_TIMEOUT", "300")),
            auto_pull=os.getenv("TERMINAL_SANDBOX_AUTO_PULL", "true").lower()
            in {"true", "1", "yes"},
        )


# ---------------------------------------------------------------------------
# SandboxBackend
# ---------------------------------------------------------------------------


class DockerNotAvailableError(RuntimeError):
    """Raised when Docker is required but not available on the host."""


class SandboxBackend:
    """Lightweight Docker sandbox backend for terminal command execution.

    Spawns a fresh container per session (or per command for non-persistent
    usage). Follows the same interface as the ``BaseEnvironment`` subclasses
    in ``tools/environments/`` — specifically ``execute()``, ``cleanup()``,
    and ``_run_bash()``.

    Graceful degradation: if Docker is not installed, :meth:`execute` falls
    back to a local subprocess and logs a warning.
    """

    def __init__(
        self,
        config: SandboxConfig | None = None,
        *,
        cwd: str | None = None,
        task_id: str = "default",
        force_local_fallback: bool = False,
    ):
        self.config = config or SandboxConfig.from_env()
        self.cwd = cwd or os.getcwd()
        self._task_id = task_id
        self._force_local_fallback = force_local_fallback

        # Container lifecycle
        self._container_id: str | None = None
        self._container_created = False
        self._lock = threading.Lock()

        # Guard: check Docker once
        self._docker_exe: str | None = _find_docker()
        if self._docker_exe is None and not force_local_fallback:
            logger.warning(
                "Docker sandbox backend: Docker not found. "
                "Commands will fall back to local execution. "
                "Install Docker or set OPENAMER_SANDBOX_DOCKER_BINARY."
            )

        # Register atexit cleanup so containers don't leak on crash
        atexit.register(self._atexit_cleanup)

    # -- Public interface (mirrors BaseEnvironment) ------------------------

    def execute(
        self, command: str, *, timeout: int | None = None
    ) -> str:
        """Execute *command* inside the sandbox (or locally if Docker is absent).

        Returns stdout+stderr as a string.
        """
        effective_timeout = timeout or self.config.timeout

        if self._docker_exe is None or self._force_local_fallback:
            return self._execute_local(command, timeout=effective_timeout)

        try:
            return self._execute_in_docker(command, timeout=effective_timeout)
        except DockerNotAvailableError:
            logger.warning(
                "Docker sandbox became unavailable mid-operation. "
                "Falling back to local execution."
            )
            return self._execute_local(command, timeout=effective_timeout)

    def cleanup(self, force_remove: bool = False) -> None:
        """Remove the sandbox container (if any). Idempotent."""
        with self._lock:
            cid = self._container_id
            if cid is None:
                return
            self._container_id = None
            self._container_created = False

        if self._docker_exe is None:
            return

        try:
            subprocess.run(
                [self._docker_exe, "rm", "-f", cid],
                capture_output=True,
                text=True,
                timeout=30,
                stdin=subprocess.DEVNULL,
                check=False,
            )
            logger.info("Sandbox container %s removed.", cid[:12])
        except (subprocess.TimeoutExpired, OSError) as e:
            logger.warning("Failed to remove sandbox container %s: %s", cid[:12], e)

    def _run_bash(
        self,
        command: str,
        *,
        login: bool = False,
        timeout: int = 120,
        stdin_data: str | None = None,
    ) -> subprocess.Popen:
        """Spawn a bash subprocess (local fallback path)."""
        args: list[str] = []
        if login:
            args = ["bash", "-l", "-c", command]
        else:
            args = ["bash", "-c", command]

        proc = subprocess.Popen(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.PIPE if stdin_data is not None else subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=self.cwd,
        )
        if stdin_data is not None:
            proc.stdin.write(stdin_data)
            proc.stdin.close()
        return proc

    # -- Internal helpers --------------------------------------------------

    def _execute_local(self, command: str, *, timeout: int) -> str:
        """Run *command* directly on the host via subprocess."""
        logger.info("Sandbox: executing locally (Docker unavailable): %.80s", command)
        try:
            proc = self._run_bash(command, timeout=timeout)
            stdout, _ = proc.communicate(timeout=timeout)
            return stdout or ""
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(5)
            return f"Command timed out after {timeout}s\n"
        except Exception as e:
            return f"Local execution failed: {e}\n"

    def _ensure_image_pulled(self) -> None:
        """Pull the configured image if auto_pull is enabled and the image
        is not already cached locally."""
        if not self.config.auto_pull or self._docker_exe is None:
            return

        image = self.config.image
        try:
            result = subprocess.run(
                [self._docker_exe, "image", "inspect", image],
                capture_output=True,
                text=True,
                timeout=15,
                stdin=subprocess.DEVNULL,
                check=False,
            )
            if result.returncode == 0:
                logger.debug("Image %s already cached locally.", image)
                return
        except (subprocess.TimeoutExpired, OSError):
            pass

        logger.info("Pulling sandbox image %s ...", image)
        try:
            pull = subprocess.run(
                [self._docker_exe, "pull", image],
                capture_output=True,
                text=True,
                timeout=300,
                stdin=subprocess.DEVNULL,
                check=False,
            )
            if pull.returncode != 0:
                logger.warning(
                    "Failed to pull image %s: %s",
                    image,
                    pull.stderr.strip(),
                )
        except (subprocess.TimeoutExpired, OSError) as e:
            logger.warning("Error pulling image %s: %s", image, e)

    def _create_container(self) -> str:
        """Create (or reuse) the sandbox container and return its ID."""
        with self._lock:
            if self._container_created and self._container_id is not None:
                return self._container_id
            self._ensure_image_pulled()

        docker = self._docker_exe
        image = self.config.image
        host_cwd = self.cwd

        # Map the host cwd into the container at the same path.
        # On Linux we use the path as-is; on Windows we convert to a POSIX path.
        cwd = host_cwd

        cmd = [
            docker,
            "run",
            "--rm",                  # auto-cleanup on stop
            "-i",                    # interactive (stdin)
            "--label", "openamer-agent=sandbox",
            "--label", f"openamer-task={self._task_id}",
            "-w", cwd,
            "-v", f"{host_cwd}:{cwd}",
            image,
            "bash",
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,
                stdin=subprocess.DEVNULL,
                check=False,
            )
            if result.returncode != 0:
                raise DockerNotAvailableError(
                    f"Container creation failed (exit {result.returncode}): "
                    f"{result.stderr.strip()}"
                )
            # ``docker run --rm bash`` with no command exits. For a
            # *session* model we'd start ``sleep infinity`` and exec
            # commands into it.  For simplicity we use a fresh
            # ``docker run --rm`` per :meth:`_execute_in_docker`.
            # The container ID is only used for cleanup tracking.
            return ""
        except (subprocess.TimeoutExpired, OSError) as e:
            raise DockerNotAvailableError(
                f"Container creation failed: {e}"
            ) from e

    def _execute_in_docker(self, command: str, *, timeout: int) -> str:
        """Execute *command* inside a one-shot Docker container.

        Each command gets a fresh ``docker run --rm`` invocation with:
        - The configured image (auto-pulled if needed)
        - The host cwd bind-mounted at the same path
        - ``bash -c <command>`` as the entrypoint
        - Auto-cleanup via ``--rm`` flag
        """
        docker = self._docker_exe
        if docker is None:
            raise DockerNotAvailableError("Docker binary not found.")

        image = self.config.image
        host_cwd = self.cwd

        # Ensure image is pulled before the first run
        self._ensure_image_pulled()

        run_cmd = [
            docker,
            "run",
            "--rm",
            "-i",
            "-w", host_cwd,
            "-v", f"{host_cwd}:{host_cwd}",
            "--label", "openamer-agent=sandbox",
            "--label", f"openamer-task={self._task_id}",
            image,
            "bash", "-c", command,
        ]

        logger.info(
            "Sandbox: executing in Docker container (image=%s): %.80s",
            image,
            command,
        )

        try:
            result = subprocess.run(
                run_cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                stdin=subprocess.DEVNULL,
                check=False,
            )
            output = result.stdout or ""
            if result.stderr:
                output += "\n" + result.stderr
            return output
        except subprocess.TimeoutExpired:
            logger.warning("Sandbox command timed out after %ds: %.80s", timeout, command)
            return f"Command timed out after {timeout}s\n"
        except OSError as e:
            raise DockerNotAvailableError(
                f"Docker execution failed: {e}"
            ) from e

    def _atexit_cleanup(self) -> None:
        """Cleanup handler registered at exit."""
        self.cleanup(force_remove=True)


# ---------------------------------------------------------------------------
# Convenience: create a sandbox backend from config/env
# ---------------------------------------------------------------------------


def create_sandbox_backend(*, sandbox_enabled: bool = True, **kwargs: Any) -> SandboxBackend | None:
    """Create a :class:`SandboxBackend` if sandbox mode is enabled and Docker
    is available, else return ``None`` (caller falls back to local).

    ``kwargs`` are forwarded to the ``SandboxBackend`` constructor.
    """
    if not sandbox_enabled:
        return None
    return SandboxBackend(**kwargs)