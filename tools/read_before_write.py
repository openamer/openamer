"""Read-before-write policy for the file mutation tools.

Adapted from deepseek-ai/deepseek-harness ``fs-observation-policy``
(``packages/fs/fs-observation-policy``). Upstream makes it a *decider*:
a mutation that was not preceded by a read of the same path is rejected
with ``FS_NOT_OBSERVED``, and a file that changed since the read is
rejected as well. OpenAmer already detects both situations but only
reports them as a warning next to the write result.

This module turns that detection into an enforced policy:

  * ``read_before_write.enabled``  — off by default (behaviour-preserving),
    turned on per profile in config.yaml.
  * ``read_before_write.allow_create`` — permit creating a file that was
    never read (upstream: "reading a missing path authorizes guarded
    creation").

The policy is deliberately conservative: it only blocks when it can
prove the agent never observed the current content. When it cannot decide
(net-new file, unreadable path, disabled registry), it lets the write
through and says nothing.
"""
from __future__ import annotations

import os
import threading
from dataclasses import dataclass
from typing import Optional

from tools import file_state


@dataclass(frozen=True)
class ReadBeforeWriteConfig:
    """Configuration for the read-before-write policy."""

    enabled: bool = False
    allow_create: bool = True

    @classmethod
    def from_mapping(cls, data) -> "ReadBeforeWriteConfig":
        """Build a config from the ``read_before_write`` config.yaml section."""

        def _bool(value, default: bool) -> bool:
            if isinstance(value, bool):
                return value
            return default

        if not isinstance(data, dict):
            return cls()
        return cls(
            enabled=_bool(data.get("enabled"), False),
            allow_create=_bool(data.get("allow_create"), True),
        )


_LOCK = threading.Lock()
_CONFIG = ReadBeforeWriteConfig()


def _disabled_by_env() -> bool:
    return os.environ.get("OPENAMER_DISABLE_READ_BEFORE_WRITE") == "1"


def configure(cfg: ReadBeforeWriteConfig) -> None:
    """Install the effective policy configuration."""
    global _CONFIG
    with _LOCK:
        _CONFIG = cfg


def reset() -> None:
    """Restore the default (disabled) policy. Used by tests."""
    global _CONFIG
    with _LOCK:
        _CONFIG = ReadBeforeWriteConfig()


def current_config() -> ReadBeforeWriteConfig:
    with _LOCK:
        return _CONFIG


def check(task_id: str, resolved: str) -> Optional[str]:
    """Return a refusal message when the mutation must not proceed.

    ``resolved`` is the absolute path the write would land on. The
    message is written for the model, so it states what to do next.
    """
    cfg = current_config()
    if not cfg.enabled or _disabled_by_env():
        return None

    # Net-new file: creating a file nobody read is legitimate work.
    # Upstream requires reading the *missing* path to authorize creation,
    # but refusing every first write would block legitimate scaffolding.
    if not os.path.exists(resolved):
        if cfg.allow_create:
            return None
        return (
            f"Read-before-write policy: {resolved} does not exist yet. "
            "Read the path first to authorize creating it."
        )

    if resolved not in set(file_state.known_reads(task_id)):
        return (
            f"Read-before-write policy: {resolved} was not read by this "
            "agent. Read the file first so the write is based on its "
            "current content."
        )

    # A file that changed since the read is a different case: the agent
    # did observe it, but what it saw is no longer on disk.
    #
    # Only the *changed* case blocks. A partial read (offset/limit
    # pagination) is a hint, not a blocker: it would make every targeted
    # edit of a large file impossible, because reading the whole file to
    # satisfy the policy is exactly the cost the policy is meant to
    # avoid. Upstream's policy decider has the same shape — it refuses
    # unobserved and stale writes, not windowed ones.
    stale = file_state.check_stale(task_id, resolved)
    if stale and "was last read with offset/limit pagination" not in stale:
        return (
            f"Read-before-write policy: {resolved} changed since you read "
            f"it. {stale} Re-read the file and apply your change to the "
            "current content."
        )

    return None


__all__ = [
    "ReadBeforeWriteConfig",
    "check",
    "configure",
    "current_config",
    "reset",
]
