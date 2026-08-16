"""openamer_cli.a2a — Agent-to-Agent (A2A) support for OpenAmer.

Phase 0: identity + signed envelope core.
Phase 1: trust store + HTTP transport (node-to-node).
"""

from openamer_cli.a2a import core, trust, transport  # noqa: F401

__all__ = ["core", "trust", "transport"]
