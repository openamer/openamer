#!/usr/bin/env python3
"""``openamer secrets vault`` — manage the local credential vault.

The vault feeds ``browser_vault`` (model-blind browser autofill). Two halves:

- The CLI (``add`` / ``list`` / ``remove``) needs an interactive terminal: a
  credential is typed by the user into a masked prompt, never passed as an
  argument. Arguments land in the shell history and the process listing, which
  is exactly what this feature exists to avoid.
- :func:`attach_prompt_callback` wires the same masked prompt into a running CLI
  session, so the agent's ``browser_vault save_login`` action can ask the user
  on their own surface. Without it that action returns a typed refusal — which is
  correct for cron/gateway sessions, but it means the CLI must call this at
  startup for interactive use.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Dict, Optional


def _read_identifier(prompt: str) -> str:
    """Read the non-secret identifier. Plain input: it is not a secret."""
    try:
        return input(prompt).strip()
    except (EOFError, KeyboardInterrupt):
        return ""


def _read_password(prompt: str) -> str:
    """Read the secret with masked echo. Never echoes, never logs.

    Two paths, and the split matters. Interactive: the masked prompt, which
    shows one mask character per keystroke and never the value. Non-interactive
    (piped stdin, a script, a test): read the line straight from stdin.

    The non-interactive path is not a convenience — ``getpass.getpass``, which
    the masked prompt falls back to, reads the CONSOLE on Windows rather than
    stdin and HANGS when stdin is a pipe. Verified live: `secrets vault add`
    under a pipe blocked until the timeout. Reading the line avoids that while
    keeping the properties that matter: nothing is echoed, nothing is logged,
    and the value never appears in argv.
    """
    from openamer_cli.secret_prompt import masked_secret_prompt

    try:
        interactive = bool(sys.stdin.isatty())
    except Exception:
        interactive = False

    try:
        if not interactive:
            return sys.stdin.readline().rstrip("\r\n")
        return masked_secret_prompt(prompt)
    except (EOFError, KeyboardInterrupt):
        return ""


def cmd_add(args: argparse.Namespace) -> int:
    """Store a login for an origin. Prompts for everything; nothing via argv."""
    from agent.vault_store import VaultError, get_vault_store, normalize_origin

    origin = normalize_origin(getattr(args, "origin", "") or "")
    if not origin:
        print("A valid http(s) origin is required, e.g. https://example.com")
        return 2

    print(f"Storing a login for {origin}")
    print("The value is typed here and stored encrypted; it is never shown again.")
    identifier = _read_identifier("Username / email: ")
    if not identifier:
        print("Aborted: no identifier entered.")
        return 1
    password = _read_password("Password (hidden): ")
    if not password:
        print("Aborted: no password entered.")
        return 1

    try:
        meta = get_vault_store().add_item(
            "login", getattr(args, "label", "") or origin.split("://", 1)[-1],
            {"identifier": identifier, "password": password}, origin=origin,
        )
    except VaultError as exc:
        print(f"Could not store the login: {exc}")
        return 1
    finally:
        del password

    print(f"Stored. Handle: {meta.id}")
    print("Fill it with the browser_vault tool (action='fill').")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    """List handles and metadata. Never prints a password."""
    from agent.vault_store import get_vault_store

    try:
        vault = get_vault_store()
        if vault.needs_unlock():
            print("The vault could not be opened (missing or damaged key).")
            return 1
        items = [meta.to_dict() for meta in vault.list_items()]
    except Exception as exc:
        print(f"Vault unavailable: {exc}")
        return 1

    if getattr(args, "json", False):
        print(json.dumps({"items": items}, ensure_ascii=False, indent=2))
        return 0
    if not items:
        print("No stored credentials.")
        return 0
    print(f"{len(items)} item(s):")
    for item in items:
        origin = item.get("origin") or "(no origin)"
        ident = item.get("identifier") or ""
        print(f"  {item['handle']}  {item['kind']:<8} {origin:<34} {ident}")
    return 0


def cmd_remove(args: argparse.Namespace) -> int:
    """Remove one item by handle."""
    from agent.vault_store import get_vault_store

    try:
        removed = get_vault_store().remove_item(getattr(args, "handle", "") or "")
    except Exception as exc:
        print(f"Vault unavailable: {exc}")
        return 1
    if not removed:
        print("No item with that handle.")
        return 1
    print("Removed.")
    return 0


def register_cli(parent_parser: argparse.ArgumentParser) -> None:
    """Attach the ``vault`` subcommand tree to the ``secrets`` parser."""
    sub = parent_parser.add_subparsers(dest="secrets_vault_command")

    add = sub.add_parser("add", help="Store a login for a site (prompts for the secret)")
    add.add_argument("origin", help="The site origin, e.g. https://example.com")
    add.add_argument("--label", default="", help="Optional human label")
    add.set_defaults(func=cmd_add)

    ls = sub.add_parser("list", help="List stored handles (never prints secrets)")
    ls.add_argument("--json", action="store_true", help="Machine-readable output")
    ls.set_defaults(func=cmd_list)

    rm = sub.add_parser("remove", help="Delete one stored item")
    rm.add_argument("handle", help="Handle from `vault list`")
    rm.set_defaults(func=cmd_remove)

    parent_parser.set_defaults(func=lambda a: (parent_parser.print_help() or 0))


def attach_prompt_callback(cli: Any) -> None:
    """Wire the masked credential prompt into a running CLI session.

    Called once at CLI startup. This is what makes the agent-side
    ``browser_vault save_login`` action work in an interactive session; in
    cron/gateway/API sessions it is never called and that action refuses by
    design.
    """
    from agent.vault_prompt import set_prompt_callback
    from openamer_cli.callbacks import clarify_callback

    def _prompt(origin: str, site_label: str) -> Dict[str, str]:
        identifier = clarify_callback(cli, f"{site_label}: username / email for {origin}?", [])
        if not isinstance(identifier, str) or not identifier.strip():
            return {}
        if identifier.startswith("The user did not provide a response"):
            return {}
        password = _read_password(f"{site_label}: password for {origin} (hidden): ")
        if not password:
            return {}
        return {"identifier": identifier.strip(), "password": password}

    set_prompt_callback(_prompt)
