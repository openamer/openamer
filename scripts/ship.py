"""Ship a branch: push, open PR, merge — and refuse to believe any of it blindly.

Built 2026-11-17 after the same mistake three times in one evening:

* `git push` was rejected as non-fast-forward, the branch on the remote stayed
  stale, the PR therefore carried old content, and GitHub still answered
  `merged: True`. Two PRs (#386, #387) "merged" while the code never reached
  main, and a third change (6 backfill chains) silently kept main at 4.
* Every one of those was visible in a place I did not look: the push output said
  `hint: Note about fast-forwards`, and `origin/main:<file>` did not contain the
  marker.

So this helper treats every step as a claim to verify, and refuses to continue:

1. the push must not report a rejection,
2. the PR's file list must contain every expected file,
3. the merge must report success,
4. `origin/main:<file>` must contain the marker — otherwise the whole run fails
   with a non-zero exit and names what is missing.

    python scripts/ship.py --branch feat/x --title "feat: y" --body-file pr.md \
        --expect scripts/a.py --expect scripts/b.py \
        --verify scripts/a.py:DEF_MARKER

Exit code 0 means: the marker is readable from main. Anything else is a failure.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

REJECT_HINTS = (
    "hint: updates were rejected",
    "[rejected]",
    "non-fast-forward",
    "fetch first",
    "failed to push some refs",
)


def push_was_rejected(output: str) -> bool:
    """True when git refused the push, even if it printed a hint instead of an error."""
    low = output.lower()
    return any(hint in low for hint in REJECT_HINTS)


def token() -> str:
    path = os.path.expanduser("~/.git-credentials")
    for line in open(path, encoding="utf-8"):
        if "github.com" in line:
            return line.rsplit(":", 1)[1].rsplit("@", 1)[0]
    raise SystemExit("no github credential found")


class GitHub:
    def __init__(self, slug: str, tok: str):
        self.slug = slug
        self.tok = tok

    def call(self, method: str, path: str, body: dict | None = None):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(
            f"https://api.github.com{path}", data=data, method=method,
            headers={"Authorization": f"Bearer {self.tok}",
                     "Accept": "application/vnd.github+json",
                     "X-GitHub-Api-Version": "2022-11-28",
                     "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.status, json.loads(r.read() or b"{}")
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read() or b"{}")

    def file_on_main(self, path: str) -> tuple[int, str]:
        st, data = self.call("GET", f"/repos/{self.slug}/contents/{path}?ref=main")
        if st != 200 or not data.get("content"):
            return st, ""
        return st, base64.b64decode(data["content"]).decode("utf-8", "replace")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--branch", required=True)
    ap.add_argument("--title", required=True)
    ap.add_argument("--body-file", required=True)
    ap.add_argument("--expect", action="append", default=[],
                    help="file that must appear in the PR file list (repeatable)")
    ap.add_argument("--verify", action="append", default=[],
                    help="path:marker that must be readable from origin/main (repeatable)")
    ap.add_argument("--slug", default="openamer/openamer")
    ap.add_argument("--repo", default=os.path.expanduser("~/openamer-repo"))
    ap.add_argument("--wait", type=int, default=25)
    args = ap.parse_args()

    tok = token()
    gh = GitHub(args.slug, tok)

    push = subprocess.run(
        ["git", "push", f"https://x-access-token:{tok}@github.com/{args.slug}.git",
         f"HEAD:refs/heads/{args.branch}"],
        cwd=args.repo, capture_output=True, text=True)
    output = (push.stderr or "") + (push.stdout or "")
    print("push output:", " | ".join(output.strip().splitlines()[-2:])[:200])
    if push.returncode != 0 or push_was_rejected(output):
        print("ABBRUCH: der Push wurde abgelehnt — der Remote-Branch ist NICHT aktuell.",
              file=sys.stderr)
        print("        Nichts wird gemergt, bis der Push sauber ist.", file=sys.stderr)
        return 2

    body = open(args.body_file, encoding="utf-8").read()
    st, pr = gh.call("POST", f"/repos/{args.slug}/pulls",
                     {"title": args.title, "head": args.branch, "base": "main", "body": body})
    print("create:", st, pr.get("number"), pr.get("html_url"), pr.get("message", ""))
    if st >= 300:
        return 3
    num = pr["number"]

    st, files = gh.call("GET", f"/repos/{args.slug}/pulls/{num}/files?per_page=100")
    names = {f["filename"] for f in (files if isinstance(files, list) else [])}
    print("PR-Dateien:", sorted(names))
    missing = [f for f in args.expect if f not in names]
    if missing:
        print(f"ABBRUCH: PR enthält nicht {missing} — der Branch ist nicht der, den du meinst.",
              file=sys.stderr)
        return 4

    for _ in range(args.wait):
        st, info = gh.call("GET", f"/repos/{args.slug}/pulls/{num}")
        if info.get("mergeable"):
            break
        time.sleep(8)
    st, res = gh.call("PUT", f"/repos/{args.slug}/pulls/{num}/merge",
                      {"merge_method": "squash",
                       "commit_title": f"{args.title} (#{num})"})
    print("merge:", st, res.get("merged"), str(res.get("sha", ""))[:10])
    if not res.get("merged"):
        return 5

    time.sleep(5)
    failed = []
    for spec in args.verify:
        path, _, marker = spec.partition(":")
        st, text = gh.file_on_main(path)
        ok = st == 200 and (not marker or marker in text)
        print(f"main:{path} -> HTTP {st}, marker {marker!r} {'gefunden' if ok else 'FEHLT'}")
        if not ok:
            failed.append(path)
    if failed:
        print(f"ABBRUCH: 'merged' gemeldet, aber main enthält {failed} nicht.", file=sys.stderr)
        return 6

    print(f"OK: #{num} ist auf main nachweisbar.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
