# IndieHackers posting attempt – 2026-09-11 (cron)

## Verdict

**Cannot post.** No authenticated account, no credentials on disk. Verified live, not assumed.

## Evidence chain (all via real tool calls)

1. `curl http://127.0.0.1:9333/json/version` → **CDP_9333_DOWN** (task text port is wrong).
2. `curl http://127.0.0.1:9222/json/version` → Chrome/152.0.7977.84, non-headless. **This is the port.**
3. `browser_navigate https://www.indiehackers.com/` → header shows `link "Sign in"` + `link "Join"` → logged out.
4. On `/post/looking-for-founders-who-need-ai-automation-096972a480`, clicked `POST COMMENT` (@e32)
   → snapshot became a **login modal**: `button "Continue with Google"` + `link "Sign in"`.
5. On `/submit`, clicked `Submit Story` (@e13) → **sign-in form** (Email, Password, SIGN IN, Google).
6. `sessions.json` `IndieHackers` key = 5 cookies, **all anonymous**:
   `_ga`, `ih-anon-id`, `ih-ab-bucket`, `_ga_W1TFN9RN75`, `OptanonConsent`. No auth cookie.
7. `.env` has no IndieHackers/IH keys. No IndieHackers credentials anywhere under the profile.

## Why cookie injection can't fix it

IndieHackers auth = **Firebase Auth**; the session token is kept in browser IndexedDB /
localStorage, not in a cookie. The session_manager cookie-inject approach that works for
HN (where the login cookie is a plain `user=...` value) does **not** apply here.

## Validated assets (so the post is ready the moment login exists)

- GitHub `openamer/openamer`: real, **5 stars**, pushed 2026-09-11.
- Discord invite `gckmapHrr`: valid, guild "openamer", **1 member**, expires 2026-09-22.
- `consulting.html` 200, PayPal link 200, docs site 200.
- Target thread "Looking for founders who need AI automation" (Kay, 20.08.2026): live, 15 comments.

## Artifacts

- Post text: `memory/outbound/indiehackers-post-20260911.md`
- Report: `memory/outbound/promotion-report-20260911.md`

## Next action (human)

Log in once at IndieHackers with Google in the Chrome running on :9222
(profile `%APPDATA%/openamer-browser`). Then the prepared post + comments can be submitted.
