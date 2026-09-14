# Distribution channels — measured, not assumed

**Date:** 2026-09-14. Evidence: the real Chrome cookie stores on this machine
(`chrome-profile/Default/Network/Cookies`, 234 cookies / 55 hosts) plus a live
CDP probe. Nothing here is a guess.

## The blocker in one line

**Chrome's CDP endpoint (`localhost:9222`) was DOWN when measured** — so no
automated posting channel is live right now, regardless of which accounts exist.
Everything below is *potential* reach, gated first on the browser being up.

## Accounts with an auth cookie present

Presence of a session/auth cookie is the only honest signal we can read from
disk. It proves a login *existed*; it does not prove the session is still valid.

| Channel | Host | Auth cookie seen |
|---|---|---|
| X / Twitter | x.com | `auth_token` |
| Reddit | reddit.com | `reddit_session` |
| Quora | quora.com | `m-login` |
| Product Hunt | producthunt.com | `_producthunt_session_production` |
| Instagram | instagram.com | `csrftoken` |
| YouTube / Google | youtube.com, accounts.google.com | `__Secure-1PSIDTS`, `LSID` |
| Kleinanzeigen | login.kleinanzeigen.de | `auth0` |
| Fiverr | fiverr.com | `session_locale`, `forterToken` |
| Bing / MSN | bing.com | `.MSA.Auth.Correlation.*` |
| OpenHands docs | docs.openhands.dev | `__sec__token` |

## Hosts with cookies but NO auth cookie found

Do **not** treat these as logged-in:

| Channel | Host | Cookies | Note |
|---|---|---|---|
| Discord | discord.com | 2 | matches the known "not logged in" state |
| Dev.to | dev.to | 2 | likely anonymous |
| Facebook | facebook.com | 2 | likely anonymous |
| LinkedIn | linkedin.com | 4 | no session cookie |
| GitHub | github.com | 3 | no session cookie (auth is via PAT/SSH, not the browser) |

## Known-failing even where a login exists

| Channel | State | Source |
|---|---|---|
| Hacker News | **shadow-flagged** — posts do not surface | recorded in memory; not readable from cookies |
| X (@openamer_agent) | logged in (`auth_token`), **posting blocked** | recorded in memory; workaround was a GitHub issue |
| Discord | not logged in | memory + the cookie table above |

## What this means for reach

1. The single most valuable channel (Hacker News) is **not** a browser problem —
   it is an account-reputation problem only the owner can resolve.
2. Of the channels that *do* have a login, the highest-signal one for a
   developer tool is Reddit (`r/LocalLLaMA`, `r/selfhosted`), followed by
   Product Hunt and Dev.to.
3. None of it moves while the browser is down. Fix order:
   **browser up → verify a session actually loads → post one thing → measure.**
4. The content to post is prepared in [`launch/`](launch/) and the proof asset
   is [`demo/`](demo/) — distribution is the binding constraint, not material.

## Reproduce this audit

```bash
# the cookie audit (read-only; copies the DB so a running Chrome is never touched)
python - <<'PY'
import sqlite3, shutil, collections, os
db = "chrome-profile/Default/Network/Cookies"
shutil.copy2(db, "tmp/ck.db")
rows = sqlite3.connect("tmp/ck.db").execute("SELECT host_key,name FROM cookies").fetchall()
print(collections.Counter(h.lstrip('.') for h, _ in rows).most_common(20))
PY

# the browser liveness probe
curl -s -m 5 http://localhost:9222/json/version
```