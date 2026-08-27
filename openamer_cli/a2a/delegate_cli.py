"""openamer a2a delegate — delegate a task to the remote GitHub Actions worker.

This is the CLI surface for the real-internet A2A workflow (Node A = this
machine, worker = a github.com runner). It is intentionally a thin, separate
module so the core a2a subcommand file stays clean.

Tasks: ping | echo | time | sum | ask  (whitelisted on the remote worker).
The task is signed with this node's Ed25519 identity, uploaded to the shared
relay (directory/a2a/relay/) via git, the GitHub Actions worker is dispatched,
and openamer polls main for the worker's FRESH signed reply, verifying it.

Usage:
    openamer a2a delegate sum --msg "(a/b ignored for sum in CLI demo use ask)"
    openamer a2a delegate ask --msg "explain A2A briefly"
    openamer a2a delegate ping --msg hi
    (flags: --model, --wait, --repo <dir>, --gh-repo owner/repo)
"""
from __future__ import annotations

import json
import os
import subprocess
import time
import urllib.request
import urllib.error
from pathlib import Path

from openamer_cli.a2a import relay as rl
from openamer_cli.a2a.core import Envelope, IdentityStore

DEFAULT_GH_REPO = "openamer/openamer"
DEFAULT_LABEL = "nodeworker"

_cred_cache: str = ""


def _cred_token() -> str:
    global _cred_cache
    if _cred_cache:
        return _cred_cache
    line = Path.home() / ".git-credentials"
    try:
        t = line.read_text().strip() if line.exists() else ""
        if ":" in t:
            _cred_cache = t.rsplit(":", 1)[1].rsplit("@", 1)[0]
    except Exception:
        _cred_cache = ""
    return _cred_cache


def _upload_via_api(gh_repo: str, token: str, path: str, content: str) -> str:
    """Upload a file via the GitHub Contents API (no git staging race)."""
    import base64
    b64 = base64.b64encode(content.encode("utf-8")).decode("ascii")
    req = urllib.request.Request(
        f"https://api.github.com/repos/{gh_repo}/contents/{path}",
        data=json.dumps({"message": f"a2a delegate: {path.split('/')[-1]}",
                         "content": b64, "branch": "main"}).encode(),
        method="PUT",
        headers={"Authorization": f"Bearer {token}",
                 "Accept": "application/vnd.github+json",
                 "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=40) as resp:
            d = json.loads(resp.read().decode("utf-8", "replace"))
        return d.get("content", {}).get("sha", "")
    except urllib.error.HTTPError as e:
        # 422 = file exists; retry once with a fresh nonce name handled by caller
        body = e.read().decode("utf-8", "replace")[:200] if hasattr(e, "read") else str(e)
        raise RuntimeError(f"upload {e.code}: {body}")


def _git(cwd: Path, *args: str, check=True, timeout=200):
    env = dict(os.environ)
    env["GIT_TERMINAL_PROMPT"] = "0"
    r = subprocess.run(["git", "-C", str(cwd)] + list(args), env=env,
                       capture_output=True, text=True, timeout=timeout)
    if check and r.returncode != 0:
        raise RuntimeError("git " + " ".join(args) + "\n" + r.stderr[-400:])
    return r


def _dispatch(gh_repo: str, token: str) -> None:
    body = json.dumps({"event_type": "a2a-task"}).encode()
    req = urllib.request.Request(
        f"https://api.github.com/repos/{gh_repo}/dispatches", data=body,
        method="POST",
        headers={"Authorization": f"Bearer {token}",
                 "Accept": "application/vnd.github+json",
                 "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=40):
        pass


def _latest_reply(inbox: Path, fingerprint: str, after_ts: int = 0):
    best = None
    for p in inbox.glob("*.json"):
        try:
            n = json.loads(p.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            continue
        k = (n.get("envelope") or {}).get("kind", "")
        if n.get("recipient", "").startswith(fingerprint) and k.endswith("result"):
            ts = (n.get("envelope") or {}).get("ts", 0)
            if ts > after_ts and (best is None or ts > best[0]):
                best = (ts, n)
    return best[1] if best else None


def delegate_cmd(task, args) -> int:
    """Run the delegation; ``args`` carries the parsed CLI options."""
    if task not in ("ping", "echo", "time", "sum", "ask"):
        print("Usage: openamer a2a delegate <ping|echo|time|sum|ask> [--msg text] "
              "[--model m] [--wait s] [--repo dir] [--gh-repo owner/repo]")
        return 2

    repo_dir = Path(args.get("repo") or Path.cwd())
    gh_repo = args.get("gh_repo") or DEFAULT_GH_REPO
    client_ts = int(time.time())

    token = _cred_token()
    if not token:
        print("Error: no GitHub token in ~/.git-credentials — cannot upload.")
        return 1

    # (1) build + upload the signed task note via the GitHub Contents API
    identity = IdentityStore()
    me = identity.ensure_identity()
    env = Envelope.create(
        private_key=identity.private_key(), sender=f"{me.fingerprint}@openamer",
        recipient=DEFAULT_LABEL, kind="task.ask",
        payload={"task": task,
                 "msg": args.get("msg", ""),
                 "text": args.get("text", ""),
                 "model": args.get("model", ""),
                 "client_ts": client_ts})
    note = rl.relay_note(identity_store=identity, envelope=env)
    rel = rl.RELAY_PREFIX.replace("\\", "/")
    fname = rl.sort_relay_filename(DEFAULT_LABEL)
    _upload_via_api(gh_repo, token, f"{rel}/{fname}", json.dumps(note, ensure_ascii=False))
    print(f"[a2a] queued {task} to remote worker (sender {me.fingerprint[:8]})")

    # (2) dispatch the worker
    try:
        _dispatch(gh_repo, token)
        print("[a2a] dispatched a2a-worker workflow")
    except Exception as e:
        print("[a2a] WARN dispatch:", e)

    # (3) poll for a fresh signed reply addressed to this node (read via git fetch)
    push_target = f"https://x-access-token:{token}@github.com/{gh_repo}.git"
    deadline = time.time() + int(args.get("wait", 300))
    while time.time() < deadline:
        time.sleep(12)
        _git(repo_dir, "fetch", push_target, "main", check=False)
        _git(repo_dir, "checkout", "-q", "FETCH_HEAD", "--", rel, check=False)
        mine = _latest_reply(repo_dir / rl.RELAY_PREFIX, me.fingerprint, after_ts=client_ts)
        if mine:
            v = rl.verify_note(mine)
            if v["ok"]:
                out = v["env"].payload or {}
                print("\n=== A2A result (signed+verified, from remote worker) ===")
                print("task :", out.get("task"))
                for kls in ("sum", "pong", "text", "utc", "runner", "ok", "from",
                            "model", "answer", "error"):
                    if kls in out:
                        print(f"  {kls}: {out[kls]}")
                print("worker pubkey:", mine["sender_pubkey"][:12])
                return 0
    print("timeout: no fresh signed reply within wait window")
    return 1