#!/usr/bin/env python3
"""openamer replication - encrypted state replication (DIR-01).

Two halves, two commands:

    openamer replication status          # module, key, verified snapshot, peers
    openamer replication selftest        # seal + restore + verify every hash now
    openamer replication peers           # registered targets and their last push
    openamer replication push <url>      # send the sealed snapshot to a peer
    openamer replication serve           # BE the peer: accept envelopes on :8765

`serve` is the missing piece for the second machine: run it there, register that
address here, and `push` delivers a snapshot the peer stores without ever being
able to read it (AES-256-GCM, key stays on the sender).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _load():
    repo = _repo_root()
    if str(repo) not in sys.path:
        sys.path.insert(0, str(repo))
    from agent import replication

    return replication


def _load_network():
    repo = _repo_root()
    if str(repo) not in sys.path:
        sys.path.insert(0, str(repo))
    from agent import replication_network

    return replication_network


def _render_network(state: dict) -> str:
    lines = [
        "replication network (DIR-01, internet)",
        f"  enabled        {'yes' if state['enabled'] else 'NO (opt-in: OPENAMER_REPLICATION_NETWORK=1)'}",
        f"  node id        {state.get('node_id') or '-'}",
        f"  directory      {state.get('directory') or '- (set replication.directory_url)'}",
        f"  last sync      "
        + (
            f"{'OK' if state['last_sync_ok'] else 'FAILED'} · {state['last_sync_peers']} peer(s) · "
            f"{state['last_sync_age_s']}s ago"
            if state.get("last_sync_age_s") is not None
            else "never"
        ),
    ]
    return "\n".join(lines)


def _cmd_replication(args) -> int:
    rep = _load()
    action = getattr(args, "action", None) or "status"

    if action in ("network-status", "join", "sync"):
        network = _load_network()

        if action == "network-status":
            state = network.network_status()
            print(json.dumps(state, indent=2) if getattr(args, "json", False) else _render_network(state))
            return 0 if (state["enabled"] and state["last_sync_ok"]) else 2

        if action == "join":
            # Opt-in: publishing a node address to a directory is a decision.
            import os as _os

            _os.environ["OPENAMER_REPLICATION_NETWORK"] = "1"
            if getattr(args, "directory", None):
                _os.environ["OPENAMER_REPLICATION_DIRECTORY"] = args.directory
            report = network.announce_and_sync(args.url, directory=getattr(args, "directory", None))
            print(json.dumps(report, indent=2))
            return 0 if report.get("ok") else 1

        report = network.announce_and_sync(args.url, directory=getattr(args, "directory", None) or None)
        print(json.dumps(report, indent=2))
        return 0 if report.get("ok") else 1

    if action == "status":
        state = rep.status()
        print(json.dumps(state, indent=2) if getattr(args, "json", False) else _render_status(state))
        # Exit 2 while the peer half is missing: scripts and cron can tell
        # "artifact proven, redundancy absent" from "everything fine".
        return 0 if state["peers"] else 2

    if action == "selftest":
        result = rep.selftest(profile=getattr(args, "profile", "fast") or "fast")
        print(json.dumps(result, indent=2))
        return 0 if result.get("ok") else 1

    if action == "peers":
        peers = rep.load_peers()
        if not peers:
            print("no peers registered — the redundancy half of DIR-01 is unmeasured (0 nodes)")
            return 2
        for peer in peers:
            print(f"{peer['url']:<45} {peer.get('name', '')}")
        return 0

    if action == "push":
        url = args.url
        key = rep.load_or_create_key()
        sources = [rep._home() / part for part in rep.DEFAULT_SOURCES]
        sources = [path for path in sources if path.exists()]
        skipped: list[dict] = []
        bundle, entries = rep.build_bundle(sources, skipped_out=skipped)
        envelope = rep.seal(bundle, entries, key)
        result = rep.push(envelope, url, timeout=float(getattr(args, "timeout", 60) or 60))
        print(
            json.dumps(
                {
                    **result,
                    "files": len(entries),
                    "bytes": sum(entry["size"] for entry in entries),
                    "envelope_bytes": len(envelope),
                    "skipped_files": len(skipped),
                },
                indent=2,
            )
        )
        return 0

    if action == "serve":
        return rep.serve(
            host=getattr(args, "host", "127.0.0.1") or "127.0.0.1",
            port=int(getattr(args, "port", 8765) or 8765),
            keep=int(getattr(args, "keep", 5) or 5),
        )

    print(f"unknown action {action!r}", file=sys.stderr)
    return 1


def _render_status(state: dict) -> str:
    age = state.get("last_selftest_age_s")
    lines = [
        "replication (DIR-01)",
        f"  module            present",
        f"  key               {'present' if state['key_present'] else 'MISSING'}",
        f"  last selftest     {'OK' if state['last_selftest_ok'] else 'never/FAILED'}"
        + (
            f" · {state['last_selftest_files']} files · {state['last_selftest_bytes']} B"
            f" · {state.get('last_selftest_profile') or '?'} · {age}s ago"
            if state["last_selftest_ok"]
            else ""
        ),
        f"  peers             {state['peers']}"
        + ("" if state["peers"] else "   <-- redundancy half unmeasured"),
    ]
    return "\n".join(lines)


def build_replication_parser(subparsers) -> None:
    """Wire `openamer replication`."""
    p = subparsers.add_parser(
        "replication",
        help="Verschluesselte Zustands-Replikation (DIR-01): Snapshot, Peers, Peer-Server",
        description=(
            "DIR-01 hat zwei Haelften: ein Artefakt, das nachweislich wiederherstellbar ist "
            "(selftest), und einen zweiten Knoten (peers/push/serve). `serve` macht diesen "
            "Rechner zum Peer; er speichert nur Chiffrat und kann den Snapshot ohne "
            "Schluessel nicht lesen."
        ),
    )
    sub = p.add_subparsers(dest="action")
    sub.required = False

    status = sub.add_parser("status", help="Zustand: Schluessel, letzter Selftest, Peers")
    status.add_argument("--json", action="store_true")

    selftest = sub.add_parser("selftest", help="Snapshot versiegeln, wiederherstellen, jede Datei pruefen")
    selftest.add_argument("--profile", choices=["fast", "full"], default="fast")

    sub.add_parser("peers", help="registrierte Ziele")

    push = sub.add_parser("push", help="versiegelten Snapshot an einen Peer senden")
    push.add_argument("url", help="http(s)://host:port (nicht-loopback nur mit https)")
    push.add_argument("--timeout", type=float, default=60.0)

    serve = sub.add_parser("serve", help="als Peer laufen: POST /replication/accept speichern")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8765)
    serve.add_argument("--keep", type=int, default=5, help="wie viele Envelopes aufbewahrt werden")

    net_status = sub.add_parser(
        "network-status",
        help="Internet-Replikation: aktiviert? Knoten-ID, Verzeichnis, letzter Sync",
    )
    net_status.add_argument("--json", action="store_true")

    join = sub.add_parser(
        "join",
        help="Netzwerk beitreten: Knoten veroeffentlichen und an alle Peers versiegelt senden",
    )
    join.add_argument("url", help="oeffentlich erreichbare URL dieses Knotens, z.B. https://host:8765")
    join.add_argument("--directory", default=None, help="Verzeichnis-URL (sonst aus der Config)")

    sync = sub.add_parser("sync", help="erneut veroeffentlichen und an alle gefundenen Peers senden")
    sync.add_argument("url")
    sync.add_argument("--directory", default=None)

    p.set_defaults(func=_cmd_replication)
