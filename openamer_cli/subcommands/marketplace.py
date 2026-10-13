"""``openamer marketplace`` subcommand — discover, install, and publish community agents & skills.

CLI commands:
  openamer marketplace search <query>   Search community marketplace
  openamer marketplace install <name>   Install an item from the marketplace
  openamer marketplace publish <name>   Prepare an item for publishing
  openamer marketplace list             List installed marketplace items
"""

from __future__ import annotations

import sys
from typing import Callable

from openamer_cli.marketplace import (
    MarketplaceStore,
    discover_marketplace,
    install_from_marketplace,
    list_installed,
    publish_to_marketplace,
)


def _cmd_search(args) -> int:
    query = args.query or ""
    results = discover_marketplace(query)
    if not results:
        print("No marketplace items found." + (" for query: " + query if query else ""))
        return 0
    print(f"\n{'Found ' + str(len(results)) + ' item(s)'} in the community marketplace:")
    print(f"{'─' * 72}")
    for i, item in enumerate(results, 1):
        print(f"  {i}. {item.name}")
        print(f"     Type     : {item.type}")
        print(f"     Author   : {item.author}")
        print(f"     Version  : {item.version}")
        if item.description:
            desc = item.description[:100]
            print(f"     Descr.   : {desc}{'…' if len(item.description) > 100 else ''}")
        if item.topics:
            print(f"     Topics   : {', '.join(item.topics[:5])}")
        print()
    return 0


def _cmd_install(args) -> int:
    name = args.name
    source = getattr(args, "source", "") or f"https://github.com/openamer/{name}"

    print(f"Installing '{name}' from marketplace...")
    ok = install_from_marketplace(name, source)
    if ok:
        print(f"✓ Successfully installed '{name}'.")
        return 0
    print(f"✗ Failed to install '{name}'. Check the name and source.")
    return 1


def _cmd_publish(args) -> int:
    name = args.name
    # Default to skill type; can be overridden with --type
    item_type = getattr(args, "type", "skill")

    # Check if it exists locally first — look in skills/ or marketplace/
    store = MarketplaceStore()
    listing = store.get(name)

    if listing:
        item_type = listing.type

    print(f"Preparing '{name}' for publishing ({item_type})...")
    ok = publish_to_marketplace(name, item_type)
    if ok:
        print("✓ Package prepared. Follow the instructions above to publish on GitHub.")
        return 0
    print(f"✗ Failed to prepare '{name}' for publishing.")
    return 1


def _cmd_list(args) -> int:
    items = list_installed()
    if not items:
        print("No marketplace items installed.\n"
              "  Use `openamer marketplace search` to discover, then `openamer marketplace install`.")
        return 0
    print(f"\nInstalled marketplace items ({len(items)}):")
    print(f"{'─' * 72}")
    for item in items:
        print(f"  {item.name}  ({item.type}) v{item.version}  by {item.author}")
        if item.description:
            print(f"    {item.description[:120]}")
        print()
    return 0


def build_marketplace_parser(subparsers) -> None:
    """Attach the ``marketplace`` subcommand tree.

    Matches the pattern used by ``build_a2a_parser``, ``build_skills_parser``,
    etc. in ``openamer_cli/subcommands/``.
    """
    p = subparsers.add_parser(
        "marketplace",
        help="Discover, install, and publish community agents & skills",
        description=(
            "The OpenAmer Agent Marketplace — a community-driven directory of "
            "agents and skills. Search GitHub for shared tools, install them "
            "locally, or prepare your own for publishing."
        ),
    )
    sub = p.add_subparsers(dest="marketplace_cmd")

    # --- search ---
    s = sub.add_parser("search", help="Search the community marketplace")
    s.add_argument("query", nargs="?", default="", help="Search query (name/description)")
    s.set_defaults(func=_cmd_search)

    # --- install ---
    i = sub.add_parser("install", help="Install an item from the marketplace")
    i.add_argument("name", help="Item name (e.g. my-agent)")
    i.add_argument("--source", default="", help="Override source URL (default: github.com/openamer/<name>)")
    i.set_defaults(func=_cmd_install)

    # --- publish ---
    pb = sub.add_parser("publish", help="Prepare a marketplace item for publishing on GitHub")
    pb.add_argument("name", help="Item name to publish")
    pb.add_argument("--type", choices=["agent", "skill"], default="skill",
                    help="Item type (default: skill)")
    pb.set_defaults(func=_cmd_publish)

    # --- list ---
    lc = sub.add_parser("list", help="List installed marketplace items")
    lc.set_defaults(func=_cmd_list)

    p.set_defaults(func=_cmd_list)