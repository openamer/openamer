#!/usr/bin/env python3
"""Pull Opire's live bounty board from its public API (no auth needed).

Usage:
    python opire_live_bounties.py             # list all open rewards
    python opire_live_bounties.py --verify    # + cross-check each via gh (needs gh auth)

Why: app.opire.dev is JS-only behind a login wall for *claiming*, but its read
API is open. The listing is STALE -- closed issues and deleted repos stay listed
-- so always cross-check a candidate before authoring. See
references/opire-live-bounty-pull.md for the full trap write-up.
"""
import argparse
import json
import subprocess
import urllib.request

API = "https://api.opire.dev/rewards"


def fetch():
    req = urllib.request.Request(API, headers={
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    })
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def gh_issue_state(url):
    """Return the live GitHub issue state for an Opire reward URL, or a marker."""
    parts = url.rstrip("/").split("/")
    try:
        number = parts[-1]
        repo = "/".join(parts[-4:-2])  # owner/repo
        out = subprocess.run(
            ["gh", "issue", "view", number, "--repo", repo, "--json", "state"],
            capture_output=True, text=True, timeout=30,
        )
        if out.returncode != 0:
            return "REPO/ISSUE MISSING"
        return json.loads(out.stdout).get("state", "?")
    except Exception as e:  # noqa: BLE001
        return "ERR:%s" % str(e)[:40]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify", action="store_true",
                    help="cross-check each issue's live state via gh (needs gh auth)")
    args = ap.parse_args()

    data = fetch()
    print("Open rewards listed: %d" % len(data))
    for r in data:
        price = (r.get("pendingPrice") or {}).get("value", 0) / 100.0
        state = gh_issue_state(r["url"]) if args.verify else ""
        line = "%7.2f USD | %-20s | %-48s | claimers=%d tryers=%d" % (
            price, r["project"]["name"][:20], r["title"][:48],
            len(r.get("claimerUsers", [])), len(r.get("tryingUsers", [])),
        )
        if state:
            line += " | issue=%s" % state
        print(line + " | " + r["url"])


if __name__ == "__main__":
    main()
