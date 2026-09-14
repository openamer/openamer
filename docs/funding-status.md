# Funding Link Status — Live Audit

**Audit date:** 2026-09-14 (Europe/Berlin)
**Method:** `rg` sweep of the whole repo for payment/donation patterns, then a live
HTTP check on every distinct user-facing URL plus a rendered-page check
(browser) for SPA pages where an HTTP status alone is meaningless (PayPal.Me,
Ko-fi, IssueHunt). Every classification below is backed by the literal tool
output quoted in the evidence column.

**Host tested from:** git-bash (MSYS) on Windows 10.
**Published site:** `https://openamer.github.io/openamer/` — the files in
`docs/*.html` are served at the site **root** (`/index.html`, `/landing.html`,
`/consulting.html`, `/skills-store.html`, `/academy.html`). All five returned
HTTP `200`, so every funding link inside them is user-facing on the live site.
(The Docusaurus build is served under `/docs/`, which currently returns `404` —
unrelated to funding.)

---

## Summary

| # | URL | Where it appears (file:line) | HTTP | Verdict |
|---|-----|------------------------------|------|---------|
| 1 | `https://www.paypal.com/ncp/payment/3HMBFYC9CQTMS` | `README.md:29`, `README.md:32`, `README.md:627`; `SPONSORS.md:11`; `docs/index.html:181`, `docs/index.html:182`; `docs/landing.html:62`, `docs/landing.html:83`; `docs/consulting.html:208`, `docs/consulting.html:209`; `docs/skills-store.html:73,82,91,100,137,138`; `docs/academy.html:81` (hosted button `3HMBFYC9CQTMS`); `LAUNCH/support_posts.md:9,25,41,66,86` | **200** | **LIVE** ✅ |
| 2 | `https://www.paypal.com/paypalme/openamer` | `scripts/funding.py:36` | 200 (SPA) | **DEAD** ❌ (renders "Profil nicht gefunden") |
| 3 | `https://github.com/sponsors/openamer` | `LICENSE.md:94`; `docs/landing.html:37`, `docs/landing.html:68` | 302→200 | **DEAD**  (redirects to plain profile, not a sponsor page) |
| 4 | `https://buymeacoffee.com/openamer` | `LICENSE.md:95` | **404** | **DEAD** ❌ |
| 5 | `https://ko-fi.com/openamer_agent` | `LAUNCH/support_posts.md:45` | 200→homepage | **DEAD** ❌ (redirects to ko-fi.com homepage) |
| 6 | `https://oss.issuehunt.io/r/openamer` | `README.md:627`; `SPONSORS.md:16`; `scripts/funding.py:37` | 200 (soft-404) | **DEAD** ❌ (page renders "404") |
| 7 | `https://www.paypal.com/sdk/js?client-id=BAApuQJllkY1E5zO5E-pMbGFzr3EiBEiXjPy8e_sR0yz8a3PNTVjSjnt3BCngGLXQsjeHI1IoPqZmpBpa4…` | `docs/index.html:14`; `docs/landing.html` (SDK); `docs/consulting.html:13`; `docs/skills-store.html:13`; `docs/academy.html:32` | **200** | **LIVE** ✅ (PayPal SDK asset; supports link #1) |

**Net result:** one working pay route (the PayPal hosted button / `ncp/payment`
link). Every other "support" platform advertised in the repo is dead.

---

## Verbatim evidence (literal tool output)

### Link #1 — PayPal hosted button — LIVE

```
$ curl -s -o /dev/null -w '%{http_code} final=%{url_effective}\n' -L --max-time 30 \
    "https://www.paypal.com/ncp/payment/3HMBFYC9CQTMS"
200 final=https://www.paypal.com/ncp/payment/3HMBFYC9CQTMS
```

Rendered page (browser, 2026-09-14) — confirms a real, functional checkout:

```
heading "OpenAmer Supporter"
paragraph "Skill-Pack / Plugin Käufe"
textbox "10 €"  (amount field)
heading "Bestellübersicht"
group "Express-Checkout-Optionen"
group "oder mit Karte bezahlen"
```

→ **LIVE.** Valid payment page, accepts custom amount and card.

### Link #2 — `paypalme/openamer` — DEAD

```
$ curl -s -o /dev/null -w '%{http_code} final=%{url_effective}\n' -L --max-time 30 \
    "https://www.paypal.com/paypalme/openamer"
200 final=https://www.paypal.com/paypalme/openamer
```

HTTP `200` is misleading: PayPal.Me returns `200` for **any** handle (a bogus
control handle `…/paypalme/zzqqxx998877nope` also returned `200`). The rendered
page is authoritative:

```
$ browser render of https://www.paypal.com/paypalme/openamer
heading "Wir können dieses Profil nicht finden"
text  "Vergewissern Sie sich, dass der Link korrekt ist und das Profil nicht
       deaktiviert wurde."
```

→ **DEAD.** PayPal itself says the profile cannot be found. This is a *different*
PayPal target than the working `ncp/payment` link, and it is the one hard-coded
in `scripts/funding.py` (`PAYMENT_LINKS["paypal"]`).

### Link #3 — GitHub Sponsors — DEAD

```
$ curl -sI -L --max-time 25 "https://github.com/sponsors/openamer" | grep -iE '^(HTTP/|location:)'
HTTP/1.1 302 Found
Location: https://github.com/openamer
HTTP/1.1 200 OK
```

→ **DEAD.** `/sponsors/openamer` 302-redirects to the bare profile
`github.com/openamer` — the canonical signature of "GitHub Sponsors is not set
up for this account". The user clicks "Become a sponsor" and lands on the repo
profile, not a sponsorship page.

### Link #4 — Buy Me a Coffee — DEAD

```
$ curl -sI -L --max-time 25 "https://buymeacoffee.com/openamer" | grep -iE '^(HTTP/|location:)'
HTTP/1.1 404 Not Found
```

→ **DEAD.** 404.

### Link #5 — Ko-fi — DEAD

```
$ curl -s -o /dev/null -w '%{http_code} final=%{url_effective}\n' -L --max-time 20 \
    -A "Mozilla/5.0 … Chrome/120 Safari/537.36" "https://ko-fi.com/openamer_agent"
200 final=https://ko-fi.com/
```

→ **DEAD.** With a browser user-agent it returns `200` but the *effective final
URL is the ko-fi.com homepage* — the `/openamer_agent` page does not exist and
is bounced to the site root. (With curl's default UA it returned `403`; the
browser-UA redirect is the reliable signal.) This matches the note already in
`.github/FUNDING.yml`.

### Link #6 — IssueHunt — DEAD

```
$ curl -s -o /dev/null -w '%{http_code} final=%{url_effective}\n' -L --max-time 30 \
    "https://oss.issuehunt.io/r/openamer"
200 final=https://oss.issuehunt.io/r/openamer
```

HTTP `200`, but the rendered page is a 404:

```
$ browser render of https://oss.issuehunt.io/r/openamer
heading "404"
```

→ **DEAD.** Soft-404: the server answers `200` but the body is the IssueHunt
"404" page. The repo's `openamer` org/repo is not registered on IssueHunt. This
contradicts the claim in `.github/FUNDING.yml` and `scripts/funding.py`
("issuehunt (200) — verified live").

### Link #7 — PayPal SDK — LIVE

```
$ curl -s -o /dev/null -w '%{http_code} final=%{url_effective}\n' -L --max-time 30 \
    "https://www.paypal.com/sdk/js?client-id=BAApuQJllkY1E5zO5E-pMbGFzr3EiBEiXjPy8e_sR0yz8a3PNTVjSjnt3BCngGLXQsjeHI1IoPqZmpBpa4&components=hosted-buttons&disable-funding=venmo&currency=EUR"
200 final=https://www.paypal.com/sdk/js?…(same URL)
```

→ **LIVE.** The SDK asset loads, which is what renders the hosted buttons in
`docs/*.html`. The `client-id` belongs to the same PayPal merchant as the
working hosted button.

---

## Non-URL funding references

| Reference | Where | Status |
|---|---|---|
| `enterprise@openamer.ai` (sales) | `LICENSE.md:50` | Mailbox — not HTTP-testable. Only meaningful if the address exists. |
| `openamer@openamer.ai` (contact) | `SPONSORS.md:29` (`mailto:`) | Mailbox — not HTTP-testable. |
| hosted-button id `3HMBFYC9CQTMS` | `docs/academy.html:87`, `docs/index.html:203`, `docs/consulting.html:191`, `docs/skills-store.html:118` | LIVE — same merchant as link #1. |
| `paypal-container-QUICK-AUDIT-PLACEHOLDER` / `-PIPELINE-PLACEHOLDER` / `-FULLSTACK-PLACEHOLDER` | `docs/consulting.html:92,109,125` | **PLACEHOLDER, not a link.** These tier buttons are non-functional by design ("Coming soon — use general support button below", `docs/consulting.html:93,110,126`). They render nothing; the page's working route is the generic hosted button at `docs/consulting.html:185`. Not dead, but no tier checkout exists. |
| No `paypal.me` handle, IBAN, bank account, or donation e-mail in user-facing docs beyond the above. | — | — |

---

## Remove these (dead) — owner action required

Do **not** delete from published pages without the owner's decision; they are
listed here precisely so the owner can choose. Ordered by user impact:

1. **`https://github.com/sponsors/openamer`** — appears as a *"Become a sponsor"*
   / *"Sponsor"* button on the **live landing page** (`docs/landing.html:37,68`)
   and in `LICENSE.md:94`. Clicks land on the plain GitHub profile. **Highest
   priority** — it is a prominent support CTA that goes nowhere.
2. **`https://buymeacoffee.com/openamer`** — `LICENSE.md:95` (404).
3. **`https://oss.issuehunt.io/r/openamer`** — `README.md:627`, `SPONSORS.md:16`,
   `scripts/funding.py:37` (soft-404). Also fix the false "verified live" claims
   in `.github/FUNDING.yml` and `scripts/funding.py`.
4. **`https://www.paypal.com/paypalme/openamer`** — `scripts/funding.py:36`
   (PayPal profile not found). Note this differs from the working link #1.
5. **`https://ko-fi.com/openamer_agent`** — `LAUNCH/support_posts.md:45`
   (redirects to homepage). **Unreleased draft** — the file promotes a dead
   Ko-fi link and a dead GitHub-Sponsors link; do not publish it as-is.
6. **`LAUNCH/support_posts.md:43-45`** — draft text advertising *"GitHub Sponsors
   ($3-$250/mo) + Ko-fi available"*, both of which are dead.

## Keep these (live)

1. **`https://www.paypal.com/ncp/payment/3HMBFYC9CQTMS`** — the one working pay
   route. Used across `README.md`, `SPONSORS.md`, and all five `docs/*.html`
   pages. ✅
2. **The PayPal hosted button id `3HMBFYC9CQTMS`** rendered via the PayPal SDK
   in the `docs/*.html` pages. ✅

## Internal inconsistencies found (flag, not a link issue)

- `scripts/funding.py:36` uses `paypalme/openamer` (DEAD) while every user-facing
  page uses `ncp/payment/3HMBFYC9CQTMS` (LIVE) — the funding script points at a
  different, broken PayPal target than the actual donation button.
- `.github/FUNDING.yml` header comment and `scripts/funding.py:30,4-5` both claim
  "issuehunt (200) — verified live 2026-09-11"; the page is in fact a soft-404
  (see #6). The same comment correctly flags ko-fi and buymeacoffee as dead, and
  GitHub Sponsors as "not set up" — consistent with this audit.
- `README.md:630` funding bar claims `total_raised=$30 | monthly_recurring=$28`
  (auto-generated by the funding cron); treat as illustrative, not verified here.

---

*Every status above is reproducible with the exact commands quoted. No status
was inferred without a literal HTTP or rendered-page result.*