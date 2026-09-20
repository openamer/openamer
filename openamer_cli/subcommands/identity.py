"""``openamer identity`` subcommand parser.

Thin shim: the parser lives with the identity core in ``openamer_cli.identity``
so there is exactly one place that defines OpenAmer's identity surface.
Handler is injected to avoid importing ``main``.
"""

from __future__ import annotations

from openamer_cli.identity import build_identity_parser

__all__ = ["build_identity_parser"]
