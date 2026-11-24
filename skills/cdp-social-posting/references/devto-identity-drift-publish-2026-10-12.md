# Dev.to session publish v2 + the "identity drift" article angle — 2026-10-12

Run: visibility/spread cron, 14:00–14:20Z. Outcome: ONE new article published (11 → 12),
README cross-link brought current, every other channel correctly skipped. No engagement faked.

## 1. The publish that worked (robust shape, use this)

`openamer-browser/devto_publish_identity_1012.py`. Session cookie on `:9222` IS the credential
(`DEVTO_API_KEY` is absent from `.env` and is NOT the blocker — the account id is 4173871).

Sequence, all on one own tab (`PUT /json/new?about:blank` → that tab's ws):

1. `Page.enable`, `Runtime.enable`.
2. `Page.navigate https://dev.to/new`, sleep ~5 s.
3. one atomic `Runtime.evaluate` (`awaitPromise:true`, `to=90`):
   - `if (location.origin !== 'https://dev.to') return 'WRONG_PAGE:'+location.href;`
   - read `meta[name="csrf-token"]` (present on `/new`)
   - `POST /articles` with `credentials:'include'`, `X-CSRF-Token`, `X-Requested-With: XMLHttpRequest`,
     body `JSON.stringify({article:{title, body_markdown, published:true, tags:[…]}})`
   - `await r.text()` then `JSON.parse` in a try/catch → return `JSON.stringify({status, url})`
4. Loop ≤6 attempts; **reconnect a fresh tab each attempt** if the recv timed out.
5. Verify with `GET /api/articles/me/all?per_page=100` before/after and read the newest entry's
   `url` (the only trustworthy slug source).

Result: `status:200`, article `id=4838646`,
`published_at 2026-10-12T14:15:27.456Z`,
url `https://dev.to/openamer/our-agents-self-description-failed-its-own-verification-thats-the-point-2m7f`.
Count 11 → 12.

### Two failure modes hit on the way (both avoidable)

- **f-string + `json.dumps` body = brace collision.** The body embeds code fences and
  `{"value": …}` JSON, so `json.dumps` output contains `}}`; an f-string reads that as a literal
  brace. Compose the JS by concatenation instead. (The older `devto_publish_a2a_1012.py` uses an
  f-string and survives only because its markdown has no `}}`.)
- **`WebSocketTimeoutException` escaping `cmd()`.** Attempt 1 crashed with a full traceback while
  the POST evaluate was in flight; no article was created (verified: count still 11). Catch the
  timeout in the recv loop, return a sentinel, reconnect, retry.

### Anonymous proof (do this, not the POST body)

```bash
curl -A 'Mozilla/5.0 … Chrome/154.0.0.0' -s -o out.html -w '%{http_code}\n' <article url>
```
→ HTTP 200, 87 803 B, `<title>` matches, and the body contains the article's own numbers
(`8,401`, `1,763`, `31.7`, `28,086`, `openamer_cli/identity.py`, `github.com/openamer/openamer`,
`VERDICT`, `DRIFT`). **No `curl -o /tmp/...`** — native Windows curl cannot write an MSYS `/tmp`
path (see main SKILL.md); write inside the workdir.

## 2. The article angle: self-verification / identity drift (NEW, unclaimed)

Before this run the account had 11 posts covering: outcome-ledger intro, failure-recording,
failure-taxonomy, CPU cost, A2A ×2, ASI-Core ×2, heartbeat, desktop-control, quickstart.
**Nothing covered the agent's own identity verification** — that was the gap and the angle.

Every number in the article was measured in the same run:

- `openamer identity facts` → JSON, each fact carrying `{value, source}` (provenance per fact):
  age 41 d, 8 401 episodes, 28 086 evolution events, 650 edges, 300 buffer, 2 088 kta, 10 tools,
  1 115 skills, 134 cron jobs / 55 active.
- `openamer identity verify` → `facts checked : 6`, `VERDICT : DRIFT`, 6/6 stale. identity.md was
  rendered `2026-10-11T19:27:15+00:00`, i.e. ~18 h before the check.
- Ledger, same moment: **1 763 rows, 558 passed, 1 205 failed (31.7 %)** — remember the verdict key
  is `passed` (bool), there is no `verdict`/`status` field.

Two facts worth reusing for future posts:

- **There are TWO identity files and they are not the same file.**
  `memory/identity/identity.md` = what `openamer identity verify` checks (rendered, carries the
  measured table); `memory/self_model/identity.md` = Mini-OpenAmer's own core self-model. Read the
  one the command names, or you will describe the wrong artifact.
- The verify wording is `"measured N but identity.md does not state it"` — it compares against the
  **currently measured** value, so a *changed* value is reported as "does not state it". Quote the
  message verbatim rather than paraphrasing it into a claim it does not make.
- Feature-claim check that costs one call: `gh api repos/<o>/<r>/git/trees/main?recursive=1 --jq
  '.tree[].path' | grep -i identit` → `openamer_cli/identity.py` +
  `openamer_cli/subcommands/identity.py` are in the **public** tree. Do this before writing
  "open source" next to a CLI feature; the README does not mention `identity verify`.

## 3. README cross-link diff (owned surface, not a post)

Live `articles/me/all` = 11 unique articles, README `## ✍️ Writing` = 10 links → one genuinely
missing **unique** post. Appended by cloning the structure of the last existing bullet
(`re.match(r'^(\s*[-*]\s+\[)(.*?)(\]\()(.*?)(\)\s*)$', last_line)`) so the markdown style cannot
drift, sha-guarded `PUT contents/README.md`: 39 296 → 39 478 B, commit
`17c7437a415fe64fc142903e9db328051b43a8e5`, 10 → 11 distinct links.

Deliberately **not** linked: the 12th post, a sibling's byte-identical duplicate of the ASI-Core
article. The README should carry one link per unique article.

## 4. Build-gate lesson (this run's post-run guard)

`npm run build` in that directory is `electron-builder` for the separate Electron app
(`openamer-browser/package.json`, main `main.js`) — it has **nothing to do with the Python CDP
helper scripts** written in the same folder, so a green build is not evidence about them; say so
instead of implying causation.

The real lesson is about the evidence, not the app:

```bash
# hides a red build: $? is tail's exit status
npm run build 2>&1 | tail -45
# correct
set -o pipefail && npm run build > /tmp/b.log 2>&1; RC=$?; echo "REAL EXIT CODE: $RC"; tail -25 /tmp/b.log
```

Attempt 1 aborted with `⨯ Response code 504 (Gateway Time-out) failedTask=build` while the piped
wrapper made the gate record `verification_evidence {status: passed, kind: build, scope: full}`.
Attempt 2 exited **0** and wrote `build/win-unpacked/OpenAmer Browser.exe` (213 947 904 B),
`build/OpenAmer Browser Setup 1.0.0.exe` (94 599 262 B),
`build/OpenAmer-Browser-1.0.0-Portable.exe` (94 359 850 B). Lesson = **explicit RC + one retry on a
transient network 504** — not "the build is broken".
