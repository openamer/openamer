#!/usr/bin/env python3
"""Sha-guarded GitHub-contents-API cross-link appender (owned-surface self-cross-linking).

Appends one or more `- [Title](URL)` bullets after a unique anchor line in a file on a repo,
using the contents API (never a clone). Safe to re-run: it refuses to write if the anchor is
not unique, if any new URL is already present, or if the file has CRLF (a PUT would flip line
endings and rewrite the whole file). A sibling cron pushing between the GET and the PUT yields
HTTP 409 instead of a silent clobber — that is the sha guard working.

WHY: linking your OWN already-published posts from your OWN repo/Pages surfaces is honest
spread and is NOT a platform post, so the mass-post rule does not apply. This is the one action
that stays available when every social channel is gated.

USAGE (from the OpenAmer home dir; needs `gh auth token` or --token):

    python scripts/repo_crosslink.py \
      --repo openamer/openamer --path README.md \
      --anchor '- [Run a self-verifying desktop AI agent on your own machine: a 10-minute quickstart](https://dev.to/openamer/run-a-self-verifying-desktop-ai-agent-on-your-own-machine-a-10-minute-quickstart-358p)' \
      --append "A2A without a server::https://dev.to/openamer/a2a-without-a-server-...-n62" \
      --append "We read all 1,186 failed agent runs::https://dev.to/openamer/we-read-all-1186-...-j3b"

--anchor MUST be the exact text of an existing line that occurs exactly once (e.g. the last
bullet of the section). The new bullets are inserted immediately after it.

Verify after the run (the script prints it): the file's byte length grew by roughly the length
of the appended text, every new URL is present, and the marker count (default the
`https://dev.to/openamer/` prefix) equals your live article count. Then anonymous-curl any
public URL (browser UA, no cookies) -> expect HTTP 200 + matching <title>.
"""
import argparse
import base64
import json
import subprocess
import sys
import urllib.error
import urllib.request


def gh_token():
    out = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True)
    return out.stdout.strip()


def api(url, method="GET", data=None, token=None):
    req = urllib.request.Request(
        url, method=method, data=json.dumps(data).encode() if data else None
    )
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", "openamer-repo-crosslink")
    if token:
        req.add_header("Authorization", "Bearer " + token)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True, help="owner/name")
    ap.add_argument("--path", required=True, help="e.g. README.md or docs/index.html")
    ap.add_argument("--anchor", required=True, help="exact existing line; must be unique")
    ap.add_argument("--append", action="append", default=[],
                    help="'Title::URL' (repeatable). Also accepts 'Title|URL'.")
    ap.add_argument("--message", default=None)
    ap.add_argument("--token", default=None)
    ap.add_argument("--count-prefix", default="https://dev.to/openamer/",
                    help="substring whose occurrences are reported as a sanity count")
    ap.add_argument("--branch", default="main")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    token = a.token or gh_token()
    if not token:
        print(json.dumps({"error": "no gh token (gh auth token empty and --token unset)"}))
        return 2

    pairs = []
    for item in a.append:
        sep = "::" if "::" in item else "|"
        title, _, url = item.partition(sep)
        pairs.append((title.strip(), url.strip()))
    if not pairs:
        print(json.dumps({"error": "no --append given"}))
        return 2

    cur = api(f"https://api.github.com/repos/{a.repo}/contents/{a.path}?ref={a.branch}", token=token)
    txt = base64.b64decode(cur["content"]).decode("utf-8")
    sha = cur["sha"]
    print(json.dumps({"before_bytes": len(txt.encode()), "sha": sha}))

    # --- guards ---
    if txt.count(a.anchor) != 1:
        print(json.dumps({"error": "anchor not unique", "count": txt.count(a.anchor)}))
        return 3
    dupes = [u for _, u in pairs if u in txt]
    if dupes:
        print(json.dumps({"error": "URLs already present", "urls": dupes}))
        return 3
    if txt.count("\r\n") != 0:
        print(json.dumps({"error": "file has CRLF; refusing to flip line endings on PUT"}))
        return 3

    add = "".join("\n- [%s](%s)" % (t, u) for t, u in pairs)
    new = txt.replace(a.anchor, a.anchor + add, 1)

    if a.dry_run:
        print(json.dumps({"dry_run": True, "would_add_bytes": len(new.encode()) - len(txt.encode())}))
        return 0

    body = {
        "message": a.message or "docs: link the newest own posts",
        "content": base64.b64encode(new.encode("utf-8")).decode(),
        "sha": sha,
        "branch": a.branch,
    }
    try:
        res = api(f"https://api.github.com/repos/{a.repo}/contents/{a.path}",
                  method="PUT", data=body, token=token)
    except urllib.error.HTTPError as e:  # noqa: F821
        print(json.dumps({"error": "PUT failed (sibling push => 409?)", "status": e.code}))
        return 4
    print(json.dumps({"commit": res.get("commit", {}).get("sha"),
                      "new_blob": res.get("content", {}).get("sha")}))

    ver = api(f"https://api.github.com/repos/{a.repo}/contents/{a.path}?ref={a.branch}", token=token)
    vtxt = base64.b64decode(ver["content"]).decode("utf-8")
    print(json.dumps({
        "after_bytes": len(vtxt.encode()),
        "sha_after": ver["sha"],
        "new_links_present": len([u for _, u in pairs if u in vtxt]),
        "marker_count": vtxt.count(a.count_prefix),
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
