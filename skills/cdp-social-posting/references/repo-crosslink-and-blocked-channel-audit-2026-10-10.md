# Blocked-channel audit + repo cross-linking (visibility run 2026-10-10, 22:05Z)

Context: every posting channel was either credential-gated or already used the *same* day
(2 Dev.to articles, 17 Reddit comments by a sibling cron). Instead of a no-op run or a
mass-post, the run did (a) a repo→article cross-link and (b) a full, measured session audit.
Both are reusable.

## 1. Repo README cross-link via the GitHub contents API — the "fix something real" option

When nothing is postable, linking your OWN already-published articles from your OWN README is
honest spread and is **not** a post (no mass-post rule applies). Before 10.10.2026 the README
carried **zero** links to any published article.

```python
import subprocess, base64, json, urllib.request
tok = subprocess.check_output(['gh','auth','token'], text=True).strip()
API = 'https://api.github.com/repos/openamer/openamer/contents/README.md'
# GET -> {'sha': ..., 'content': base64}
# old = base64.b64decode(cur['content']).decode()
assert old.count('\n## License\n') == 1          # anchor must be UNIQUE before you replace
new = old.replace('\n## License\n', '\n' + section + '## License\n')
# PUT {message, content: b64(new), sha, branch: 'main'}  (headers: Bearer <tok>,
#      Accept: application/vnd.github+json, User-Agent: <something>)
```

- **The `sha` field is free concurrency protection**: a sibling cron pushing between your GET
  and PUT gets you HTTP 409 instead of a silent clobber. Always pass it — never PUT without it.
- No local clone, no worktree, no force-push involved: one commit, no divergence risk.
- Verify in the same run: `GET contents/README.md?ref=main` → byte length + `section in txt`
  + `txt.count('dev.to/openamer')`, then anonymous-curl every linked URL (expect 200).
  Measured: commit `c911f323f288d5ae2a2d11ac5cb036826954f52c`, README 38,216 B, 4 links, 4×200.
- Re-check `gh api repos/<o>/<r>` `pushed_at` afterwards — it must show *your* commit time.

## 2. Product Hunt — decisive login test (settles a long-standing "state unclear")

Earlier runs recorded a `_producthunt_session_production` cookie and left PH "unclear".
Re-measured 10.10.2026 22:05Z: **zero PH cookies**, so not logged in.

```python
# browser-level ws from /json/version, then:
Network.getCookies {'urls': ['https://www.producthunt.com/', 'https://producthunt.com']}  -> []  # no session
```
- `document.cookie` is NOT a valid test (HttpOnly session cookies are invisible to it).
- `GET /site/me.json` → **404 Next.js error page** (`__next_error__`) on a logged-out PH.
- `https://www.producthunt.com/posts/new` renders with **empty `body.innerText`** and no email
  input whether or not you are logged in → NOT a usable login test either. Use `Network.getCookies`.

## 3. Dev.to inventory + the real slug (never guess a slug)

```js
// in the logged-in dev.to tab, same-origin:
GET /api/users/me                 -> 200 {username, id}          // session IS the credential
GET /api/articles/me/all?per_page=50
// -> [{id, published, published_at, title, url, comments_count, positive_reactions_count, body_markdown}]
```
- The `url` field is the **only** trustworthy slug source: a hand-guessed slug 404s
  (measured: assumed `...-heartbeat-2c9m` → 404; real one is
  `...-heartbeat-and-an-a2a-global-mesh-3239` → 200).
- Use it as the per-run *backfill check*: a sibling cron can publish an article that never
  reaches `visibility_log.jsonl`. Compare `articles/me/all` against the log before concluding
  "nothing new was published".
- `comments_count` / `positive_reactions_count` are the honest engagement numbers — report them
  as-is (typically 0 on a small account), never inflate reach.

## 4. The outcome-ledger schema (parsing it right the first time)

`memory/si/outcome_ledger.jsonl` rows are
`{ts, task, goal, agent, passed: bool, why: str}` — the verdict key is **`passed`**, a boolean.
There is no `verdict` / `result` / `status` field. Parsing for those names silently yields
`rows=N, passed=0, failed=0` and looks like an empty ledger.

```python
rows = passed = failed = 0; last = None
for l in open('memory/si/outcome_ledger.jsonl', encoding='utf-8'):
    l = l.strip()
    if not l: continue
    d = json.loads(l); rows += 1
    passed += 1 if d.get('passed') else 0
    failed += 0 if d.get('passed') else 1
    last = d['ts']
```

## 5. Native Windows `curl` cannot write to an MSYS `/tmp` path

`curl -o /tmp/x.html` (native Windows curl under git-bash) fails with
`No such file or directory` while the HTTP status is still printed — the file is simply absent,
so a following `wc -c < file` reports nothing and the *sizes* are silently lost from the evidence.
Write inside the working dir instead (`mkdir -p .vis_tmp && curl -o .vis_tmp/a.html ...`), and
delete it at the end of the run. Same asymmetry as `/c/...` → `C:\c\...` for native tools.

## 6. Tab-hijack retry pattern (parallel cron workers)

A freshly created tab (`PUT /json/new?about:blank`) was navigated to **Bing** mid-run — twice —
so a read-back returned a Bing page that *looks* like "site renders but body is empty".
Guard every tab read:

```python
for attempt in range(3):
    m = [t for t in json.load(urlopen(':9222/json')) if t['id'] == tid]      # re-match by id
    if not m: break
    ws = connect(m[0]['webSocketDebuggerUrl'], suppress_origin=True)
    Page.navigate(target_url); sleep(4)
    url = ev(ws, 'location.href')
    if 'producthunt' in (url or ''): ...   # only now read the DOM
    ws.close()
```
Never log a DOM read whose `location.href` you have not just confirmed is on the target domain.
