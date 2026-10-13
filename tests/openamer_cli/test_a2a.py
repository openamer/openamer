"""Tests for openamer_cli.a2a — identity, envelope, trust, transport, registry.

These exercise real crypto (Ed25519) with no network. They mirror the repo's
pytest style and give durable verification for the A2A feature.
"""
import json
import pathlib
import tempfile
import threading
from http.server import ThreadingHTTPServer

import pytest

from openamer_cli import a2a  # noqa: F401  (package import)
from openamer_cli.a2a import core, trust, transport, registry


# --- identity --------------------------------------------------------------

def test_identity_generate_roundtrip():
    priv, pub = core.generate_identity()
    assert len(priv) == 64 and len(pub) == 64
    ident = core.NodeIdentity(public_key=pub, fingerprint="")
    assert ident.fingerprint == core.pubkey_fingerprint(pub)
    assert len(ident.fingerprint) == 16


def test_identity_store_persists(tmp_path):
    store = core.IdentityStore(tmp_path)
    a = store.ensure_identity()
    b = store.load()
    assert a.public_key == b.public_key
    assert store.exists()


# --- envelope --------------------------------------------------------------

def test_envelope_verify_authentic(tmp_path):
    store_a = core.IdentityStore(tmp_path / "a")
    a = store_a.ensure_identity()
    env = core.Envelope.create(
        private_key=store_a.private_key(), sender=a.fingerprint,
        recipient="peer", kind="ping", payload={"hi": "ok"},
    )
    assert env.verify(a.public_key)


def test_envelope_reject_tamper(tmp_path):
    store_a = core.IdentityStore(tmp_path / "a")
    a = store_a.ensure_identity()
    env = core.Envelope.create(
        private_key=store_a.private_key(), sender=a.fingerprint,
        recipient="peer", kind="ping", payload={"hi": "ok"},
    )
    d = core.Envelope.from_dict(env.to_dict())
    d.payload = {"hi": "MODIFIED"}
    assert d.verify(a.public_key) is False


def test_envelope_reject_future():
    # build a private key directly; deterministic via IdentityStore in temp
    with tempfile.TemporaryDirectory() as td:
        store = core.IdentityStore(pathlib.Path(td))
        ident = store.ensure_identity()
        env = core.Envelope.create(
            private_key=store.private_key(), sender=ident.fingerprint,
            recipient="x", kind="ping", payload={}, ts=9999999999,
        )
        assert env.verify(ident.public_key) is False


# --- trust -----------------------------------------------------------------

def test_trust_grant_flow(tmp_path):
    ts = trust.TrustStore(tmp_path)
    ts.add_peer("fp1", "k" * 64, name="n1")
    assert ts.trusted("fp1") is not None
    g = ts.grant("fp1", "task.sum", budget=0)
    assert g.capability == "task.sum"
    assert ts.has_grant("fp1", "task.sum")
    assert not ts.has_grant("fp1", "task.other")
    assert ts.revoke("fp1", "task.sum") == 1
    assert not ts.has_grant("fp1", "task.sum")


def test_trust_persists(tmp_path):
    tv = trust.TrustStore(tmp_path)
    tv.add_peer("fp", "p" * 64)
    tv2 = trust.TrustStore(tmp_path)
    assert tv2.trusted("fp") is not None


# --- registry --------------------------------------------------------------

def test_registry_announcement_sign_verify(tmp_path):
    store = core.IdentityStore(tmp_path)
    ident = store.ensure_identity()
    ann = registry.Announcement.create(
        private_key=store.private_key(), fingerprint=ident.fingerprint,
        public_key=ident.public_key, name="n", endpoints=["https://x"],
        capabilities=["task.sum"],
    )
    assert ann.verify() is True
    # wrong pin -> reject
    other = core.IdentityStore(tmp_path / "o").ensure_identity()
    assert ann.verify(trusted_pubkey_hex=other.public_key) is False
    # tamper -> reject
    tampered = registry.Announcement.from_dict(ann.to_dict())
    tampered.name = "HACK"
    assert tampered.verify() is False


def test_registry_sign_announcement(tmp_path):
    ann = registry.sign_announcement(home=tmp_path, capabilities=["task.sum"])
    assert ann.verify()
    assert "task.sum" in ann.capabilities


# --- transport -------------------------------------------------------------

def _start_node(tmp_path):
    ts = trust.TrustStore(tmp_path)
    ident_store = core.IdentityStore(tmp_path)
    srv = transport.A2ANodeServer(host="127.0.0.1", port=0, trust=ts,
                                  identity=ident_store,
                                  on_task=lambda env, pd=None: {"got": env.kind})
    return srv, ts, ident_store


def test_transport_e2e_grant_and_reject(tmp_path):
    # two homes: server (A) node, client (B) node
    homeA = pathlib.Path(tmp_path) / "A"; homeB = pathlib.Path(tmp_path) / "B"
    idA = core.IdentityStore(homeA); a = idA.ensure_identity()
    idB = core.IdentityStore(homeB); b = idB.ensure_identity()
    tsA = trust.TrustStore(homeA)
    srv = transport.A2ANodeServer(host="127.0.0.1", port=0, trust=tsA,
                                  identity=idA,
                                  on_task=lambda env, pd=None: {"kind": env.kind})
    th = threading.Thread(target=srv.serve_forever, daemon=True); th.start()
    base = f"http://127.0.0.1:{srv.port}"
    # card
    card = transport.fetch_card(f"{base}/card")
    assert card["agent_card"]["fingerprint"] == a.fingerprint
    # untrusted ping -> 403
    env = core.Envelope.create(private_key=idB.private_key(), sender=b.fingerprint,
                               recipient=a.fingerprint, kind="ping", payload={})
    r = transport.send_message(f"{base}/message", env)
    assert "not trusted" in r.get("error", r.get("http_status") and "403")
    # trust B, no grant -> 403
    tsA.add_peer(b.fingerprint, b.public_key, name="B")
    env2 = core.Envelope.create(private_key=idB.private_key(), sender=b.fingerprint,
                                recipient=a.fingerprint, kind="sum", payload={"a": 2, "b": 3})
    r2 = transport.send_message(f"{base}/message", env2)
    assert "no grant" in r2.get("error", r2.get("http_status") and "403")
    # grant task.sum -> 200
    tsA.grant(b.fingerprint, "task.sum")
    r3 = transport.send_message(f"{base}/message", env2)
    assert r3.get("ok") is True and r3.get("kind") == "sum"
    srv.shutdown()


def test_a2a_ask_roundtrip(tmp_path):
    """A questioner node asks a trusted, granted server node via HTTP and
    receives the signed-server's answer."""
    import threading as _th
    idQ = core.IdentityStore(tmp_path / "q"); Q = idQ.ensure_identity()
    idA = core.IdentityStore(tmp_path / "a"); A = idA.ensure_identity()
    trA = trust.TrustStore(tmp_path / "a")
    def on_task(env, pd=None):
        return {"answer": "got " + str((env.payload or {}).get("question", ""))}
    srv = transport.A2ANodeServer(host="127.0.0.1", port=0, trust=trA,
                                  identity=idA, on_task=on_task)
    th = _th.Thread(target=srv.serve_forever, daemon=True); th.start()
    base = f"http://127.0.0.1:{srv.port}"
    trQ = trust.TrustStore(tmp_path / "q")
    trQ.add_peer(A.fingerprint, A.public_key, name="server")
    trA.add_peer(Q.fingerprint, Q.public_key, name="questioner")
    trA.grant(Q.fingerprint, "task.ask")
    res = transport.ask(idQ, trQ, base, "what is 2+2?", kind="ask")
    srv.shutdown()
    assert res.get("ok") is True
    assert "got what is 2+2?" in str(res.get("result", {}))


def test_skill_manifest_sign_verify(tmp_path):
    """Signed skill manifest: publish, verify, and reject tampering."""
    from openamer_cli.a2a import skillshare as sks
    os = tmp_path
    store = core.IdentityStore(tmp_path / "id")
    ds = tmp_path / "demo"; ds.mkdir(parents=True, exist_ok=True)
    (ds / "SKILL.md").write_text("# Demo", encoding="utf-8")
    (ds / "tool.py").write_text("x=1", encoding="utf-8")
    outdir = tmp_path / "pub"
    mfile = sks.publish(ds, outdir, identity_store=store)
    m = sks.SkillManifest.from_dict(__import__("json").loads(mfile.read_text()))
    assert m.verify_signature() is True
    assert m.verify_directory(ds) is True
    (ds / "tool.py").write_text("x=2", encoding="utf-8")  # tamper
    assert m.verify_directory(ds) is False
    m2 = sks.SkillManifest.from_dict(__import__("json").loads(mfile.read_text()))
    m2.name = "hack"
    assert m2.verify_signature() is False


def test_meshlearn_insight_publish_adopt(tmp_path):
    """Node learns -> signs an insight -> staged for mesh; verified adopt works;
    tampered/manipulated insight is rejected."""
    from openamer_cli.a2a import meshlearn as ml
    store = core.IdentityStore(tmp_path / "id")
    ins = ml.Insight.build(identity_store=store, title="RuntimeError fix",
                           body="initialize reactor after event loop starts", topic="debug")
    assert ins.verify() is True
    out = tmp_path / "insights"
    f = ml.publish(ins, out)
    assert f.exists()
    loaded = ml.Insight.from_dict(__import__("json").loads(f.read_text()))
    assert loaded.verify() is True
    mem = tmp_path / "MEMORY.md"
    assert ml.adopt(loaded, mem) is True
    assert "RuntimeError fix" in mem.read_text()
    # tampered -> reject
    bad = ml.Insight.from_dict(__import__("json").loads(f.read_text()))
    bad.body = "rm -rf /"
    assert ml.adopt(bad, mem) is False
    # de-dupe
    assert ml.adopt(loaded, mem) is True
    assert mem.read_text().count("RuntimeError fix") == 1


def test_selflearn_auto_loop(tmp_path):
    """Autonomous self-learn: distill -> sign -> adopt into mesh memory; dedupe."""
    from openamer_cli.a2a import selflearn as sl
    store = core.IdentityStore(tmp_path / "id")
    mem = tmp_path / "MEMORY.md"
    out = tmp_path / "insights"
    def distill(exp, topic):
        return ("Use staged builds", "cache layers to speed CI",)
    res = sl.auto_learn(identity_store=store, memory_path=mem,
                        learn_from="slow CI", topic="devops",
                        distill=distill, publish_dir=out, skip_publish=False)
    assert res["ok"] and res["signature_ok"] and res["adopted"] and res["staged"]
    entries = sl.parse_mesh_memory(mem)
    assert any("staged builds" in e["title"] for e in entries)
    # second identical learn must not duplicate
    res2 = sl.auto_learn(identity_store=store, memory_path=mem,
                         learn_from="done CI", topic="devops", distill=distill,
                         publish_dir=out, skip_publish=False)
    assert res2["ok"]
    assert mem.read_text().count("Use staged builds") == 1


def test_braindata_build_dataset(tmp_path):
    """Collect learning material (trajectories + mesh insights) into JSONL."""
    from openamer_cli.a2a import braindata as bd
    import json
    tj = tmp_path / "trajectory_samples.jsonl"
    rec = {"messages": [{"role": "system", "content": "s"},
                        {"role": "user", "content": "how to X?"},
                        {"role": "assistant", "content": "do Y"}]}
    tj.write_text(json.dumps(rec) + "\n", encoding="utf-8")
    mem = tmp_path / "MEMORY.md"
    mem.write_text("#mesh:debug: Close DB conn - use finally block.\n", encoding="utf-8")
    out = tmp_path / "brain.jsonl"
    res = bd.build_dataset(trajectories=[tj], insights=mem, out=out)
    assert res["records"] == 2
    lines = out.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2 and all(json.loads(l) for l in lines)
    # dedupe identical duplicate trajectory
    tj.write_text(tj.read_text(encoding="utf-8") + json.dumps(rec) + "\n", encoding="utf-8")
    res2 = bd.build_dataset(trajectories=[tj], insights=mem, out=out)
    assert res2["records"] == 2


def test_brainlog_full_activity_stream(tmp_path):
    """Full activity (chat, thinking, tools, search, skill, background, a2a)
    is logged and folded into chronological ChatML turns for training."""
    from openamer_cli.a2a import brainlog as bl
    log = bl.ActivityLog(tmp_path / "activity.jsonl", max_len=800)
    log.append("user", "weather?", role="user", session="S", ts=1)
    log.append("thinking", "user wants forecast", session="S", ts=2)
    log.append("search", "berlin", session="S", ts=3)
    log.append("tool_call", 'web({"q":"berlin"})', session="S", ts=4)
    log.append("skill", "maps", session="S", ts=5)
    log.append("subagent", "world", session="S", ts=6)
    log.append("background", "cron", session="S", ts=7)
    log.append("a2a", "ask to peer answered", session="S", ts=8)
    log.append("assistant", "Cloudy 14C.", session="S", ts=9)
    turns = list(log.to_chatml(include_thinking=True))
    assert len(turns) == 1
    roles = [m["role"] for m in turns[0]]
    assert roles[0] == "system" and roles[1] == "user"
    assert "thinking" in roles and "tool" in roles
    # user content must be the actual user msg (chronological fold)
    assert turns[0][1]["content"] == "weather?"
    # all raw entries sanitized and persisted
    raw = list(log.iter_events())
    assert all(len(e["content"]) <= 800 for e in raw)
    assert {e["kind"] for e in raw} >= {"user", "thinking", "search", "assistant"}

def test_autolog_on_off_capture(tmp_path, monkeypatch):
    """Auto activity capture: disabled = no-op; enabled = events written + flag toggles."""
    monkeypatch.setenv("OPENAMER_HOME", str(tmp_path))
    from openamer_cli.a2a import autolog as al
    assert al.enabled() is True   # ON by default (local capture)
    al.disable()
    assert al.enabled() is False  # opt-out works
    a = al.Autolog()
    a.user("hello"); a.assistant("hi")
    logp = tmp_path / "a2a" / "activity.jsonl"
    assert not logp.exists()      # disabled = no events
    al.enable()
    a2 = al.Autolog()
    a2.user("what is 2+2?", session="S")
    a2.thinking("answer directly", session="S")
    a2.tool("bash", "echo 4", ok=True, session="S")
    a2.assistant("4", session="S")
    assert logp.exists()
    import json
    kinds = [json.loads(l)["kind"] for l in logp.read_text(encoding="utf-8").splitlines()]
    assert "user" in kinds and "thinking" in kinds and "tool_call" in kinds and "assistant" in kinds
    al.disable()
    assert al.enabled() is False

def test_privacy_redact_core():
    """Private data (phone, password, email, card, key) is replaced before storage."""
    from openamer_cli.a2a import privacy as pr
    assert pr.contains_private("call +49 152 1234567") is True
    assert pr.contains_private("password=Hunter2") is True
    out = pr.redact("card 4532015112830366 and pass=Sup3rSec and john@x.com")
    assert "4532015112830366" not in out and "Sup3rSec" not in out and "john@x.com" not in out
    assert "REDACTED" in out
    assert pr.redact("Just a normal math question") == "Just a normal math question"


def test_autolog_redacts_private(tmp_path, monkeypatch):
    """No private data ever persisted by the activity log."""
    monkeypatch.setenv("OPENAMER_HOME", str(tmp_path))
    from openamer_cli.a2a import autolog as al
    al.enable()
    a = al.Autolog()
    a.user("my password=pw123456 and tel +49 152 1234567 and a@b.com", session="S")
    a.assistant("ok", session="S")
    raw = (tmp_path / "a2a" / "activity.jsonl").read_text(encoding="utf-8")
    assert "pw123456" not in raw and "1234567" not in raw and "a@b.com" not in raw
    assert "[REDACTED" in raw


def test_publish_curated_redacts_private(tmp_path):
    """brain publish shares only privacy-scrubbed curated insights."""
    from openamer_cli.a2a import braindata as bd
    mem = tmp_path / "MEMORY.md"
    mem.write_text("#mesh:security: call +49 152 1234567 - urgent\n"
                   "#mesh:devops: cache layers - speeds CI\n", encoding="utf-8")
    out = tmp_path / "shared"
    n = bd.publish_curated(insights=mem, out_dir=out)
    assert n >= 2
    blob = "".join(f.read_text(encoding="utf-8") for f in out.glob("*.jsonl"))
    assert "+49 152 1234567" not in blob
    assert "cache layers" in blob

def test_a2a_ask_many_swarm(tmp_path):
    """Question fan-out to several trusted peers -> bundled collective answers."""
    import threading as _th
    from openamer_cli.a2a import transport as tr
    idQ = core.IdentityStore(tmp_path / "q"); Q = idQ.ensure_identity()
    trQ = trust.TrustStore(tmp_path / "q")
    servers = []
    peers = []
    for i in range(2):
        hs = tmp_path / f"s{i}"
        idP = core.IdentityStore(hs); ident = idP.ensure_identity()
        trP = trust.TrustStore(hs)
        def on_task(env, pd=None):
            return {"answer": "ok:" + str((env.payload or {}).get("question"))}
        srv = transport.A2ANodeServer(host="127.0.0.1", port=0, trust=trP,
                                      identity=idP, on_task=on_task)
        _th.Thread(target=srv.serve_forever, daemon=True).start()
        servers.append(srv)
        trQ.add_peer(ident.fingerprint, ident.public_key, name=f"p{i}")
        trP.add_peer(Q.fingerprint, Q.public_key, name="Q"); trP.grant(Q.fingerprint, "task.ask")
    urls = [f"http://127.0.0.1:{s.port}" for s in servers]
    res = transport.ask_many(idQ, trQ, urls, "meaning?", kind="ask")
    for s in servers: s.shutdown()
    assert res["ok"] is True and res["answered"] == 2
    assert len(res["answers"]) == 2

def test_selflearn_runtime_auto(tmp_path, monkeypatch):
    """Runtime hook: tool-calling turns auto-learn; light/disabled turns skip."""
    monkeypatch.setenv("OPENAMER_HOME", str(tmp_path))
    from openamer_cli.a2a import selflearn_runtime as sr
    from openamer_cli.a2a import autolog as al
    al.enable()
    turn = {"messages": [
        {"role": "user", "content": "how to fix DB lock?"},
        {"role": "tool", "content": "sqlite.execute", "name": "terminal"},
        {"role": "assistant", "content": "close connections in finally"},
    ]}
    res = sr.maybe_learn(turn)
    assert res.get("ok") and res.get("learned")
    mem = tmp_path / "MEMORY-official-mesh.md"
    assert mem.exists() and "finally" in mem.read_text(encoding="utf-8")
    # simple turn -> skip
    assert sr.maybe_learn({"messages": [{"role": "user", "content": "hi"}]}) == {}
    # disabled -> skip
    al.disable()
    assert sr.maybe_learn(turn) == {}
