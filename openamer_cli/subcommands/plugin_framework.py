"""``openamer plugins`` subcommand overrides for the Plugin Framework.

This module adds ``openamer plugins list``, ``openamer plugins install <path>``,
and ``openamer plugins reload`` using the new Plugin Framework.

NOTE: These commands exist alongside the existing plugins system in
``openamer_cli/plugins.py`` / ``subcommands/plugins.py``. They are separate
entry points for the composability framework.
"""

from __future__ import annotations

from typing import Callable


def build_plugins_framework_parser(subparsers, *, cmd_plugins_framework: Callable) -> None:
    """Attach extra ``plugins framework`` subcommands for the composability layer."""
    # Reuse the existing "plugins" top-level parser if already built;
    # otherwise this is added to the shared subparsers.
    plugins_parser = subparsers.add_parser(
        "plugins",
        help="Plugin framework — list, install, reload composable plugins",
        description="Manage the plugin composability framework (separate from the existing plugin system).",
    )
    plugins_sub = plugins_parser.add_subparsers(dest="plugins_framework_action")

    # list
    list_parser = plugins_sub.add_parser(
        "list",
        help="List discovered plugins from the framework registry",
    )
    list_parser.add_argument(
        "--all",
        action="store_true",
        help="Include disabled plugins",
    )

    # install
    install_parser = plugins_sub.add_parser(
        "install",
        help="Install a plugin from a file or directory path",
    )
    install_parser.add_argument(
        "path",
        help="Path to plugin directory or .py file",
    )

    # reload
    reload_parser = plugins_sub.add_parser(
        "reload",
        help="Reload one or all plugins",
    )
    reload_parser.add_argument(
        "name",
        nargs="?",
        default=None,
        help="Plugin name to reload (omit to reload all)",
    )

    plugins_parser.set_defaults(func=cmd_plugins_framework)