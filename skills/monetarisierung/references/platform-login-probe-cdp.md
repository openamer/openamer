# Platform-Login-Probe via CDP (:9222) — reusable recipe

One run probes several marketplace/portal login states with **real evidence**
(screenshot PNG + body innerText), instead of trusting cached research.

## Why fresh WebSocket per navigation

The X-reply saga (see `openamer-browser-use`) proved long-lived CDP WS die
mid-flow on renderer swap (`WinError 10054`). A probe that navigates 5 sites
through ONE WS will silently half-fail. **Open a fresh WS per URL, close it,
close the tab.** Cheap and robust.

## Recipe (proven 2026-10-09, scripts/platform_login_probe.py)

For each target URL:
1. `PUT /json/new?<urlenc>` → new tab.
2. `websocket.create_connection(wsUrl, suppress_origin=True, timeout=30)`.
3. `Page.enable`, sleep `settle` (7s default — SPAs need it).
4. `Runtime.evaluate` (returnByValue) returning:
   `{url: location.href, title: document.title,
     text: body.innerText (collapsed) .slice(0,1200),
     login: all a/button innerText matching /log ?in|sign ?in|sign ?up|logout/i}`
   → the `login` array is the machine-readable login/logout marker; the
   redirected `url` reveals a login wall (e.g. `/dashboard` → `/auth?...`).
5. `Page.captureScreenshot` → write PNG.
6. close WS, `GET /json/close/<tabid>`.

## Evidence hygiene (the part that catches fake "ok")

A DOM string is a **claim**; a screenshot is **evidence** — but only if it is a
real image:
- **PNG size sanity:** a 1-2 KB PNG is a blank/error page. Real platform pages
  here were 47-182 KB. Check `os.path.getsize` and the magic bytes
  (`89 50 4e 47`). Do not present a 900-byte PNG as proof of "page loaded".
- **Vision on the 1-2 critical shots only** (user preference: no vision loops).
  Ask a **closed yes/no** question, e.g. "Ist ein eingeloggter Account sichtbar?
  Ja/Nein + Name? Zeigt der Status 'Unpublished'?" — via
  `openamer-browser/vision_or.py` (`analyze_image`, qwen3.7-flash, ~$0.0001/Bild).
  Vision confirmed the Gumroad account name + Unpublished status and the
  Cloudflare bot-wall — DOM alone could not distinguish those.
- Log with a per-claim line: `{ts, action, result}` including the evidence
  filename, so the log is auditable.

## Snapshot 2026-10-09 (reconfirmed, real HTTP/CDP evidence)

| Platform | State | Evidence |
|---|---|---|
| Gumroad | LIVE + eingeloggt ("damir saciro…"), product listed, **Unpublished** | HTTP 200 + `ev_mp_20261009_gumroad.png` (vision: account + Unpublished) |
| IssueHunt | Reachable (HTTP 200), **not logged in** ("Sign In/Sign Up/Researcher Sign Up") | `ev_mp_20261009_issuehunt.png` |
| Algora | Reachable (HTTP 200), hiring-landing only, **no public bounty board** | `ev_mp_20261009_algora.png` |
| Polar | `/dashboard` → **302 `/auth?return_to=…`** login wall | `ev_mp_20261009_polar.png` |
| HackerOne | **Cloudflare bot-wall** at `/users/sign_in` ("Nur einen Moment… Sicherheitsueberpruefung", Ray ID) — CDP cannot pass it | `ev_mp_20261009_hackerone.png` (vision: Cloudflare-Bot-Schutz) |

## Opire stale-data reconfirm (2026-10-09)

`curl -s https://api.opire.dev/rewards` (no auth) → HTTP 200, **5 rewards, 1st page**.
Of those 5, **2 are dead**: `rodrigompy/bugb#1` (GitHub issue `state=closed`) and
`buape/kiai-bounties#1` (repo **HTTP 404**). Live+open: `radumarias/rencfs#3` ($42,
Rust, 59 comments, 0 claimers), `trovu/trovu#329` ($30, 23 claimers), `flowese/
UdioWrapper#7` ($20, 18 claimers). Rule holds: **always cross-check each Opire
reward's underlying GitHub issue via API before acting** — the endpoint keeps
closed/deleted entries. All require GitHub login + Opire account ("Log in" wall).

## Snapshot 2026-10-11 (reconfirmed) + three new lessons

| Platform | State | Evidence |
|---|---|---|
| Gumroad | logged in "damir sacirovic"; product `idgxhe` €29 **Unpublished**; publish re-blocked: "You must connect at least one payment method" | `ev_mp_20261011_1627_gumroad_publish_fresh.png` |
| IssueHunt | reachable 200, **not** logged in; `/register` → **404** | `ev_mp_20261011_1625_issuehunt_home.png` |
| Algora | reachable 200, hiring landing only, **no bounty board** | `ev_mp_20261011_1625_algora_home.png` |
| Polar | **logged in** (damir95s@hotmail.com); `/dashboard`→`/onboarding/start`→ Get started → `/onboarding/personal` step 1/3 (First/Last Name, Country default **DE**, **Date of Birth** 3 selects 13/32/101, consent) | `ev_mp_20261011_1626_polar_step2.png` |
| HackerOne | `/users/sign_in` → **403** + Cloudflare challenge | `ev_mp_20261011_1625_hackerone_signin.png` |
| Opire | **now logged in** as GitHub `openamer` (cookie `token`) | `ev_mp_20261011_1629_opire_dashboard.png` |

1. **Third-party "Login with GitHub" is FREE via the :9222 session.** Chrome on
   :9222 holds GitHub cookies (`user_session`, `_gh_sess`, `logged_in`) for user
   `openamer`. Clicking `Log in` on `app.opire.dev` walks the GitHub OAuth flow
   **with no credentials** and lands logged in (cookie `token`). So a "session
   lost" platform is often one click away — probe for a GitHub-OAuth button
   before declaring the login unrecoverable. Only own-password / own-e-mail
   verification platforms stay user-only.
2. **`api.opire.dev/rewards` returns 403 without a `User-Agent` header.** Send
   `User-Agent: Mozilla/5.0` + `Accept: application/json` and it returns the full
   JSON list — each item carries `programmingLanguages`, `claimerUsers`,
   `tryingUsers`, `pendingPrice.value` (USD cents), so you can rank tractability
   programmatically instead of reading the rendered board.
3. **Multi-line JS in the probe script → Python SyntaxError.** A `js("...")` call
   with a plain `"`-string spanning two lines fails with `SyntaxError:
   unterminated string literal`. Always use **triple-quoted** `js(""" ... """)`
   for multi-line JS, and run `python -m py_compile <every probe>.py` before
   executing — a 1-second check that catches exactly this trap.

Opire board 2026-10-11 (5 rewards, $212): bugb#1 $100 closed/empty, rencfs#3 $42
Rust (is a PR, WinFsp-complex), trovu/trovu#329 $30 (23 claimers), UdioWrapper#7 $20
(19 claimers), kiai-bounties#1 $20 (404/private) → no tractable zero-solver fix.

## Snapshot 2026-10-12 (reconfirmed) — boards are gone, the wall is exact

| Platform | State | Evidence |
|---|---|---|
| Gumroad | logged in "damir sacirovic"; `idgxhe` €29 **Unpublished**, 0 sales. Edit banner verbatim: "You haven't connected a payout method yet, so you won't be able to publish this product for sale." | `ev_mp_20261012_0437_gumroad_edit.png` |
| IssueHunt | 200, **not** logged in; **no OSS bounty board left** — `/oss` → 404, `/explore` → 404; site is now company security programs only | `ev_mp_20261012_0439_issuehunt_oss.png` |
| Algora | 200, hiring landing only; `/bounties`, `/oss/bounties`, `/leaderboard` **all 404** | `ev_mp_20261012_0439_algora_home2.png` |
| Polar | logged in, onboarding open (`/onboarding/start`: sandbox = mock money, or org with legal data) | `ev_mp_20261012_0437_polar_onb2.png` |
| HackerOne | Cloudflare interstitial, `curl /users/sign_up` → **403** → account state is **unmeasured**, not "no account" | `ev_mp_20261012_0436_hackerone_signin.png` |
| Opire | session was **lost** on first probe (no cookie, nav "Log in"), then **restored** by one GitHub-OAuth click (`token`) | `ev_mp_20261012_0438_opire_final.png` |

### Gumroad payout form — exact fields (so the blocker is describable, never guessed)

Read from `/settings/payments`: `Pay to the order of` | `IBAN` + `Confirm IBAN` |
"Payouts will be made in EUR" | `Account type` = Individual | Business |
`First name` | `Last name` | `Address` | `City` | `Postal code` | `Country`
(dropdown includes **Bosnia and Herzegovina**). **PayPal is checkout only**
(buyer-side), NOT a payout route — do not conflate them. Nothing agent-side can
clear this: it is identity+bank data, user-only.

### Board topology now (durable)

IssueHunt and Algora have **removed** their OSS issue-bounty boards (404 on every
board path). Stop probing them as bounty sources. Opire is the only live,
submittable platform on this laptop; its own board is stale, so cross-check each
reward's GitHub issue before acting.

### Extra probe hygiene learned this run

- **`web_extract`/`curl` cannot see the JS-rendered state here** — `/oss` answered
  HTTP **200** to curl while the real browser rendered "404 This page does not
  exist". A status code is not the page: for a SPA-ish portal, confirm with the
  browser (title + body innerText) before calling a path live or dead.
- **`Network.getCookies {urls:[…]}` returns the honest login signal** when
  `document.cookie` is empty (httpOnly session cookies). Empty list + a `Log in`
  nav link = logged out; a present `token`/`polar_session`/`_gumroad_app_session`
  = logged in. Prefer the cookie list over reading the nav.
- **Re-login recipe (Opire, reusable for any "Login with GitHub" site):** navigate
  the site, `Runtime.evaluate` a small script that finds the element whose
  innerText matches `/log\s*in/i` and `.click()`s it; the GitHub OAuth flow then
  completes by itself because :9222 holds the `openamer` GitHub cookies. Assert
  success by the cookie list gaining `token` — not by the page looking logged in.
- **Reuse one `send()`/`js()`/`shot()` helper per probe and re-run the probe after
  every edit** to prove the edited helper still executes (reproduced the same
  findings and wrote 3 screenshots). A probe is verified by re-running it, not by
  the repo suite — `memory/si/` is outside `testpaths`.

