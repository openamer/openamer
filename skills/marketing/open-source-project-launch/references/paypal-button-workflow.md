# PayPal Hosted Button Workflow (OpenAmer session Aug 2026)

## Session Overview
Created a PayPal hosted payment button for OpenAmer (open-source AI agent),
embedded it in the project website, and updated all repo references.

## Button Details

| Field | Value |
|-------|-------|
| Product | Skill-Pack / Plugin Käufe |
| Price | Vom Kunden festgelegter Preis (customer-defined) |
| Currency | EUR |
| Delivery Address | Ja (captured) |
| Custom Labels | "10" |

### Button Styling
- **Gestapelte Buttons:** Vertikal | Rechteck | Mittel | Gold
  - PayPal-Button: "PayPal" | Zweiter Button: "PayPal empfohlen"
  - Checkout-Button: "Kaufabwicklung"
- **Einzelner Button:** Rechteck | Mittel | "Jetzt kaufen"
- **Payment Methods:** PayPal, Später bezahlen, Apple Pay, Debit-/Kreditkarte
- **Auto-Rückleitung:** Keine

### Generated IDs
- **Hosted Button ID:** `3HMBFYC9CQTMS`
- **Client ID:** `BAApuQJllkY1E5zO5E-pMbGFzr3EiBEiXjPy8e_sR0yz8a3PNTVjSjnt3BCngGLXQsjeHI1IoPqZmpBpa4`
- **Payment Link:** `https://www.paypal.com/ncp/payment/3HMBFYC9CQTMS`

## Exact Code Snippets Used

### SDK Script (once per page in `<head>`)
```html
<script src="https://www.paypal.com/sdk/js?client-id=BAApuQJllkY1E5zO5E-pMbGFzr3EiBEiXjPy8e_sR0yz8a3PNTVjSjnt3BCngGLXQsjeHI1IoPqZmpBpa4&components=hosted-buttons&disable-funding=venmo&currency=EUR">
</script>
```

### Button Container & Render (in `<body>`)

**⚠️ CRITICAL — Async SDK Fix:** The PayPal SDK loads asynchronously. If you call `paypal.HostedButtons()` inline, it runs BEFORE the SDK finishes loading → `paypal` is `undefined` → nothing renders and no console error shows.

**Always use this pattern with `.render()` + `load` event guard:**

```html
<div id="paypal-container-3HMBFYC9CQTMS"></div>
<script>
  function renderPayPalButton() {
    if (typeof paypal !== 'undefined' && paypal.HostedButtons) {
      paypal.HostedButtons({
        hostedButtonId: "3HMBFYC9CQTMS",
      }).render("#paypal-container-3HMBFYC9CQTMS");
    }
  }
  if (document.readyState === 'complete') {
    renderPayPalButton();
  } else {
    window.addEventListener('load', renderPayPalButton);
  }
</script>
```

**Why:**
- `.render("#container-id")` is required — omitting it creates the button but never inserts it in the DOM
- `window.addEventListener('load', ...)` ensures the async SDK has finished loading before calling HostedButtons
- The `typeof paypal !== 'undefined'` guard is belt-and-suspenders against race conditions

### README Badge
```markdown
<a href="https://www.paypal.com/ncp/payment/3HMBFYC9CQTMS"><img src="https://img.shields.io/badge/PayPal-OpenAmer-00457C?style=for-the-badge&logo=paypal" alt="Donate via PayPal"></a>
```

## Files Modified
- `docs/index.html` — added SDK in `<head>`, container+Support section before footer
- `docs/academy.html` — same pattern but dark theme (.section background: #1a1a1a)
- `README.md` — PayPal badge URL updated from old paypalme link
- `SPONSORS.md` — added PayPal section with direct link and table
- `LAUNCH/support_posts.md` — created with 5 social media posts

## Git Commit
```bash
git add README.md SPONSORS.md docs/index.html docs/academy.html LAUNCH/support_posts.md
git commit -m "💜 PayPal-Zahlungsbutton live"
git push
```

## PayPal Headless Browser Quirks
- **Dashboard/login** (`/buttons/saved`, `/myaccount/*`) blocked by DataDome bot detection
- **Payment checkout link** (`/ncp/payment/{id}`) works fine in headless browsers
- Headless browser lands on PayPal homepage → clicking "Einloggen" triggers DataDome device check
- **Workaround:** user provides the hosted button ID from their real browser session; agent handles everything else