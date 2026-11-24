# Product Hunt media upload — autonomous bypass attempts (2026-08-23)

Goal: upload 6 gallery PNGs to the Product Hunt edit page without a human,
using only agent tools. The Media button (`Button 'Media'`, AX at ~(600,644))
opens a native Windows file dialog. cua-driver cannot drive it. These are the
four autonomous alternatives that were tried and FAILED, so future sessions
do not re-walk them:

## 1. browser_console file-input injection — FAILED
```js
document.querySelectorAll('input[type=file]').length  // → 0
```
The `browser_*` tool runs a SEPARATE headless browser instance (agent-browser /
Browserbase) with its own empty profile. It has NO Product Hunt cookies, so the
DOM never contains the edit form's file inputs. Injecting `input[type=file]`
and setting `files` is pointless without the logged-in session.

## 2. browser_navigate to the edit URL — FAILED (Cloudflare wall)
`browser_navigate('https://www.producthunt.com/posts/github-481/edit')` returns
the Cloudflare "Sicherheitsüberprüfung wird durchgeführt" interstitial
("www.producthunt.com ... Nur einen Moment ..."). Session cookies from the
user's real Edge do not carry into the headless profile. Even a plain
`browser_navigate('https://www.producthunt.com/')` hits the same wall.

## 3. Localhost HTTP server for the assets — NOT HELPFUL
`python3 -m http.server 8999` in `LAUNCH/assets/` served the PNGs fine
(verified via `browser_navigate('http://localhost:8999/')` directory listing,
9 elements: 6 screens + 2 logos + icon). This proves asset reachability is
NOT the problem — but there is no URL field on Product Hunt for gallery images;
the UI only accepts a native file picker. Serving files locally changes nothing.

## 4. fetch to Product Hunt GraphQL from browser_console — FAILED
```js
fetch('https://www.producthunt.com/_api/graphql', {...})
// → TypeError: Failed to fetch  (CORS / Cloudflare block)
```
Product Hunt's GraphQL endpoint rejects cross-origin fetches from the headless
context; no auth cookie is present either. No REST upload API is publicly
documented for gallery images.

## What DOES work (proven same session)
- Driving the ALREADY-OPEN, logged-in Edge tab via computer_use: name, tagline,
  description, X account, tags, makers, pricing — all editable + verifiable.
- Save + "All changes saved successfully." confirmation via AX tree.
- Verify field content via the Edit element's label char count
  (`Name of the launch 8/40`).

## Conclusion
Native Windows file-open dialogs are the hard wall. Report it once, factually,
with the asset paths. The gallery upload is the single remaining manual step;
do not dress it up as a numbered to-do list and do not ask "what next".
