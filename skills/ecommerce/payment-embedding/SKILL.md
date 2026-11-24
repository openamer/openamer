---
name: payment-embedding
category: ecommerce
tags: [paypal, payment, checkout, button, embedding, fiverr, marketplace]
trigger: "Use when embedding PayPal buttons on web pages or listing products on marketplaces."
description: "Embed PayPal buttons on pages and list on marketplaces."
---

# Payment Embedding

Set up PayPal payments on static sites and list products on Fiverr.

## 1. PayPal Button Creation

1. PayPal → **Zahlungsbuttons** → choose link or website button
2. Fill: name, description, price (custom/fixed), currency (EUR), images
3. Save → copy **Hosted Button ID**

### Code Snippets

**SDK (`<head>`):**
```html
<script src="https://www.paypal.com/sdk/js?client-id=CLIENT_ID&components=hosted-buttons&disable-funding=venmo&currency=EUR">
</script>
```

**Button + Render (`<body>`):**
```html
<div id="paypal-container-BUTTON_ID"></div>
<script>
  function renderPayPalButton() {
    if (typeof paypal !== 'undefined' && paypal.HostedButtons) {
      paypal.HostedButtons({
        hostedButtonId: "BUTTON_ID",
      }).render("#paypal-container-BUTTON_ID");
    }
  }
  if (document.readyState === 'complete') {
    renderPayPalButton();
  } else {
    window.addEventListener('load', renderPayPalButton);
  }
</script>
```

> **⚠️ Async SDK Fix:** SDK loads async — inline script runs before `paypal` is defined. Always use the `window.load` guard.

**Direct payment link:** `https://www.paypal.com/ncp/payment/BUTTON_ID`

## 2. GitHub Pages

- SDK in `<head>`, container+render in `<body>` per page
- CDN: wait 1-5 min after push, verify with `typeof paypal`

## 3. Fiverr Gig Structure

1. Title: "I will build you a custom AI agent pipeline in 48h"
2. Category: Programming & Tech → AI Agents → Automation
3. Price: matches PayPal tier
4. Description: problem → solution → deliverables → guarantee
5. Requirements: use case, tech stack

## Pitfalls

1. **SDK async timing** — #1 failure. Use `window.load` guard.
2. **Headless blocks** — PayPal/Fiverr block CDP dashboards. Payment links work headless.
3. **Missing `.render()`** — container without `.render()` shows nothing.

## Dead-funding-channel audit (OpenAmer landing, live 2026-09-10)

Before trusting ANY funding link on a page: measure it with curl (`-o /dev/null
-w "%{http_code}"`), never assume it works because it's in the docs. Live audit
found on the OpenAmer landing/store/consulting pages:

- `ko-fi.com/openamer_agent` → **403** (dead account, even without `_agent`)
- `buymeacoffee.com/openamer` → **404** (dead account)
- `github.com/sponsors/openamer` → **404** (Sponsors dashboard never set up;
  the URL redirects to the plain profile — that redirect is NOT a working
  sponsor page)
- `paypal.com/ncp/payment/3HMBFYC9CQTMS` → **200** (verified live)
- `issuehunt.com/r/openamer` → **200**

Fix pattern: replace dead links everywhere (landing `docs/index.html`,
`skills-store.html`, `consulting.html` — check ALL pages, the same dead badge
is usually copy-pasted across several), comment the dead slot in
`.github/FUNDING.yml` (`ko_fi: # dead 403 — re-add when account exists`) so the
intent survives, and promote the one verified working channel to primary.

**Deep link verification (beyond HTTP status, live 2026-09-10):** a 200 alone
is not proof. PayPal NCP pages embed `window.__initialState__` with the hosted
button details — read it with curl, no SDK needed:
```bash
curl -s -L -A "Mozilla/5.0" "https://www.paypal.com/ncp/payment/<ID>" \
  | grep -oE '"status":"[A-Z]+"|"item_name","value":"[^"]*"|"currency_code","value":"[^"]*"'
```
`"status":"ACTIVE"` + item_name (e.g. "OpenAmer Supporter", VARIABLE_PRICE,
default amount_label) = link genuinely live and configured. Then close the loop
with the real buyer path: open the landing page in the browser, click the pay
button, confirm the actual PayPal checkout view renders with the amount field.
That full chain (landing → click → checkout) was verified live for
`3HMBFYC9CQTMS` on 2026-09-10. Ko-fi note: a *redirect to ko-fi.com homepage*
also means dead profile, same as 403/404 — treat any non-profile final URL as dead.

Store checkout: never ship "Coming Soon" alert-buttons on a paid store — wire
every item to the hosted PayPal link (`/ncp/payment/<id>`, amount selectable)
instead. Verify the LIVE GitHub Pages page after push (CDN lag 1–5 min):
`curl -s <live-url> | grep -c "ko-fi"` must be 0.

**Browser E2E pay-flow verification (2026-09-10):** after fixing dead links,
verify the full chain in the browser, not just curl: open the landing page,
click the pay button (browser_click on the button ref), then snapshot — the
PayPal checkout renders as a `main` with `<h4>` item name ("OpenAmer
Supporter"), a currency textbox prefilled with the default amount, and
"Bestellübersicht". This catches wrong-button wiring that curl on the PayPal
URL can't see (the checkout page renders correctly even if the PAGE's button
points elsewhere or carries a stale label like "Buy (ko-fi)"). Update the
visible label text at the same time as the href — a dead-channel label on a
working link reads broken to visitors and is the same bug class.

**Phantom-success gotcha:** a POST reporting success (comment ID returned) does
not prove the object is visible where you expect — verify via direct GET on the
object ID, not a list query (list pagination/sorting can hide it).