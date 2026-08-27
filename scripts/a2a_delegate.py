"""a2a_delegate.py — delegate a task from THIS laptop to the remote a2a worker.

All transport is over the real internet via GitHub (the a2a relay); nothing uses
localhost. Flow:
  1. sign a task-note (Ed25519) addressed to the "nodeworker" mailbox
  2. upload it to directory/a2a/relay/ via the GitHub Contents API
  3. trigger the a2a-worker GitHub Action via repository_dispatch
  4. poll git main until the worker's fresh signed reply for OUR mailbox appears
  5. verify signature + freshness, print the result

Usage:
  python a2a_delegate.py ping [--msg hi]
  python a2a_delegate.py echo --text hello
  python a2a_delegate.py time
  python a2a_delegate.py sum --a 20 --b 22
"""
from __future__ import annotations

import argparse, base64, json, subprocess, sys, time, urllib.request
from pathlib import Path

REPO   = Path(r"C:\Users\damir\openamer-repo")
GH     = "openamer/openamer"
IDENT  = Path(r"C:\Users\damir\AppData\Local\openamer-laptop\.a2a-relay-laptop")

sys.path.insert(0, str(REPO))
from openamer_cli.a2a.core import IdentityStore, Envelope          # noqa: E402
from openamer_cli.a2a import relay as R                              # noqa: E402
from openamer_cli.a2a.relay import verify_note                       # noqa: E402

TOKEN = ""
def cred_token():
    global TOKEN
    l = (Path.home()/".git-credentials").read_text().strip() if (Path.home()/".git-credentials").exists() else ""
    if ":" in l: TOKEN = l.rsplit(":",1)[1].rsplit("@",1)[0]

def scrub(s):
    if isinstance(s, bytes): s = s.decode("utf-8","replace")
    return s.replace(TOKEN,"***TOKEN***") if TOKEN else s

def gh_json(method, url, data=None):
    req = urllib.request.Request(url, method=method)
    req.add_header("Authorization", f"Bearer {TOKEN}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("Content-Type", "application/json")
    body = None
    if data is not None:
        body = json.dumps(data).encode()
    with urllib.request.urlopen(req, body, timeout=40) as r:
        raw = r.read()
        return r.status, (json.loads(raw) if raw else {})

def _b64(s):
    return base64.b64encode(s.encode("utf-8")).decode("ascii")

def upload_task(path, text_content):
    st, resp = gh_json("PUT",
        f"https://api.github.com/repos/{GH}/contents/{path}",
        {"message": f"a2a delegate: {path.split('/')[-1]}",
         "content": _b64(text_content), "branch": "main"})
    return resp.get("content", {}).get("sha")

def trigger_worker():
    return gh_json("POST", f"https://api.github.com/repos/{GH}/dispatches",
                   {"event_type": "a2a-task"})[0]

def git_fetch_main():
    env = dict(os.environ); env["GIT_TERMINAL_PROMPT"] = "0"
    url = f"https://x-access-token:{TOKEN}@github.com/{GH}.git"
    subprocess.run(["git","-C",str(REPO),"fetch","-q","origin",f"+refs/heads/master:refs/remotes/origin/master"],
                   env=env, capture_output=True, timeout=90)
    # some setups use main
    subprocess.run(["git","-C",str(REPO),"fetch","-q",url,"main"],
                   env=env, capture_output=True, timeout=90)
    subprocess.run(["git","-C",str(REPO),"checkout","-q","FETCH_HEAD","--",
                    R.RELAY_PREFIX.replace("\\","/")], env=env, capture_output=True, timeout=90)

def latest_reply(li):
    cands = []
    for p in (REPO / R.RELAY_PREFIX).glob("*.json"):
        try:
            n = json.loads(p.read_text(encoding="utf-8", errors="replace"))
            k = (n.get("envelope") or {}).get("kind", "")
        except Exception: continue
        if n.get("recipient","").startswith(li.fingerprint) and k.endswith("result"):
            cands.append(n)
    return max(cands, key=lambda n: (n.get("envelope") or {}).get("ts", 0)) if cands else None

def main():
    import os
    cred_token()
    ap = argparse.ArgumentParser()
    ap.add_argument("task", choices=["ping","echo","time","sum","ask"])
    ap.add_argument("--msg", default="ping")
    ap.add_argument("--text", default="")
    ap.add_argument("--model", default="")
    ap.add_argument("--wait", type=int, default=300)
    a = ap.parse_args()

    store = IdentityStore(IDENT); li = store.ensure_identity()
    env = Envelope.create(private_key=store.private_key(),
                          sender=f"{li.fingerprint}@openamer", recipient="nodeworker",
                          kind="task.ask",
                          payload={"task": a.task, "text": a.text,
                                   "model": a.model, "msg": a.msg,
                                   "client_ts": int(time.time())})
    note = R.relay_note(identity_store=store, envelope=env)
    fname = R.sort_relay_filename("nodeworker")
    path  = f"{R.RELAY_PREFIX}/{fname}"
    sha = upload_task(path, json.dumps(note))
    print(f"[delegate] uploaded task {a.task} ({fname[:24]}) sender={li.fingerprint[:8]} sha={sha[:7] if sha else '?'}")

    st = trigger_worker()
    print(f"[delegate] triggered worker action (HTTP {st})")

    deadline = time.time() + a.wait
    while time.time() < deadline:
        time.sleep(12)
        git_fetch_all()
        mine = latest_reply(li)
        if mine:
            v = verify_note(mine)
            if v["ok"]:
                out = v["env"].payload or {}
                print("\n=== RESULT (signed+verified, from remote a2a worker) ===")
                print("task :", out.get("task"))
                for kls in ("sum","pong","text","utc","runner","ok","from","model","answer"):
                    if kls in out: print(f"  {kls}: {out[kls]}")
                print("worker pubkey:", mine["sender_pubkey"][:12])
                return 0
    print("timeout: no fresh signed reply within wait window"); return 1

def git_fetch_all():
    import os
    env = dict(os.environ); env["GIT_TERMINAL_PROMPT"] = "0"
    url = f"https://x-access-token:{TOKEN}@github.com/{GH}.git"
    for branch in ("main",):
        subprocess.run(["git","-C",str(REPO),"fetch","-q",url,branch], env=env, capture_output=True, timeout=90)
        subprocess.run(["git","-C",str(REPO),"checkout","-q","FETCH_HEAD","--",
                        R.RELAY_PREFIX.replace("\\","/")], env=env, capture_output=True, timeout=90)

if __name__ == "__main__":
    sys.exit(main())