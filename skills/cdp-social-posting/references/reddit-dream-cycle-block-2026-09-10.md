# Reddit Dream Cycle post — blocked, honest stop (10.09.2026, outreach cron)

## Task
Post `reports/post-dream-cycle-hn-reddit.md` (Dream Cycle story) to Reddit r/LocalLLaMA, ONCE.
HN was correctly skipped: post already exists there (flagged Show HN + alive link post, see ref 09.09).

## Verified session state (cron_dream_reddit_check.py)
- CDP :9222 alive, real Chrome UA (no HeadlessChrome) ✓
- Login ACTIVE via in-page `fetch('/api/me.json', {credentials:'include'})` → `u/Realistic_Kitchen_65` (modhash present)
- `/user/<name>/submitted.json` in-page → **0 submissions** (account only comments) → no duplicate risk on Reddit
- Direct urllib fetch of submitted.json → HTTP 403 Blocked (Reddit blocks non-browser fetch from this IP). Dup-checks MUST run in-page.

## Submission attempts (cron_dream_reddit_post2.py + cron_dream_reddit_form_try2.py)
1. In-page `fetch('/api/submit', FormData)` with uh modhash, kind=self, sr=LocalLLaMA, flair_id picked from `/r/LocalLLaMA/api/link_flair_v2.json` (flairs include **"I Built A Thing"** — best fit for project posts) →
   `{"json":{"errors":[["BAD_CAPTCHA","That was a tricky one. Why don't you try that again.","captcha"]]}}`
2. old.reddit `form#newlink` DOM path, correctly filled (title_len=76, body_len=2292, sr=LocalLLaMA), submit clicked →
   **silent noop**: URL unchanged, no `.status.error`, submitted.json still empty.

BAD_CAPTCHA + silent form = documented account-tier block. Honest stop, no retry-loop.

## Gotchas found this run
- `_find_or_create_page()` hijacks whichever tab is newest — a concurrent cron's Bing tab got picked and `/api/me.json` was fetched on the wrong origin ("Failed to fetch"/empty JSON). **Always create an OWN tab via `Target.createTarget` and verify `location.href` contains the target origin before any fetch.**
- Injecting body text with apostrophes into single-quoted JS strings breaks the expression (evaluate returns None silently). Pass text as a **JSON.stringify'd payload argument** to an IIFE, never string-concat into JS source.
- r/LocalLLaMA flair IDs come from in-page `link_flair_v2.json`; pick 'I Built A Thing' for project showcases.

## Remaining manual step (user)
u/Realistic_Kitchen_65 is comment-only with low karma → Reddit demands human interaction for submissions (captcha). Options: solve one captcha manually in the open browser at old.reddit.com/r/LocalLLaMA/submit (text is ready in reports/post-dream-cycle-hn-reddit.md), or let the account age/karma grow via comments, then re-run `cron_dream_reddit_post2.py`. Title prepared: "I gave my AI agent a sleep cycle — it dreams about its errors and fixes them".
