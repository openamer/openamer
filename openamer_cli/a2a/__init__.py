"""openamer_cli.a2a — Agent-to-Agent (A2A) support for OpenAmer.

Phase 0: identity + signed envelope core.
Phase 1: trust store + HTTP transport (node-to-node).
Phase 2: signed registry announcements for the GitHub mesh directory.
Phase 3: a2a ask (task routing) + signed skill sharing.
"""

from openamer_cli.a2a import (core, trust, transport, registry, skillshare)  # noqa: F401

__all__ = ["core", "trust", "transport", "registry", "skillshare"]
