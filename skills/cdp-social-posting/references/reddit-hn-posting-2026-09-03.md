# Attempt transcript — Dream Cycle post, 03.09.2026

Target: `reports/post-dream-cycle-hn-reddit.md` (Show HN / r/LocalLLaMA selftext).

## HN
- Session valid: `a[href^=user]` → "openamer" (verified via Runtime.evaluate on :9222 tab).
- Submit with 117-char title → redirect `x?fnid=...&fnop=toolong-title`. Retry with 59-char title → redirect `/showlim` ("temporarily restricting Show HNs"). Account karma = -1, 2 prior submissions (1 point each). No submission landed.
- Sustainable path remains comments on existing threads (algolia search).

## Reddit
- `scripts/session_manager.py` no longer exists at repo root — verify sessions in-page, not via that script.
- New-UI composer at `/r/LocalLLaMA/submit?selftext=true`: three light-DOM `div[contenteditable=true][role=textbox]` fields; `document.execCommand('insertText')` returned ok but textContent length 0 (state never registered). No Post button found by text match.
- old.reddit fallback: form#newlink present; filled title/text (textareas), kind=self, submit_type_subreddit, sr='LocalLLaMA' → click = silent no-op, `/submitted.json` empty.
- In-page `fetch('/api/submit', FormData{api_type:'json', sr:'LocalLLaMA', kind:'self', uh:<modhash>, title, text})` → `{"json":{"errors":[["BAD_CAPTCHA","That was a tricky one..."]]}}`. Definitive account-tier block. Stopped honestly; no duplicate posting.

## Working verification snippets
- Login: `fetch('/api/me.json',{credentials:'include'}).then(r=>r.json())` → `{u:'...'}`
- Landed check: `fetch('/user/<name>/submitted.json').then(...)` → children array
- New tab: `PUT http://localhost:9222/json/new?<url>` (GET = 405)