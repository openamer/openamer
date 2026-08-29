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
import json
import os


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
    """Verify a signed A2A object against a sender pubkey.

    Accepts two formats:
      - a signed Envelope (has ``sender``/``recipient``/``kind``)
      - a node Announcement (has ``fingerprint``/``public_key`` — as produced
        by ``openamer a2a self``)

    Usage: openamer a2a verify '<json>' <sender_public_key_hex>
    """
    if not args.json_payload or not args.sender_pubkey:
        print("Usage: openamer a2a verify '<envelope-or-announcement-json>' <sender_public_key_hex>")
        return 2
    try:
        data = json.loads(args.json_payload)
    except json.JSONDecodeError as e:
        print(f"Invalid envelope JSON: {e}")
        return 2
    if not isinstance(data, dict):
        print("Invalid object: expected a JSON object")
        return 2
    # Announcement format (as produced by `openamer a2a self`)
    if "fingerprint" in data and "public_key" in data:
        from openamer_cli.a2a.registry import Announcement
        ann = Announcement.from_dict(data)
        ok = ann.verify(trusted_pubkey_hex=args.sender_pubkey)
        print("VERIFIED" if ok else "INVALID")
        print(f"  fingerprint : {ann.fingerprint}")
        print(f"  name        : {ann.name}")
        print(f"  ts          : {ann.ts}")
        return 0 if ok else 1
    # Envelope format (sender/recipient/kind)
    env = core.Envelope.from_dict(data)
    ok = env.verify(args.sender_pubkey)
    print("VERIFIED" if ok else "INVALID")
    print(f"  sender    : {env.sender}")
    print(f"  recipient : {env.recipient}")
    print(f"  kind      : {env.kind}")
    return 0 if ok else 1


def _cmd_serve(args) -> int:
    """Serve the ARD ai-catalog over HTTP so `navigate <host>` autodiscovers."""
    from openamer_cli.a2a.catalog_serve import serve_cmd
    return serve_cmd(args)


def _cmd_discover(args) -> int:
    """Search the public ARD registry for agents/skills/MCP resources."""
    from openamer_cli.a2a import ard_client
    q = getattr(args, "query", "")
    if not q:
        print("Usage: openamer a2a discover <natural-language query> [--registry URL] [--limit N]")
        return 2
    reg = getattr(args, "registry", None) or ard_client.DEFAULT_REGISTRY
    limit = int(getattr(args, "limit", 5))
    results = ard_client.search_results(q, registry=reg, page_size=limit)
    print(f"[a2a discover] '{q}' — {len(results)} result(s) from ARD registry")
    if not results:
        print("  (no matches)")
        return 1
    for r in results:
        print(ard_client.format_result(r))
    return 0


def _cmd_mcp_catalog(args) -> int:
    """Search the MCP server catalog (keyless) for a ready-made tool.

    ``--install <name>`` routes a found server to the safe, supply-chain-pinned
    OpenAmer-approved catalog install path — never pins an arbitrary community
    repo without a manifest.
    """
    install_name = (getattr(args, "install", "") or "").strip()
    if install_name:
        from openamer_cli import mcp_catalog as curated
        entry = curated.get_entry(install_name)
        if entry is None:
            print(
                f"  ✗ '{install_name}' is not in OpenAmer's approved catalog. "
                "Only approved manifests are installable (supply-chain-pinned). "
                "Propose it as a manifest PR, or add a custom server with "
                "`openamer mcp add`."
            )
            return 1
        curated.install_entry(entry, enable=True)
        return 0

    from openamer_cli.a2a import mcp_catalog
    q = getattr(args, "query", "")
    limit = int(getattr(args, "limit", 10))
    entries = mcp_catalog.search(q, limit=limit)
    print(f"[a2a mcp-catalog] '{q or ''}' — {len(entries)} MCP server(s)")
    if not entries:
        print("  (catalog unreachable or no matches — check network)")
        return 1
    for e in entries:
        print(mcp_catalog.format_entry(e))
    return 0


def _cmd_delegate(args) -> int:
    """Delegate a task to the remote GitHub Actions worker via the new module."""
    from openamer_cli.a2a.delegate_cli import delegate_cmd
    return delegate_cmd(args.task, {
        "msg": getattr(args, "msg", ""),
        "text": getattr(args, "text", ""),
        "model": getattr(args, "model", ""),
        "wait": getattr(args, "wait", 300),
        "repo": getattr(args, "repo", None),
        "gh_repo": getattr(args, "gh_repo", None),
    })


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


def _cmd_relay(args) -> int:
    """Post / pull A2A messages over the GitHub relay (not localhost)."""
    from openamer_cli.a2a import relay as rl
    from openamer_cli.a2a import core as a2a_core
    import pathlib as _pl
    act = args.relay_cmd
    if act == "post":
        if not (args.question and args.relay_peer):
            print("Usage: openamer a2a relay post <peer_fingerprint> \"<question>\" [--repo-dir <dir>]")
            return 2
        # build a signed ask envelope
        identity = a2a_core.IdentityStore()
        me = identity.ensure_identity()
        from openamer_cli.a2a.core import Envelope
        env = Envelope.create(private_key=identity.private_key(), sender=me.fingerprint,
                              recipient=args.relay_peer, kind="ask",
                              payload={"question": args.question})
        note = rl.relay_note(identity_store=identity, envelope=env)
        # if a local relay repo dir is given, push it; else write to a mailbox dir
        if args.repo_dir:
            ok = rl.git_push_relay(_pl.Path(args.repo_dir), note)
            print(f"Relay note pushed to {args.repo_dir} (ok={ok})")
        else:
            mb = rl.RelayMailbox(_pl.Path.cwd() / "relay-inbox")
            f = mb.store(note)
            print(f"Relay note staged locally: {f} (push repo to GitHub directory/a2a/relay/)")
        return 0
    if act == "pull":
        mb = rl.RelayMailbox(_pl.Path(args.repo_dir or _pl.Path.cwd()/ "relay-inbox"))
        notes = mb.claim(args.mailbox or "*") if getattr(args, "once", False) \
            else [(None, n) for n in mb.pull(args.mailbox or "*")]
        if getattr(args, "purge", None) is not None:
            pb = mb.purge_consumed(max_age=args.purge)
            print(f"Purged {pb} consumed relay notes older than {args.purge}s.")
        print(f"Pulled {len(notes)} relay notes for mailbox {args.mailbox or '*'}.")
        for fname, n in notes:
            v = rl.verify_note(n)
            print(f"  [{'OK' if v['ok'] else v['reason']}] {n.get('sender')} -> {n.get('recipient')}")
        return 0
    print("Usage: openamer a2a relay post|pull"); return 2


def _cmd_ask(args) -> int:
    """Ask a trusted remote node a question (Node-to-Node A2A routing)."""
    from openamer_cli.a2a import transport
    identity = core.IdentityStore()
    trust_store = _trust()
    if getattr(args, "peers", None):
        # collective swarm ask: fan out to multiple peers
        urls = [u for u in args.peers if u]
        if not urls:
            print("Usage: openamer a2a ask --peers url1 url2 ... \"<question>\"")
            return 2
        res = transport.ask_many(identity, trust_store, urls, args.question or "",
                                 kind=args.kind or "ask")
        print(f"Swarm asked {res['total']} peers; {res['answered']} answered.")
        for a in res["answers"]:
            ok = "OK " if a["ok"] else "ERR"
            print(f"  [{ok}] {a['peer']}: {a['result']}")
        return 0 if res.get("ok") else 1
    if not args.peer_url or not args.question:
        print("Usage: openamer a2a ask <peer-http-url> \"<question>\" [--peers url1 url2 ...]")
        return 2
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


def _cmd_meshlearn(args) -> int:
    """Sign + stage a learning insight for the mesh, or adopt a verified one."""
    from openamer_cli.a2a import meshlearn
    from openamer_cli.a2a import selflearn
    import pathlib as _pl
    act = args.ml_cmd
    store = core.IdentityStore()
    if act == "auto":
        # Autonomous self-learning loop (no distill callback -> deterministic)
        mem = _pl.Path(args.memory or _pl.Path.home() / ".openamer" / "MEMORY-official-mesh.md")
        src = args.text or ""
        if not src:
            print("Usage: openamer a2a meshlearn auto \"<lesson text>\" [--topic t]")
            return 2
        res = selflearn.auto_learn(identity_store=store, memory_path=mem,
                                   learn_from=src, topic=args.topic or "general",
                                   title=args.title, skip_publish=True)
        if res.get("ok"):
            print(f"Learned+adopted into mesh memory: {res['insight_path']}")
            print(f"  source : {res['source']}@openamer | topic: {res['topic']} | sig: {res['signature_ok']}")
        else:
            print(f"Error: {res.get('error')}")
            return 1
        return 0
    if act == "learn":
        title = args.title or ""
        body = args.body or ""
        topic = args.topic or "general"
        if not title or not body:
            print("Usage: openamer a2a meshlearn learn <title> \"<body>\" [--topic <t>]")
            return 2
        ins = meshlearn.Insight.build(identity_store=store, title=title, body=body, topic=topic)
        out = _pl.Path(args.out or _pl.Path.home()/".openamer"/"a2a"/"insights")
        f = meshlearn.publish(ins, out)
        print(f"Signed insight staged for mesh: {f}")
        print(f"  topic     : {topic}")
        print(f"  source    : {ins.source}@openamer")
        print("Commit this file to directory/a2a/insights/ in github.com/openamer/openamer to share.")
        return 0
    if act == "adopt":
        if not args.json_file:
            print("Usage: openamer a2a meshlearn adopt <insight.json>")
            return 2
        import pathlib as _p
        pj = _p.Path(args.json_file)
        if not pj.exists():
            print(f"Error: {args.json_file} not found"); return 1
        ins = meshlearn.Insight.from_dict(json.loads(pj.read_text(encoding="utf-8")))
        mem = _pl.Path(args.memory or _pl.home()/".openamer"/"MEMORY-official-mesh.md")
        ok = meshlearn.adopt(ins, mem)
        print("Adopted into mesh memory" if ok else "REJECTED (bad signature or not fresh)")
        return 0 if ok else 1
    print("Unknown meshlearn subcommand."); return 2


def _cmd_brain(args) -> int:
    """Collect learning material OR toggle automatic activity capture."""
    from openamer_cli.a2a import braindata
    from openamer_cli.a2a import autolog
    import pathlib as _pl
    subject = args.brain_cmd
    # --- autolog subcommand (on/off/status) ---
    if subject == "autolog" or (subject in ("on", "off", "status") and hasattr(args, "autolog_sub")):
        sub = getattr(args, "autolog_sub", subject)
        if sub == "on":
            autolog.enable(); print("Autolog ON — all OpenAmer activity now flows to the brain dataset."); return 0
        if sub == "off":
            autolog.disable(); print("Autolog OFF."); return 0
        if sub == "status":
            print("Autolog:", "ON" if autolog.enabled() else "OFF"); return 0
    if subject == "autolog":
        print("Usage: openamer a2a brain autolog on|off|status"); return 2
    if subject == "share":
        from openamer_cli.a2a.brain_share import cmd_brain_share
        cmd_brain_share(args)
        return 0
    if subject != "collect" and subject != "publish":
        print("Usage: openamer a2a brain collect|publish|autolog <on|off|status>"); return 2
    home = _pl.Path.home() / ".openamer"
    if subject == "publish":
        # Public ONLY curated, redacted insights -> shared directory/a2a/insights
        repo_shared = _pl.Path(getattr(args, "out", "") or _pl.Path.cwd() / "directory" / "a2a" / "insights")
        mem = _pl.Path(args.memory or home / "MEMORY-official-mesh.md")
        n = braindata.publish_curated(insights=mem, out_dir=repo_shared)
        print(f"Shared {n} curated (redacted) insights to {repo_shared}")
        print("  (raw activity stays local; only verified, privacy-scrubbed knowledge is shared)")
        return 0
    # gather trajectory files (both success + failure) under the home/openamer data dir
    traj_dirs = [
        home / "trajectories", home / "logs", home / "data",
        _pl.Path(os.getenv("OPENAMER_HOME") or home),
    ]
    traj_files: list = []
    for d in args.traj_dirs or [str(td) for td in traj_dirs]:
        p = _pl.Path(d)
        if p.exists():
            for f in p.rglob("*.jsonl"):
                if "traject" in f.name:
                    traj_files.append(f)
    # mesh memory
    mem = _pl.Path(args.memory or home / "MEMORY-official-mesh.md")
    outpath = _pl.Path(args.out or home / "a2a" / "openamer-brain.jsonl")
    res = braindata.build_dataset(trajectories=traj_files, insights=mem, out=outpath,
                                  skills=[])
    print(f"OpenAmer brain dataset written: {outpath}")
    print(f"  records: {res['records']}  ({res['sources']})")
    return 0


def _cmd_skill(args) -> int:
    """Sign / verify a skill for the A2A mesh."""
    from openamer_cli.a2a import skillshare
    act = args.skill_cmd
    store = core.IdentityStore()
    if act == "sign":
        if not args.skill_dir:
            print("Usage: openamer a2a skill sign <skill_dir>")
            return 2
        import pathlib as _pl
        sd = _pl.Path(args.skill_dir)
        try:
            out = skillshare.publish(sd, _pl.Path(args.out or _pl.Path.home()/".openamer" / "a2a" / "skills"),
                                     identity_store=store)
        except ValueError as e:
            print(f"Error: {e}"); return 1
        print(f"Signed skill manifest: {out}")
        m = skillshare.SkillManifest.from_dict(_json_load(out))
        print(f"  publisher : {m.publisher}@openamer")
        print(f"  files     : {len(m.files)}")
        return 0
    if act == "verify":
        if not args.skill_dir:
            print("Usage: openamer a2a skill verify <skill_dir> [--manifest <json>]")
            return 2
        import pathlib as _pl
        sd = _pl.Path(args.skill_dir)
        mpath = _pl.Path(args.manifest) if args.manifest else None
        if mpath is None:
            # find sibling manifest
            cand = _pl.Path(str(sd) + ".json")
            if cand.exists(): mpath = cand
            else:
                cand2 = sd / ".." / f"{sd.name}.json"
                if cand2.exists(): mpath = cand2
        if mpath is None or not mpath.exists():
            print("Error: no manifest found (pass --manifest)."); return 1
        m = skillshare.SkillManifest.from_dict(json.loads(mpath.read_text(encoding="utf-8")))
        res = m.verify_all(sd)
        print(f"signature_ok : {res['signature_ok']}")
        print(f"content_ok   : {res['content_ok']}")
        return 0 if (res["signature_ok"] and res.get("content_ok")) else 1
    print("Unknown skill subcommand."); return 2

def _json_load(p):
    import json
    return json.loads(p.read_text(encoding="utf-8"))

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


def _cmd_query(args) -> int:
    """Ask a question across the A2A swarm mesh (peer-to-peer query)."""
    from openamer_cli.a2a import query as a2a_query
    from openamer_cli.a2a.trust import TrustStore
    from openamer_cli.a2a.core import IdentityStore
    import time as _time

    if not args.question:
        print("Usage: openamer a2a query \"<question>\" [--timeout N] [--max-peers N] [--local]")
        return 2

    t0 = _time.monotonic()
    identity = IdentityStore()
    trust_store = TrustStore()

    # Optionally query local brain first
    local_text = ""
    if args.local:
        local_text = a2a_query.answer_locally(args.question)
        elapsed = int((_time.monotonic() - t0) * 1000)
        print(f"Local answer ({elapsed}ms):")
        print(f"  {local_text}")
        print()

    res = a2a_query.query_mesh(
        args.question,
        max_peers=args.max_peers or 5,
        timeout=args.timeout or 60,
        identity=identity,
        trust_store=trust_store,
    )

    elapsed = int((_time.monotonic() - t0) * 1000)
    print(f"Mesh query: {res.peers_contacted} peers contacted, "
          f"{res.peers_answered} answered ({elapsed}ms total)")
    print()

    if res.answers:
        # Show ranked answers
        for i, a in enumerate(res.answers, 1):
            status = "OK" if a.ok else "ERR"
            trust_str = f"trust={a.trust_score:.2f}"
            lat_str = f"latency={a.latency_ms}ms"
            name = a.peer_name or a.peer_fingerprint[:12]
            print(f"  #{i} [{status}] {name} ({trust_str}, {lat_str})")
            if a.ok and a.answer:
                # Truncate long answers for display
                disp = a.answer[:300] + "..." if len(a.answer) > 300 else a.answer
                print(f"      {disp}")
            elif not a.ok and a.error:
                print(f"      error: {a.error}")
    elif res.local_answer:
        if not args.local:
            print("No peer answers received.")
            print(f"Fallback: {res.local_answer}")
    else:
        print("No answers received from the mesh.")

    return 0 if res.peers_answered > 0 else 1


def _cmd_mesh(args) -> int:
    """Handle ``openamer a2a mesh learn|publish|import|stats``."""
    from openamer_cli.a2a.mesh_learning import MeshLearningCoordinator
    import json as _json

    coord = MeshLearningCoordinator()
    cmd = args.mesh_cmd

    if cmd == "publish":
        lesson = getattr(args, "lesson", None)
        title = getattr(args, "title", None)
        body = getattr(args, "body", None)
        topic = getattr(args, "topic", "general")

        if lesson:
            try:
                lesson_dict = _json.loads(lesson)
            except _json.JSONDecodeError:
                print("Invalid JSON for lesson argument.")
                return 2
        elif title and body:
            lesson_dict = {"title": title, "body": body, "topic": topic}
        else:
            print("Usage: openamer a2a mesh publish '<json>' or --title <title> --body <body> [--topic <topic>]")
            return 2

        result = coord.publish_lesson(lesson_dict)
        print(f"Lesson published: {result['lesson_id']}")
        print(f"  source: {result['source']}")
        print(f"  topic: {result['topic']}")
        print(f"  path: {result['path']}")
        return 0

    elif cmd == "import":
        max_lessons = getattr(args, "max_lessons", 20)
        lessons = coord.import_lessons_from_mesh(max_lessons=max_lessons)
        if not lessons:
            print("No lessons found in the mesh.")
            return 0
        print(f"Found {len(lessons)} lessons from the mesh:")
        for i, les in enumerate(lessons, 1):
            title = les.get("title", "(untitled)")
            topic = les.get("topic", "general")
            source = les.get("source", "unknown")[:12]
            print(f"  #{i} [{topic}] {title} (from {source})")
        return 0

    elif cmd == "stats":
        stats = coord.get_mesh_learning_stats()
        print("Mesh Learning Statistics:")
        print(f"  Lessons published   : {stats['lessons_published']}")
        print(f"  Lessons imported    : {stats['lessons_imported']}")
        print(f"  Memory entries      : {stats['memory_entries']}")
        print(f"  Local skills        : {stats['local_skills']}")
        print(f"  Last published      : {stats['last_published'] or 'never'}")
        print(f"  Topics              : {stats['topics']}")
        return 0

    elif cmd == "learn":
        result = coord.run_mesh_learning_cycle()
        print("Mesh Learning Cycle complete:")
        print(f"  Lessons published: {result.get('published', 0)}")
        print(f"  Lessons imported : {result.get('imported', 0)}")
        print(f"  Lessons applied  : {result.get('applied', 0)}")
        return 0

    print("Unknown mesh subcommand.")
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
    aq.add_argument("--peers", nargs="*", default=None, help="ask multiple peers (collective swarm)")
    aq.set_defaults(func=_cmd_ask)

    dv = sub.add_parser("delegate",
                            help="Delegate a task to the remote GitHub Actions worker (A2A over the internet)")
    dv.add_argument("task", nargs="?", choices=["ping", "echo", "time", "sum", "ask"])
    dv.add_argument("--msg", default="", help="prompt / message")
    dv.add_argument("--text", default="", help="payload text (echo)")
    dv.add_argument("--model", default="", help="LLM model (ask)")
    dv.add_argument("--wait", type=int, default=300, help="poll seconds")
    dv.add_argument("--repo", default=None, help="path to the relay repo checkout")
    dv.add_argument("--gh-repo", default="openamer/openamer", help="GitHub relay repo owner/name")
    dv.set_defaults(func=_cmd_delegate)

    sv = sub.add_parser("serve", help="Serve the ARD ai-catalog over HTTP (so navigate <host> can autodiscover the agent)")
    sv.add_argument("--port", type=int, default=8799)
    sv.add_argument("--host", default="127.0.0.1")
    sv.add_argument("--catalog", default=None,
                    help="path to ai-catalog.json (default: repo docs/)")
    sv.set_defaults(func=_cmd_serve)

    di = sub.add_parser("discover", help="Search the public ARD registry for agents/skills/MCP resources")
    di.add_argument("query", nargs="?", help="natural-language query")
    di.add_argument("--registry", default=None, help="ARD registry URL (default: HF public)")
    di.add_argument("--limit", type=int, default=5, help="max results")
    di.set_defaults(func=_cmd_discover)

    mc = sub.add_parser("mcp-catalog", help="Search the (keyless) MCP server catalog for a ready-made tool")
    mc.add_argument("query", nargs="?",
                    help="keyword(s), e.g. 'github' or 'postgres|mysql' or '\"web scraping\"'")
    mc.add_argument("--limit", type=int, default=10)
    mc.add_argument("--install", metavar="NAME",
                    help="install an approved entry by catalog name (safe, pinned path) instead of searching")
    mc.set_defaults(func=_cmd_mcp_catalog)

    rl = sub.add_parser("relay", help="GitHub relay transport (A2A over the repo, not localhost)")
    rl_sub = rl.add_subparsers(dest="relay_cmd")
    rp = rl_sub.add_parser("post", help="Post a signed, redacted message for a peer")
    rp.add_argument("relay_peer", nargs="?")
    rp.add_argument("question", nargs="?")
    rp.add_argument("--repo-dir", default=None)
    rp.set_defaults(func=_cmd_relay)
    rpull = rl_sub.add_parser("pull", help="Pull + verify relay notes for a mailbox")
    rpull.add_argument("mailbox", nargs="?"); rpull.add_argument("--repo-dir", default=None)
    rpull.add_argument("--once", action="store_true",
                   help="Consume each note exactly once (dedup across pulls)")
    rpull.add_argument("--purge", type=int, default=None, metavar="SECONDS",
                   help="Delete already-consumed notes older than SECONDS")
    rpull.set_defaults(func=_cmd_relay)
    rl.set_defaults(func=_cmd_relay)

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

    sk = sub.add_parser("skill", help="Sign / verify skills for the A2A mesh")
    sk_sub = sk.add_subparsers(dest="skill_cmd")
    ss = sk_sub.add_parser("sign", help="Sign a skill into a verifiable manifest")
    ss.add_argument("skill_dir", nargs="?"); ss.add_argument("--out", default=None)
    ss.set_defaults(func=_cmd_skill)
    sv = sk_sub.add_parser("verify", help="Verify a skill against its signed manifest")
    sv.add_argument("skill_dir", nargs="?"); sv.add_argument("--manifest", default=None)
    sv.set_defaults(func=_cmd_skill)
    sk.set_defaults(func=_cmd_skill)

    ml = sub.add_parser("meshlearn", help="Mesh learning memory (sign/share/adopt insights)")
    ml_sub = ml.add_subparsers(dest="ml_cmd")
    ml_learn = ml_sub.add_parser("learn", help="Sign + stage a learning insight")
    ml_learn.add_argument("title", nargs="?"); ml_learn.add_argument("body", nargs="?")
    ml_learn.add_argument("--topic", default="general"); ml_learn.add_argument("--out", default=None)
    ml_learn.set_defaults(func=_cmd_meshlearn)
    ml_auto = ml_sub.add_parser("auto", help="Autonomous self-learning loop (distill+sign+adopt)")
    ml_auto.add_argument("text", nargs="?"); ml_auto.add_argument("--topic", default="general")
    ml_auto.add_argument("--title", default=None); ml_auto.add_argument("--memory", default=None)
    ml_auto.set_defaults(func=_cmd_meshlearn)
    ml_adopt = ml_sub.add_parser("adopt", help="Adopt a verified insight into mesh memory")
    ml_adopt.add_argument("json_file", nargs="?"); ml_adopt.add_argument("--memory", default=None)
    ml_adopt.set_defaults(func=_cmd_meshlearn)
    ml.set_defaults(func=_cmd_meshlearn)

    br = sub.add_parser("brain", help="Collect learning material for the OpenAmer model (feed the brain)")
    br_sub = br.add_subparsers(dest="brain_cmd")
    bc = br_sub.add_parser("collect", help="Build a training dataset from trajectories + insights")
    bc.add_argument("--out", default=None); bc.add_argument("--memory", default=None)
    bc.add_argument("--traj-dirs", nargs="*", default=None)
    bc.set_defaults(func=_cmd_brain)
    bp = br_sub.add_parser("publish", help="Share ONLY curated, redacted insights to directory/a2a/insights")
    bp.add_argument("--out", default=None); bp.add_argument("--memory", default=None)
    bp.set_defaults(func=_cmd_brain)
    ba = br_sub.add_parser("autolog", help="Toggle automatic activity capture (on|off|status)")
    ba.add_argument("autolog_sub", nargs="?", default="status", choices=["on", "off", "status"])
    ba.set_defaults(func=_cmd_brain)
    br.set_defaults(func=_cmd_brain)

    # brain share subcommand
    bs = br_sub.add_parser("share", help="Share and import brain insights across the A2A swarm")
    bs.add_argument("brain_share_action", nargs="?", choices=["export", "import", "list"], default=None, help="Action")
    bs.add_argument("source", nargs="?", default="", help="Source file (for import)")
    bs.set_defaults(func=_cmd_brain)

    q = sub.add_parser("query", help="Ask a question across the A2A swarm mesh (peer-to-peer)")
    q.add_argument("question", nargs="?", help="the question to ask peers")
    q.add_argument("--local", action="store_true", help="query local brain first, then peers")
    q.add_argument("--timeout", type=int, default=60, help="per-peer timeout in seconds (default 60)")
    q.add_argument("--max-peers", type=int, default=5, help="max peers to contact (default 5)")
    q.set_defaults(func=_cmd_query)

    # =========================================================================
    # mesh subcommand — advanced mesh learning (coordinate, publish, import)
    # =========================================================================
    mesh = sub.add_parser(
    "mesh",
    help="Advanced mesh learning — publish, import, and coordinate cross-node learning",
    )
    mesh_sub = mesh.add_subparsers(dest="mesh_cmd")
    ml = mesh_sub.add_parser("learn", help="Run the full mesh learning cycle (publish local + import peers)")
    ml.set_defaults(func=_cmd_mesh)
    mp = mesh_sub.add_parser("publish", help="Publish a signed lesson to the mesh")
    mp.add_argument("lesson", nargs="?", help="JSON string with title/body/topic for the lesson")
    mp.add_argument("--title", default=None, help="Lesson title")
    mp.add_argument("--body", default=None, help="Lesson body")
    mp.add_argument("--topic", default="general", help="Lesson topic")
    mp.set_defaults(func=_cmd_mesh)
    mi = mesh_sub.add_parser("import", help="Import lessons from peer mesh nodes")
    mi.add_argument("--max", type=int, default=20, dest="max_lessons", help="Maximum lessons to import (default 20)")
    mi.set_defaults(func=_cmd_mesh)
    ms = mesh_sub.add_parser("stats", help="Show mesh learning statistics")
    ms.set_defaults(func=_cmd_mesh)
    p.set_defaults(func=_cmd_status)
