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
from openamer_cli.a2a import registry


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


def _cmd_announce(args) -> int:
    """Create + sign this node's announcement and stage it for publication."""
    ann = registry.sign_announcement(
        name=args.name or "OpenAmer node",
        endpoints=args.endpoints or [],
        capabilities=args.capabilities or [],
    )
    out = registry.save_announcement(ann)
    print(f"A2A announcement for {ann.fingerprint}@openamer")
    print(f"  name        : {ann.name}")
    print(f"  endpoints   : {', '.join(ann.endpoints) or '(none)'}")
    print(f"  capabilities: {', '.join(ann.capabilities) or '(none)'}")
    print(f"  staged      : {out}")
    print("To publish on GitHub, commit this file to directory/a2a/ in")
    print("  github.com/openamer/openamer.")
    return 0


def _cmd_directory(args) -> int:
    """Fetch + verify a node announcement from the GitHub mesh directory."""
    if not args.fingerprint:
        print("Usage: openamer a2a directory <fingerprint>")
        return 2
    ann = registry.fetch_announcement(args.fingerprint, repo_base=args.repo or registry.REPO_BASE)
    if ann is None:
        print(f"No verified announcement for {args.fingerprint} in the registry.")
        return 1
    print(f"node: {ann.name}")
    print(f"  fingerprint : {ann.fingerprint}")
    print(f"  public key  : {ann.public_key}")
    print(f"  endpoints   : {', '.join(ann.endpoints)}")
    print(f"  capabilities: {', '.join(ann.capabilities)}")
    return 0


def _cmd_self(args) -> int:
    """Show this node's signed announcement (dry run of what publish produces)."""
    ann = registry.sign_announcement(
        name=args.name or "OpenAmer node",
        endpoints=args.endpoints or [],
        capabilities=args.capabilities or [],
    )
    import json as _json
    print(_json.dumps(ann.to_dict(), indent=2))
    return 0


def _cmd_ask(args) -> int:
    """Ask a trusted remote node a question (Node-to-Node A2A routing).

    Usage: openamer a2a ask <peer-http-url> "<question>"
    """
    if not args.peer_url or not args.question:
        print("Usage: openamer a2a ask <peer-http-url> \"<question>\"")
        return 2
    from openamer_cli.a2a import transport
    identity = core.IdentityStore()
    trust_store = _trust()
    res = transport.ask(identity, trust_store, args.peer_url, args.question,
                        kind=args.kind or "ask")
    if res.get("ok"):
        print(f"OK ({res.get('kind')}): {res.get('result', {})}")
    else:
        print(f"Not answered: {res.get('error', res)}")
    return 0 if res.get("ok") else 1


def _trust() -> "TrustStore":
    from openamer_cli.a2a.trust import TrustStore
    return TrustStore()


def _cmd_trust(args) -> int:
    """Manage trusted peers (opt-in mesh membership)."""
    from openamer_cli.a2a.trust import TrustStore
    store = TrustStore()
    act = args.trust_cmd
    if act == "list":
        peers = store.peers()
        if not peers:
            print("No trusted peers yet.")
            return 0
        for p in peers:
            print(f"{p.fingerprint}  {p.name}")
        return 0
    if act == "add":
        if not args.fingerprint or not args.public_key:
            print("Usage: openamer a2a trust add <fingerprint> <public_key_hex> [name]")
            return 2
        store.add_peer(args.fingerprint, args.public_key, name=args.name or "")
        print(f"Added peer {args.fingerprint}")
        return 0
    if act == "remove":
        if not args.fingerprint:
            print("Usage: openamer a2a trust remove <fingerprint>")
            return 2
        ok = store.remove_peer(args.fingerprint)
        print("Removed." if ok else "Not found.")
        return 0 if ok else 1
    print("Unknown trust subcommand.")
    return 2


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

    an = sub.add_parser("announce", help="Create + sign this node's announcement, stage for GitHub")
    an.add_argument("--name", default=None)
    an.add_argument("--endpoints", nargs="*", default=None)
    an.add_argument("--capabilities", nargs="*", default=None)
    an.set_defaults(func=_cmd_announce)

    sf = sub.add_parser("self", help="Print this node's signed announcement (JSON)")
    sf.add_argument("--name", default=None)
    sf.add_argument("--endpoints", nargs="*", default=None)
    sf.add_argument("--capabilities", nargs="*", default=None)
    sf.set_defaults(func=_cmd_self)

    dc = sub.add_parser("directory", help="Fetch + verify a node from the GitHub mesh directory")
    dc.add_argument("fingerprint", nargs="?", help="node fingerprint")
    dc.add_argument("--repo", default=None, help="registry base URL")
    dc.set_defaults(func=_cmd_directory)

    aq = sub.add_parser("ask", help="Ask a trusted peer a question (A2A routing)")
    aq.add_argument("peer_url", nargs="?", help="peer HTTP base URL")
    aq.add_argument("question", nargs="?", help="the question to ask")
    aq.add_argument("--kind", default="ask")
    aq.set_defaults(func=_cmd_ask)

    tr = sub.add_parser("trust", help="Manage trusted peers (opt-in)")
    tr_sub = tr.add_subparsers(dest="trust_cmd")
    tl = tr_sub.add_parser("list", help="List trusted peers"); tl.set_defaults(func=_cmd_trust)
    ta = tr_sub.add_parser("add", help="Trust a peer by fingerprint + public key")
    ta.add_argument("fingerprint", nargs="?"); ta.add_argument("public_key", nargs="?")
    ta.add_argument("--name", default="")
    ta.set_defaults(func=_cmd_trust)
    trm = tr_sub.add_parser("remove", help="Remove a trusted peer")
    trm.add_argument("fingerprint", nargs="?"); trm.set_defaults(func=_cmd_trust)
    tr.set_defaults(func=_cmd_trust)

    p.set_defaults(func=_cmd_status)