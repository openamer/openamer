# GitHub-native Sales Funnel — autonomer Vertriebsweg ohne externe Plattformen

Verifiziert 2026-10-02 (alle Befehle aus echtem Session-Output, alle URLs HTTP 200).

## Der Funnel

```
GitHub Topic-Search / Explore → Repo (gepinntes Shop-Issue oben)
  → README Buy-CTA (erster Bildschirm, kein Scrollen nötig)
  → PRODUCTS.md / Shop-Website (GitHub Pages)
  → PayPal NCP-Checkout → Geld beim Seller (instant, keine Freigabe)
```

## Schritt-für-Schritt

### 1. Topics auf Kauf-Keywords setzen (20-Slot-Limit: austauschen, nicht adden)

```bash
gh api repos/<owner>/<repo> --method PUT -f "names[]=agent" -f "names[]=bug-triage" \
  -f "names[]=security-scanning" -f "names[]=static-analysis" ... # komplette Liste nötig
# Verify:
gh api repos/<owner>/<repo> --jq .topics
```
Kauf-Keywords: `bug-triage`, `security-scanning`, `static-analysis`. Opfer-Kandidaten:
Nischentopics ohne Suchvolumen (z.B. `voice-assistant`, `vector-memory`).

### 2. README Buy-CTA in den ersten Bildschirm

Shop-Sektion weit unten (z.B. Zeile 648) wird ohne Scroll nie gesehen. Direkt
nach der Tagline (Zeile ~9) einfügen:

```markdown
> 🛒 **[Produktname — $29 one-time](PRODUCTS.md)** · Feature A, Feature B,
> Feature C. 👉 **[Buy now](https://www.paypal.com/ncp/payment/<ID>)**
```

Commit + Push + Verify: `git ls-remote origin main` == lokaler HEAD.

### 3. Shop-Website via GitHub Pages (docs/ Falle!)

GitHub Pages mit Source=branch main, path=/docs serviert Dateien unter /docs
AT ROOT — die öffentliche URL von `docs/shop/index.html` ist
`https://<owner>.github.io/<repo>/shop/index.html` (NICHT `/docs/shop/...`).

```bash
# Pages-Status prüfen (source zeigt auf main /docs):
gh api repos/<owner>/<repo> pages --jq '.source'
# Nach erstem Pages-Build kann der neue Pfad 404 liefern — Rebuild abwarten
# (einige Minuten), dann:
curl -s -o /dev/null -w "%{http_code}" https://<owner>.github.io/<repo>/shop/index.html  # → 200
# Repo-Homepage auf die Shop-URL setzen:
gh api repos/<owner>/<repo> --method PATCH -f homepage="<shop-url>" --jq .homepage
```

### 4. Announcement-Discussion (GraphQL — inline-JSON scheitert, Datei-Variablen-Method)

Inline-Mutation mit中文/Emoji-Body schlägt fehl ("Expected NAME"). Sauberer Weg:
Mutation in eine .graphql-Datei schreiben mit $title/$body-Variablen, dann
`gh api graphql -f query=@discussion.graphql -f title=... -f body=...` (subprocess,
Args als Listen — keine Shell-Quoting-Probleme).

Repository-ID und Category-IDs vorher holen:
```bash
gh api graphql -f query='query{repository(owner:"x",name:"y"){id discussionCategories(first:5){nodes{id name}}}}'
```
Announcements-Category für Produkt-Releases verwenden.

### 5. Release mit Produkt-ZIP als Asset (Download-Kanal)

```bash
gh release create product-<name>-v1 --title "🛒 <Name> v1.0 ($X)" --notes "<kauf-links>"
gh release upload product-<name>-v1 <pfad>/produkt.zip
# Verify: gh release view --json assets --jq '.assets[] | {name, size, downloadCount}'
```

### 6. Shop-Issue pinnen (Discussions haben KEINE pin-API!)

`pinDiscussion` existiert nicht in der GraphQL-Mutation-Schema. Stattdessen:

```bash
gh issue create --title "SHOP: <Produkt> - X USD (PayPal instant checkout)" --body "<alle Links>"
gh api graphql -f query='query{repository(owner:"x",name:"y"){issue(number:110){id}}}'  # Issue-ID holen
gh api graphql -f query='mutation{pinIssue(input:{issueId:"<ID>"}){issue{id}}}'
gh api graphql -f query='query{repository(owner:"x",name:"y"){pinnedIssues(first:3){nodes{issue{title}}}}}'  # verify
```

**Falle:** `$29` im Issue-Titel wird beim Pinnen zu `9` gerendert (Markdown-fett-
Parsing frisst das `$`). Titel mit `29 USD` statt `$29` schreiben.

## Echte Verfügbarkeits-Matrix der Vertriebskanäle (2026-10-02)

| Kanal | autonom? | Befund |
|---|---|---|
| GitHub (Topics/README/Pages/Discussions/Releases/Pins) | ✅ voll | der stärkste Kanal, alles kontrolliert |
| PayPal NCP-Button | ✅ (Link einbetten) | Käufer zahlt instant an Seller |
| PayPal.me | ✅ (Link einbetten) | Trinkgelder |
| Gumroad Publish | ⚠️ blocked bis User Payout-Methode verbindet | Produkt anlegen/upload/price = autonom |
| Hacker News | ⚠️ Session nötig + Rate-Limit (`fnop=story-toofast`) | Retry nur nach Abkühlfrist |
| dev.to / Product Hunt | ❌ ausgeloggt, Credentials nicht vorhanden | nie fremde Credentials nutzen |
| Ko-fi | ❌ Cloudflare 403 für Bot-Zugriff | nur als manuellen Link in Ship-Artefakten |
| Telegram/Discord/Reddit | nur wenn Session existiert | Login-Status via CDP :9222 prüfen, nie Accounts erfinden |

## Selbst-Verifikation pro Kanal (Pflicht vor "live"-Behauptung)

```bash
curl -s -o /dev/null -w "%{http_code}" "<kanal-url>" --max-time 20   # → 200
```
Alles in `memory/si/bounty_pipeline_log.jsonl` loggen (ts, action, result).

## Verboten

- Self-buying (selbst auf eigenen PayPal-Button klicken und zahlen) — ToS-Verletzung
- Fake-Käufe, Spam-Posts, Accounts mit erfundenen Credentials
- "'X ist kaputt'-Claims": Ko-fi 403 ist Cloudflare-Status, kein Feature-Verbot — manuelle Links bleiben valide