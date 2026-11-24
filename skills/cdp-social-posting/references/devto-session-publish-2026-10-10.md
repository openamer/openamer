# Dev.to session-based publish — proven 2026-10-09 / 10-10

**Dev.to does NOT need an API key.** The `.env` has no `DEVTO_API_KEY` (and may never have one),
but the saved browser session publishes fine. Do not log `skip_no_credential` for Dev.to on the
basis of the missing key — that was a 6-run false negative; the session is the credential.

## Port: use :9222, not :9333

The `cdp-social-posting` helper `scripts/cdp.py` is hard-wired to `BASE = "http://127.0.0.1:9333"`
(the Electron OpenAmer Browser). **The live Chrome that actually holds the platform sessions
(`openamer-browser/sessions.json`) runs on `:9222`.** Driving the wrong port returns "no page
target" and looks like a dead session. Check both, then pick the one whose `/json/list` shows the
`dev.to` tab:

```bash
curl -s --max-time 5 http://127.0.0.1:9222/json/version   # must NOT contain HeadlessChrome
curl -s --max-time 5 http://127.0.0.1:9222/json/list | grep -o 'https://dev.to[^"]*'
```

## Recipe (own tab, same-origin, ~20 s)

1. **Dedupe first** — never re-publish an existing piece:
   `GET /api/articles/me/published?per_page=30` → `[{id,title,published_at}]`.
   A *new* article on a *new* angle is not a repeat of a completed platform; the identity text
   already on Dev.to (compare `title`) is.
2. Open an own tab (never `tabs[0]` — parallel crons hijack it):
   from the existing `dev.to` target call `window.open('https://dev.to/new','_blank')`, wait ~6 s,
   then re-list `/json/list` and match the tab whose URL contains `dev.to/new`.
3. Verify login live: `GET /api/users/me` (same-origin) → `{username:"openamer", id:4173871}`.
4. Fresh CSRF: `document.querySelector('meta[name=csrf-token]').content` (len ≈ 86).
5. Publish:
   ```js
   fetch('/articles',{method:'POST',credentials:'same-origin',
     headers:{'Content-Type':'application/json','X-CSRF-Token':<csrf>,
              'Accept':'application/vnd.forem.api-v1+json'},
     body: JSON.stringify({article:{title, body_markdown, published:true,
                                    tags:['ai','agents','opensource','python']}})})
   ```
   `POST` → `HTTP 200 {"id":<n>,"current_state_path":"/openamer/<slug>-<hash>"}`.

## Public proof (the only acceptable evidence)

Anonymous `curl` with a browser UA, **no cookies**:

```bash
curl -s -o /tmp/art.html -w "HTTP %{http_code} bytes %{size_download}\n" \
  -A "Mozilla/5.0 (Windows NT 10.0; Win64; x64) ... Chrome/154.0.0.0 Safari/537.36" \
  "https://dev.to/openamer/<slug>"
grep -o "<title>[^<]*</title>" /tmp/art.html   # title must match
grep -c "1,312" /tmp/art.html                  # the exact live ledger number quoted in the post
```

Write the proof file **into the home dir** (`reports/_art.html`), not `/tmp` — MSYS `/tmp`
maps to a path the follow-up `grep` cannot see (measured: `curl -o /tmp/x` then
`grep /tmp/x` → "No such file or directory" while the HTTP 200/bytes line did print).

## Tags

Dev.to tags are lowercase, alphanumeric, max 4. `['ai','agents','opensource','python']` accepted.

## Articles published via this path

| id | title | published |
|---|---|---|
| 4824648 | OpenAmer ASI Core: 5 native tools, a 10-subsystem heartbeat, and an A2A Global Mesh | 2026-10-09T17:03Z |
| 4825557 | How we made an AI agent measure itself: the outcome ledger | 2026-10-09T22:02Z |
| 4826873 | What it costs to run a self-verifying AI agent on a CPU-only laptop | 2026-10-10T06:0xZ |
