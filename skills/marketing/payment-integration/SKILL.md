---
name: payment-integration
description: "OSS donation setup: PayPal buttons, badges, SPONSORS.md."
version: 1.0.0
platforms: [web]
metadata:
  openamer:
    tags: [payment, donation, sponsorship, paypal, oss, funding]
    category: marketing
    related_skills: [open-source-project-launch]
---

# Payment Integration for OSS Donations & Support

Class-level skill for setting up payment/donation infrastructure on an
open-source project. Covers the full pipeline from creating payment
buttons on PayPal through embedding on the website to updating all
public-facing surfaces (README, SPONSORS.md, landing page).

> **Load**: `skill_view(name='payment-integration')`
> **When**: User asks about adding PayPal, donation buttons, payment links,
> sponsors page, or Zahlungslinks for an OSS project.
>
> **Related**: `open-source-project-launch` for the promotion phase after
> payment infrastructure is live.

---

## Full Workflow

### Step 1 — Create Payment Button on PayPal

Navigate to `https://www.paypal.com/buttons/saved` (logged in).

- **Zahlungslink & QR-Code** — for sharing directly (no website needed).
  Get a shareable URL like `paypal.com/ncp/payment/<HOSTED_ID>`.
- **Zahlungsbuttons** — for embedding in HTML/website.
  Choose button style (gold, blue, silver), shape (rect/pill), size.

Product fields:
| Field | Example |
|-------|---------|
| Artikelname | "OpenAmer Supporter" / "Skill-Pack Support" |
| Beschreibung | "Skill-Pack / Plugin Käufe" |
| Preis | Festpreis or "Vom Kunden festgelegter Preis" |
| Währung | EUR, USD, etc. |
| Anzahl | Multi-buy toggle |

After creation, PayPal provides:
- **Hosted Button ID** (e.g. `3HMBFYC9CQTMS`)
- **SDK snippet** for `<head>`
- **Container snippet** for `<body>`
- **PDF download** with detailed instructions

### Step 2 — Embed SDK in Website

Add the PayPal SDK script to `<head>` on every page that hosts a button:

```html
<script src="https://www.paypal.com/sdk/js?client-id=<YOUR_CLIENT_ID>&components=hosted-buttons&disable-funding=venmo&currency=EUR">
</script>
```

The `hosted-buttons` component is required for hosted button rendering.
The `disable-funding` param hides payment methods you don't support.

### Step 3 — Add Button Container

Add the container div + render script in `<body>` where the button should appear:

```html
<div id="paypal-container-3HMBFYC9CQTMS"></div>
<script>
  paypal.HostedButtons({
    hostedButtonId: "3HMBFYC9CQTMS",
  }).render("#paypal-container-3HMBFYC9CQTMS")
</script>
```

**Pitfall**: The SDK must load *before* the render script. PayPal's snippet
in the `<head>` handles this via async loading — do not move it to `<body>`.

**Verification**: Open the page in a browser. The PayPal button should render
inside the container. The hosted payment page at
`https://www.paypal.com/ncp/payment/<HOSTED_ID>` should load and accept
test transactions.

### Step 4 — Update README Badge

Replace the old PayPal.me badge URL with the new hosted payment link:

```markdown
[![PayPal](https://img.shields.io/badge/PayPal-OpenAmer-00457C?style=for-the-badge&logo=paypal)]
(https://www.paypal.com/ncp/payment/3HMBFYC9CQTMS)
```

Shields.io supports `style=for-the-badge` (large, bold) and
`style=flat-square` (compact). Use color `00457C` (PayPal blue).

### Step 5 — Update SPONSORS.md

Add a PayPal section with the direct payment link:

```markdown
### 💳 PayPal (One-time / Custom Amount)
Support directly via PayPal — every contribution counts.

[**→ Pay via PayPal**](https://www.paypal.com/ncp/payment/<HOSTED_ID>)
```

### Step 6 — Test the Payment Link

Navigate to `https://www.paypal.com/ncp/payment/<HOSTED_ID>` and verify:
- Product title and description are correct
- Price / custom-amount field accepts valid values
- Express Checkout and card options are visible
- Footer links: "Diesen Link melden", "Datenschutz"

## Multiple Buttons: Consulting Tiers

For tiered products (Quick Audit €499 → Pipeline €1,999 → Full Stack €4,999),
create separate hosted buttons per tier on `paypal.com/buttons/saved`. Each
tier gets its own `hostedButtonId`.

## QR Code for Social Media

PayPal auto-generates a QR code for each payment link. Share on:
X/Twitter, GitHub repo, Discord pins, conference slides, email sigs.

## Pitfalls

1. **PayPal blocks headless browsers** — DataDome blocks `browser_navigate`
   to PayPal. Use the user's logged-in browser via `computer_use` or ask
   for the hosted ID manually.
2. **SDK must load before render** — Keep the SDK in `<head>`, render in
   `<body>`. The snippet PayPal provides handles this correctly.
3. **Client ID is per-account** — never reuse across different PayPal accounts.
4. **Button container id must match** — div `id` and render `selector` must
   match exactly. A mismatch = silent failure, no button.
5. **Desktop capture may fail** — zombie cua-driver process can cause
   "Connection closed" on `capture()`. Fall back to `browser_*` tools
   (CDP Chromium) for web-based PayPal tasks.
6. **CSP blocks PayPal SDK** — Add `paypal.com` and `paypalobjects.com`
   to CSP `script-src`, `style-src`, `img-src`, `frame-src`, `connect-src`.

## Verification Checklist

- [ ] Payment link loads: `paypal.com/ncp/payment/<ID>` → correct product
- [ ] SDK loads in browser console (no CSP / 404 errors)
- [ ] Button renders on all website target pages
- [ ] README badge links to new payment URL
- [ ] SPONSORS.md has PayPal section with direct link