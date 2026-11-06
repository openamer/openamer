"""``openamer plugins`` subcommand parser.

Extracted from ``openamer_cli/main.py:main()`` (god-file Phase 2 follow-up).
Handler injected to avoid importing ``main``.
"""

from __future__ import annotations

from typing import Callable


def build_plugins_parser(subparsers, *, cmd_plugins: Callable) -> None:
    """Attach the ``plugins`` subcommand to ``subparsers``."""
    plugins_parser = subparsers.add_parser(
        "plugins",
        help="Manage plugins — install, update, remove, list",
        description="Install plugins from Git repositories, update, remove, or list them.",
    )
    plugins_subparsers = plugins_parser.add_subparsers(dest="plugins_action")

    plugins_install = plugins_subparsers.add_parser(
        "install", help="Install a plugin from a Git URL or owner/repo"
    )
    plugins_install.add_argument(
        "identifier",
        help="Git URL or owner/repo shorthand (e.g. anpicasso/openamer-plugin-chrome-profiles)",
    )
    plugins_install.add_argument(
        "--force",
        "-f",
        action="store_true",
        help="Remove existing plugin and reinstall",
    )
    _install_enable_group = plugins_install.add_mutually_exclusive_group()
    _install_enable_group.add_argument(
        "--enable",
        action="store_true",
        help="Auto-enable the plugin after install (skip confirmation prompt)",
    )
    _install_enable_group.add_argument(
        "--no-enable",
        action="store_true",
        help="Install disabled (skip confirmation prompt); enable later with `openamer plugins enable <name>`",
    )

    plugins_update = plugins_subparsers.add_parser(
        "update", help="Pull latest changes for an installed plugin"
    )
    plugins_update.add_argument("name", help="Plugin name to update")

    plugins_remove = plugins_subparsers.add_parser(
        "remove", aliases=["rm", "uninstall"], help="Remove an installed plugin"
    )
    plugins_remove.add_argument("name", help="Plugin directory name to remove")

    plugins_list = plugins_subparsers.add_parser(
        "list", aliases=["ls"], help="List installed plugins"
    )
    plugins_list.add_argument(
        "--enabled",
        action="store_true",
        help="Show only enabled plugins",
    )
    plugins_list.add_argument(
        "--user",
        action="store_true",
        help="Show only user-installed plugins (including git plugins)",
    )
    plugins_list.add_argument(
        "--no-bundled",
        action="store_true",
        help="Hide bundled plugins",
    )
    plugins_list.add_argument(
        "--plain",
        action="store_true",
        help="Print compact plain-text output instead of a Rich table",
    )
    plugins_list.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable JSON",
    )

    plugins_search = plugins_subparsers.add_parser(
        "search", help="Search GitHub for OpenAmer plugins"
    )
    plugins_search.add_argument(
        "query",
        nargs="?",
        help="Optional search term to filter results",
    )
    plugins_search.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Maximum number of results (default: 10)",
    )
    plugins_search.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable JSON",
    )

    plugins_enable = plugins_subparsers.add_parser(
        "enable", help="Enable a disabled plugin"
    )
    plugins_enable.add_argument("name", help="Plugin name to enable")
    _enable_override_group = plugins_enable.add_mutually_exclusive_group()
    _enable_override_group.add_argument(
        "--allow-tool-override",
        action="store_true",
        help="Grant this plugin permission to replace built-in tools "
        "(e.g. shell_exec, write_file). Skips the confirmation prompt.",
    )
    _enable_override_group.add_argument(
        "--no-allow-tool-override",
        action="store_true",
        help="Enable without granting built-in tool override (skip prompt).",
    )

    plugins_disable = plugins_subparsers.add_parser(
        "disable", help="Disable a plugin without removing it"
    )
    plugins_disable.add_argument("name", help="Plugin name to disable")

    plugins_reload = plugins_subparsers.add_parser(
        "reload", help="Re-discover and reload all plugins in this process"
    )
    plugins_reload.add_argument(
        "name",
        nargs="?",
        default=None,
        help="Optional plugin name (a force re-discovery reloads every plugin)",
    )

    plugins_package = plugins_subparsers.add_parser(
        "package",
        help="Manage portable agent-plugin packages (plugin.json; installed inert)",
        description=(
            "Install and inspect Agent Plugins v1 portable packages. Packages are "
            "stored under the profile's plugin-packages/ directory, are never "
            "imported as Python, and never start an MCP server unless explicitly "
            "enabled with `openamer plugins package enable <name>`."
        ),
    )
    package_subparsers = plugins_package.add_subparsers(dest="package_action")

    package_install = package_subparsers.add_parser(
        "install", help="Install a portable package from a local directory (inert)"
    )
    package_install.add_argument("identifier", help="Path to the package directory")
    package_install.add_argument(
        "--force", "-f", action="store_true", help="Reinstall over an existing package"
    )

    package_list = package_subparsers.add_parser(
        "list", aliases=["ls"], help="List installed portable packages"
    )
    package_list.add_argument("--json", action="store_true", help="Machine-readable output")

    package_show = package_subparsers.add_parser(
        "show", help="Show a package's declared skills and MCP servers"
    )
    package_show.add_argument("name", help="Package name")
    package_show.add_argument("--json", action="store_true", help="Machine-readable output")

    package_enable = package_subparsers.add_parser(
        "enable",
        help="Allow a package's declared MCP servers to reach the MCP config",
    )
    package_enable.add_argument("name", help="Package name")

    package_disable = package_subparsers.add_parser(
        "disable", help="Keep a package installed but stop exposing its MCP servers"
    )
    package_disable.add_argument("name", help="Package name")

    package_remove = package_subparsers.add_parser(
        "remove", aliases=["rm"], help="Remove an installed portable package"
    )
    package_remove.add_argument("name", help="Package name")

    plugins_parser.set_defaults(func=cmd_plugins)
