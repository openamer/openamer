# PayPal Hosted Button - Async Loading Fix

## Problem
PayPal's Hosted Button SDK und der `.render()`-Aufruf sind asynchron. Wenn das Script inline im `<body>` ausgeführt wird, bevor das externe SDK aus dem `<head>` geladen ist, schlägt der Render fehl — der Button bleibt unsichtbar.

**Symptom:** Der `div#paypal-container-...` existiert im DOM, aber der Button rendert nicht. `typeof paypal` ist `undefined` beim Script-Ausführungszeitpunkt.

## Fix

Zwei Änderungen:

### 1. Immer `.render()` aufrufen (nicht nur `paypal.HostedButtons({...})`)
Ohne `.render("#container")` wird der Button nie im DOM platziert:
```javascript
// FALSCH — kein Render
paypal.HostedButtons({ hostedButtonId: "BUTTON_ID" });

// RICHTIG — mit Render
paypal.HostedButtons({ hostedButtonId: "BUTTON_ID" })
  .render("#paypal-container-BUTTON_ID");
```

### 2. Async-Loading-Guard
Das Script darf erst ausgeführt werden, wenn das PayPal SDK vollständig geladen ist:
```html
<script>
  function renderPayPalButton() {
    if (typeof paypal !== 'undefined' && paypal.HostedButtons) {
      paypal.HostedButtons({
        hostedButtonId: "3HMBFYC9CQTMS",
      }).render("#paypal-container-3HMBFYC9CQTMS");
    }
  }
  // Warte auf window.load = SDK + alle Ressourcen geladen
  if (document.readyState === 'complete') {
    renderPayPalButton();
  } else {
    window.addEventListener('load', renderPayPalButton);
  }
</script>
```

### Vollständiges HTML-Muster
```html
<head>
  <!-- SDK im Head (lädt asynchron) -->
  <script src="https://www.paypal.com/sdk/js?client-id=CLIENT_ID&components=hosted-buttons&disable-funding=venmo&currency=EUR"></script>
</head>
<body>
  <!-- Container -->
  <div id="paypal-container-BUTTON_ID"></div>
  
  <!-- Render-Script mit Async-Guard -->
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
</body>
```

## Pitfalls
- **GitHub Pages Caching:** Nach dem Push dauert es 1-5 Minuten bis der Deploy live ist. `raw.githubusercontent.com` zeigt sofort den neuen Code, die GitHub Pages CDN braucht länger.
- **DataDome auf PayPal Dashboard:** Das Dashboard (paypal.com/buttons/saved) blockt headless-CDP. Der Payment-Link (paypal.com/ncp/payment/...) selbst funktioniert ohne Bot-Block.
- **Button-ID:** z.B. `3HMBFYC9CQTMS`. Diese ID ist in der PayPal-Console unter "Gespeicherte Links und Buttons" sichtbar.