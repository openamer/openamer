# SPA-State & Cookie-Login-Probe (browser_cdp Tool-Pfad)

Reusable recipes for the monetization/platform probe. All verified 2026-10-13.

## 1. Publish/Status-State aus client-gerenderten SPAs lesen

**Problem:** `document.body.innerText` ist auf React/Inertia-Seiten (z.B. die
Gumroad-Produktseite) **LEER**, obwohl die Seite vollstaendig geladen und
gerendert ist. Ein "body text empty" heisst also NICHT "Seite kaputt".

**Fix:** Inertia-Props aus dem `#app`-Attribut lesen:

```js
document.getElementById('app').getAttribute('data-page')   // JSON-String
```

Gumroad liefert dort u.a.: `product.is_published`,
`current_seller.publish_blocked_reason`, `current_seller.has_published_products`,
`product.price_cents` / `currency_code`, `product.description_html`,
`product.public_files`, `product.summary`.

2026-10-13 damit exakt diagnostiziert:
`is_published=false`, `has_published_products=false`,
`publish_blocked_reason="no_payout_method"`, `description_html=null`,
`public_files=[]`.

**Generalisierbar:** bei leerem `innerText` immer nach diesen Quellen greifen:
`#app[data-page]` (Inertia), `__NEXT_DATA__` (Next.js),
`window.__initialState__` (u.a. PayPal hosted buttons).

Der Server liefert das Attribut bei jedem Load neu -> es ist Live-Evidenz,
nicht ein Cache. Fuer den Report eine Zeile daraus zitieren.

## 2. Login-Status vieler Plattformen mit EINEM Call

- **`Storage.getCookies`** (browser-level) holt ALLE Cookies in einem Call.
  `Network.getAllCookies` wird vom `browser_cdp`-Tool **nicht** erkannt:
  `CDP error: {'code': -32601, 'message': "'Network.getAllCookies' wasn't found"}`.
  -> `method='Storage.getCookies', params={}` benutzen.
- Output ist riesig (100+ KB) und wird auf Platte gepersistiert -> **nicht** in
  den Kontext lesen. Per Python nach Domain gruppieren und nur Auth-Treffer
  ausgeben.
- Auth-Cookie-Mapping (fehlt der Cookie = NICHT eingeloggt):

| Plattform | Auth-Cookie |
|---|---|
| Gumroad | `_gumroad_app_session` |
| Polar | `polar_session` (+ `polar_last_login_method`) |
| GitHub | `user_session` / `dotcom_user` / `logged_in` |
| Product Hunt | `_producthunt_session_production` |
| Dev.to | `_Devto_Forem_Session` / `current_user` |
| Reddit | `reddit_session` |
| issuehunt.io | (nur `_ga`, intercom, mixpanel = anonym) |
| algora.io | (nur `_algora_key` = Fingerprint) |
| hackerone.com | `__Host-session` (auch anonym gesetzt -> kein Konto-Beweis) |

**Cookie vorhanden != nutzbar:** der Cookie beweist die Session-Existenz, nicht
die Funktionsfaehigkeit. Bei Zweifel die geschuetzte Seite laden und den
Seiteninhalt pruefen (Nav "Log in" statt Username).

## 3. "Ist Plattform X noch ein Bounty-Board?" per Redirect/404 pruefen

Nie aus dem Cache glauben — alte Board-Pfade und Subdomains einzeln messen:

```bash
for u in https://bounties.algora.io https://console.algora.io \
         https://algora.io/bounties https://issuehunt.io/repos ; do
  curl -s -o /dev/null -w "%{http_code} -> %{url_effective}\n" -L --max-time 20 "$u"
done
```

2026-10-13: `bounties.algora.io` und `console.algora.io` -> 302/Endet auf
`algora.io` (Hiring-Homepage) = Board endgueltig weg; `algora.io/bounties` -> 404.
`issuehunt.io/repos` -> 404 (altes OSS-Funding-Board tot), `/programs` = VDP.
Beide Plattformen sind seither reine Recruiting-/Security-Anbieter -> nicht mehr
als Bounty-Quelle anlaufen.

## 4. gh Pitfall: Issue-/PR-View-Format

`gh issue view rodrigompy/bugb#1` -> **`invalid issue format`**. Richtig ist
Nummer + Repo-Flag:

```bash
gh issue view 1 -R rodrigompy/bugb --json state,title,body
gh pr view 32 --repo openamer/openamer --json state,mergedAt,title
```

Der `owner/repo#n`-Kurzstring funktioniert nur bei `gh search`, nicht bei
`gh issue view` / `gh pr view`.

## 5. Cloudflare-gated Auth = UNVERIFIED, nicht "kein Account"

`curl -I https://hackerone.com/users/sign_in` -> 403; im echten Browser zeigt die
Seite "Sicherheitsueberpruefung wird durchgefuehrt" (Ray ID). Die Marketing-Seite
(`www.hackerone.com`) mit Menue-Punkt "Login" beweist NUR, dass dort kein
Marketing-Konto haengt — der **Platform**-Konto-Status bleibt ungemessen.
Solche Faelle als "UNGEMESSEN + Signup-URL fuer Damir" melden, nie als
"kein Account" (und nie Credentials erfinden).

## 6. Screenshot-Evidenz sauber sichern

`browser_vision` legt das PNG unter
`cache/screenshots/browser_screenshot_<hash>.png` ab. Fund + Kopie in den
Evidenz-Ordner:

```bash
find "C:/Users/damir/AppData/Local/openamer-laptop/cache" -name "*.png" \
     -newermt "-10 minutes" | head -5
cp <gefundene>.png "C:/Users/damir/AppData/Local/openamer-laptop/memory/si/ev_mp_<YYYYMMDD>_<thema>.png"
```

Dann den Pfad als eigene JSONL-Zeile (`action="<thema>_evidence"`) loggen. Ein
reiner DOM-Text-Beweis ist stark, aber das PNG ist der schnell pruefbare Beleg.

## 7. JSONL-Append-Hygiene (Wiederholung)

`memory/si/monetization_pipeline_log.jsonl` enthaelt Alt-Zeilen mit variierendem
Schema — nie die GANZE Datei gegen ein festes Keyset validieren, nur die selbst
angehaengten Zeilen (`L[-N:]`). Append ASCII-sicher mit `ensure_ascii=True`
schreiben (Windows/Mojibake), `open(..., newline="\n")`.
