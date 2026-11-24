# Direct-PayPal Shop Recipe (no Gumroad needed)

Verified working: 2026-10-02, commit `219040a82` on openamer/openamer main.
All three URLs returned HTTP 200 after push.

## Why this matters

Gumroad publishing is BLOCKED until the user connects a payout method
(identity/IBAN form = user-only, agent must never touch it). But the PayPal
receive links already work. So a direct shop can go live TODAY without any
user-side signup:

- PayPal NCP button: https://www.paypal.com/ncp/payment/3HMBFYC9CQTMS (receive payments)
- PayPal.me: https://www.paypal.com/paypalme/openamer
- Ko-fi: https://ko-fi.com/openamer_agent (live per funding tracker)

## The three files (all on repo main)

1. `PRODUCTS.md` — product description + buy button + delivery instructions
2. `docs/shop/index.html` — Gumroad-style landing page (cream/pink, price
   card, feature list, PayPal CTA). Pure HTML/CSS, no build step.
3. `README.md` — new "🛒 Shop — Paid Products" section above the Sponsor
   section, linking both files.

## Verification checklist (run after every shop change)

1. HTML sanity: python html.parser walk — zero unclosed tags, zero mismatches.
2. PayPal link count: 1x in HTML, 1x in PRODUCTS.md, >=1 in README.
3. `git push` then curl all three raw.githubusercontent.com URLs -> 200.
4. curl the PayPal NCP link -> 200 (follow redirects, -L).
5. Full test suite green (pure docs/HTML change, but the gate applies).

## Delivery flow when a buyer pays

1. Buyer pays via PayPal button -> money lands in Damir's PayPal.
2. Buyer emails their address to openamer@web.de (stated on page).
3. Agent sends the product ZIP (e.g. OpenAmer-BugTriage-Agent-v1.zip,
   368 KB, 38 SKILL.md, integrity-verified) as email reply.
4. Later: migrate to Gumroad once payout method is connected (listing steps
   in SKILL.md) — keep both channels.

## Boundary

Never touch: PayPal login/password, bank IBAN, Gumroad identity form.
Product creation, landing page, README, packaging, shipping the ZIP = all
agent-automatable.