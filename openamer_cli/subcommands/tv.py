"""``openamer tv`` — control a Philips TV on the local network.

The implementation lives in :mod:`openamer_cli.tv`; this module only attaches
the parser so ``main.py`` can wire it like every other subcommand. The same
``add_tv_subcommands`` is used by ``scripts/tv_remote.py``, so the CLI and the
standalone script can never drift apart.
"""

from __future__ import annotations


def build_tv_parser(subparsers) -> None:
    """Attach the ``tv`` subcommand to ``subparsers``."""
    from openamer_cli.tv import add_tv_subcommands

    parser = subparsers.add_parser(
        "tv",
        help="Control a Philips TV on the local network",
        description=(
            "Discover a Philips TV via SSDP, then read its state, send remote "
            "keys, open a URL in its browser or change power state over the "
            "JointSpace API on port 1925."
        ),
    )
    parser.add_argument("--host", help="TV IP (default: cached / auto-discover)")
    add_tv_subcommands(parser)
