"""``openamer a2a`` subcommand — Agent-to-Agent identity & trust for OpenAmer.

Phase 0 surface:
  openamer a2a status         Show node identity + whether A2A is initialized.
  openamer a2a init           Generate/refresh the node identity keypair.
  openamer a2a fingerprint    Print just the node fingerprint (address).
  openamer a2a verify <json>  Verify a signed envelope given a sender pubkey/identity.

These are safe, local, non-networking operations — the foundation for the
later node-to-node + mesh phases described in .plans/a2a-agent-swarm.md.
"""
from __future__ import annotations

import json
import sys
from typing import Callable

from openamer_cli.a2a import core


def _home() -> core.IdentityStore:
    return core.IdentityStore()


def _cmd_status(args) -> int:
    store = _home()
    if not store.exists():
        print("A2A: not initialized (run `openamer a2a init`).")
        return 0
    ident = store.load()
    print(f"A2A status:")
    print(f"  fingerprint : {ident.fingerprint}")
    print(f"  public key  : {ident.public_key}")
    print(f"  identity    : {ident.fingerprint}@openamer")
    return 0


def _cmd_init(args) -> int:
    store = _home()
    existed = store.exists()
    ident = store.ensure_identity()
    verb = "refreshed" if existed else "created"
    print(f"A2A identity {verb}: {ident.fingerprint}@openamer")
    return 0


def _cmd_fingerprint(args) -> int:
    store = _home()
    if not store.exists():
        store.ensure_identity()
    print(store.load().fingerprint)
    return 0


def _cmd_verify(args) -> int:
    """Verify a signed envelope from --json (a dict) against a sender pubkey.

    Usage: openamer a2a verify '{"sender": "...", ..., "signature": "..."}' <sender_public_key_hex>
    """
    if not args.json_payload or not args.sender_pubkey:
        print("Usage: openamer a2a verify '<envelope-json>' <sender_public_key_hex>")
        return 2
    try:
        data = json.loads(args.json_payload)
    except json.JSONDecodeError as e:
        print(f"Invalid envelope JSON: {e}")
        return 2
    env = core.Envelope.from_dict(data)
    ok = env.verify(args.sender_pubkey)
    print("VERIFIED" if ok else "INVALID")
    print(f"  sender    : {env.sender}")
    print(f"  recipient : {env.recipient}")
    print(f"  kind      : {env.kind}")
    return 0 if ok else 1


def build_a2a_parser(subparsers) -> None:
    """Attach the ``a2a`` subcommand tree."""
    p = subparsers.add_parser("a2a", help="Agent-to-Agent (A2A) identity & mesh")
    sub = p.add_subparsers(dest="a2a_cmd")

    s = sub.add_parser("status", help="Show A2A node status")
    s.set_defaults(func=_cmd_status)

    i = sub.add_parser("init", help="Generate the node identity keypair")
    i.set_defaults(func=_cmd_init)

    f = sub.add_parser("fingerprint", help="Print the node fingerprint")
    f.set_defaults(func=_cmd_fingerprint)

    v = sub.add_parser("verify", help="Verify a signed envelope")
    v.add_argument("json_payload", nargs="?", help="signed envelope JSON")
    v.add_argument("sender_pubkey", nargs="?", help="sender public key hex")
    v.set_defaults(func=_cmd_verify)

    p.set_defaults(func=_cmd_status)