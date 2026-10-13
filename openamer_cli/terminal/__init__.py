"""Terminal backends package for OpenAmer Agent.

This package holds sandbox and other terminal backend implementations.
The primary backend classes live under ``openamer_cli.terminal.sandbox``.
"""

from openamer_cli.terminal.sandbox import SandboxBackend, SandboxConfig, docker_available

__all__ = ["SandboxBackend", "SandboxConfig", "docker_available"]