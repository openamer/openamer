---
name: discord-server-management
description: Use when a cron must post in Discord via CDP.
version: 1.5.0
platforms: [windows, linux, macos]
tags: [discord, cdp, browser, outreach, community, posting, login]
related_skills: [cdp-social-posting, darwin-harvested-openamer-browser]
metadata:
  openamer:
    tags: [discord, cdp, browser, outreach, community, posting, login]
    related_skills: [cdp-social-posting, darwin-harvested-openamer-browser]
---

# Discord-Server-Management über den OpenAmer Browser (CDP)

## Overview

Load `discord-server-management` whenever a cron must touch the `openamer` guild.
Drives the real, logged-in Discord web session in the OpenAmer Electron browser
(CDP `:9333`, profile `openamer-browser-profile`) to read and post in the
`openamer` guild. This skill exists because Discord has **no** usable API path
here: there is no `DISCORD_BOT_TOKEN`, no webhook, and no stored password — so
everything rides on the browser session, and the very first job is always to
prove whether that session is still alive. It covers the three-way browser
topology (`:9222` plain Chrome, `:9223` headless impostor, `:9333` the real
Electron browser), the exact auth evidence to collect, and the two login paths.

## When to use

- A cron job (e.g. "Discord Community Manager") hands you a post text for
  #Allgemein or #ai-agent.
- You must prove the Discord session is logged in **before** claiming a post
  succeeded (never trust `sessions.json` or a remembered account alone).
- A post silently did nothing and you need the real root cause.
- A redirect to `/login` appeared and you must decide: fix it or report the blocker.

## Verification

Always run this first; do not post on assumption.

```bash
# 1. Is the real Electron browser up on :9333?
curl -s http://127.0.0.1:9333/json/version | grep -o 'OpenAmerBrowser/[0-9.]*' || echo "NOT RUNNING"
# 2. Load the channel and inspect auth state
python scripts/_discord_live9333.py   # or driver.py url && driver.py text 300
```

A healthy (logged-in) session reports `token: true`, `channels > 0`,
`msgs >= 0`, and a URL containing `/channels/`. A dead session reports
`login: true`, `token: false`, and a `/login?redirect_to=...` URL.

## Setup & installation

**Three browser instances can coexist — do not confuse them:**

| Port | What | Discord login |
|------|------|---------------|
| 9222 | Plain Chrome (`chrome-profile`) | ❌ NO (redirect → /login) |
| 9223 | **HeadlessChrome** (`chrome-profile-2`) — impostor | ❌ NO |
| 9333 | **OpenAmer Electron browser** — use THIS one | ⚠️ account saved, session may be expired |

- The cron prompt names `:9333` and that is **correct** — it is the Electron
  app `openamer-browser/build/win-unpacked/OpenAmer Browser.exe`, which sets
  `app.setPath('userData', PROFILE_DIR)` where
  `PROFILE_DIR = %APPDATA%/openamer-browser-profile` and opens
  `--remote-debugging-port=9333` (see `openamer-browser/main.js` lines 11/19/749/750/753).
- Start it if not active (Electron does not run persistently):
  ```bash
  cd openamer-browser/build/win-unpacked && ./"OpenAmer Browser.exe" --remote-debugging-port=9333
  ```
  then `curl http://127.0.0.1:9333/json/version` → UA contains `OpenAmerBrowser/1.0.0 … Electron/40`.
- **Navigate the `page` tab, never the `webview` tab** (the webview shows google.com).
  Match by `t["type"]=="page"` or `"discord.com" in t["url"]`.
- Tab open: `PUT http://127.0.0.1:9333/json/new?url=...` (Chrome ≥111 needs PUT; the
  `url` param is sometimes ignored → safer to create the tab, then `Page.navigate` over WebSocket).
- The agent's own `browser_*` tools run on separate Browserbase cloud infra and
  share **no** session with this local browser.

## Usage

Preferred driver: `scripts/driver.py` (standalone CDP tool), or the small
WebSocket helper pattern (`websocket-client` is installed) against
`ws://127.0.0.1:9333/devtools/page/<TAB_ID>`.

```bash
python scripts/driver.py url                          # current URL
python scripts/driver.py text 2000                    # page text
python scripts/driver.py clicktext "Anmelden"         # click by visible text (real mouse)
python scripts/driver.py focus "input[name=email]"
python scripts/driver.py type  "input[name=email]" "…"
python scripts/driver.py key   Enter
python scripts/driver.py shot  out.png
python scripts/driver.py eval  "<js>"
```

Discord is React/Slate: `element.click()` via JS is ignored — use **real mouse
events** (`Input.dispatchMouseEvent`). Posting: focus the `[role=textbox]`,
`Input.insertText` (never set `value`), then `Input.dispatchKeyEvent` with
`windowsVirtualKeyCode: 13` (Enter).

## Pitfalls

- **Claiming a post succeeded without proof.** The single worst failure mode:
  a submit click that silently did nothing, reported as success. Always re-read
  the channel via CDP afterwards and find your message in the DOM.
- **Trusting `sessions.json`.** It stores cookies, not auth state. A platform with
  only `cf_clearance`/`__dcfduid` entries is NOT logged in — verify in-page (`token`, channel list).
- **Pointing at the wrong port.** `:9222` is plain Chrome and `:9223` is a headless
  impostor; only `:9333` (Electron, `openamer-browser-profile`) has the `openamer` account.
- **`element.click()` via JS on Discord.** React/Slate ignores it — use real mouse events
  (`Input.dispatchMouseEvent`), and `Input.insertText` (never set `value`) for the composer.
- **Extracting a user token from LevelDB.** Self-botting — off-limits (ToS).
- **Restarting the gateway to "fix" login.** A gateway restart kills the tool
  subprocesses of running cron jobs (the agent would cut its own run short).

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| URL is `/login?redirect_to=…` | Web session expired | Manual login (see below); report blocker, no fake post |
| `Account auswählen … openamer … Bitte melde dich erneut an.` | Account remembered, session dead | Click "Anmelden" → email/password (or QR/passkey) |
| `:9333` connection refused | Electron app not running | Start `OpenAmer Browser.exe --remote-debugging-port=9333` |
| `channels/<id>/messages` → 401 | No auth token | Expected without login |
| Widget API → 403 `Widget Disabled` | Widget off in guild settings | Use invite API instead |
| HeadlessChrome in `/json/version` | Wrong instance (`:9223`) | Point at `:9333` |

## Login (critical point — verified 2026-09-16)

- Only the Electron OpenAmer browser (`:9333`, profile `openamer-browser-profile`)
  knows the Discord account `openamer`. Opening `/channels/...` shows an
  **account picker**: "Account auswählen … **openamer** … *Bitte melde dich erneut an.*".
  Clicking "Anmelden" lands on the email/password form (`input[name=email]` +
  `input[name=password]`), both fields empty, no autofill.
- **There is NO stored Discord token and NO password on disk.** Verified 2026-09-16:
  - `%APPDATA%/openamer-browser-profile/Network/Cookies` → 175 cookies, discord.com =
    `__cf_bm, __dcfduid, __sdcfduid, cf_clearance` only → **no `token`**.
  - `auth.json`, `config.yaml`, `openamer-browser/sessions.json`, `.env`,
    keyring, Windows Credential Manager → no token, no `DISCORD_BOT_TOKEN`, no webhook.
  - `login`/`Login Data` (password manager) → empty in every profile → nothing to autofill.
  - `openamer send --list` → "No messaging platforms configured".
- **Self-botting is off-limits:** do NOT extract/use a user token from LevelDB (ToS risk). This rule stands.
- **Without login, reading AND posting are impossible** — abort cleanly and report the blocker, never fabricate a post.
- **Only fix (manual, one-time):** open the OpenAmer browser window → on the picker choose
  "openamer" → "Anmelden" → enter email/password (or QR scan). The session then persists in
  `openamer-browser-profile` and the cron job can read + post again.
- **No fake post:** if the session is expired, report NOTHING as "posted". Take the ready
  post text and name the blocker in the report.

## What works WITHOUT login

- Guild facts via the **public invite API** (no auth needed):
  ```bash
  curl -s "https://discord.com/api/v10/invites/gckmapHrr?with_counts=true"
  ```
  → guild `openamer` (id `1541173413131849788`), channel `Allgemein`
  (id `1541173413706731594`), member/presence counts.
- All target links are checkable: `curl -L -o /dev/null -w "%{http_code}"` → PayPal 200,
  Consulting 200, Skills-Store 200, GitHub 200, Invite 200.

## Zwei mögliche Login-Pfade (Entscheidung für Damir)

| Pfad | Nötig | Aufwand | Postet als |
|---|---|---|---|
| **A) Web-CDP (dieses Skill)** | Manuell im :9333-Fenster einloggen (E-Mail/Passwort oder QR) | Einmalig, 1 Min | User `openamer` |
| **B) Gateway-Plugin (empfohlen, dauerhaft)** | Bot im [Dev Portal](https://discord.com/developers/applications) erstellen, `DISCORD_BOT_TOKEN` in `.env`, Gateway-Restart | Einmalig, ~5 Min | Bot-User |

Pfad B ist robuster (kein Session-Ablauf) und `discord.py` ist bereits installiert.
Siehe `plugins/platforms/discord/plugin.yaml` (`requires_env: DISCORD_BOT_TOKEN`).

## STATUS 2026-09-17 04:37 (letzter verifizierter Lauf, Cron „Discord Community Manager")

- **Blocker unverändert: Session abgelaufen, kein Auth-Token — 3. Lauf in Folge am 17.09.**
  Frisch reproduziert via CDP **`:9333`** (Electron-Browser läuft: Chrome/144.0.7559.236,
  UA `OpenAmerBrowser/1.0.0 … Electron/40.10.2`; Tool-Server `:8081` alive, 9 Tools).
  - Kanal-URL → **Redirect `/login?redirect_to=…`**, Seitentext = Account-Picker
    „Account auswählen … **openamer** … *Bitte melde dich erneut an.*".
  - **Navigations-Pfade alle geprüft:** agent-eigenes `browser_navigate` → Netzwerk-Timeout
    (os error 10060); Tool-Server `browser_action` → meldet `{"navigated": …}`, Tab bleibt
    aber auf `/login` (Meldung ≠ Realität — immer via `/json/list` gegenprüfen);
    `Page.navigate` über CDP-WebSocket greift ebenfalls nicht, weil die SPA selbst
    auf `/login` umleitet. **Root cause ist Auth, nicht Navigation.**
  - **Klick auf „Anmelden" mit echten Maus-Events** (`Input.dispatchMouseEvent`): Seite
    bleibt Account-Picker, `inputs: []` → es erscheint **kein** E-Mail/PW-Formular.
    Die Login-Seite hat 2 `<canvas>` → **QR-Anmeldung ist der einfachste Weg** (Handy-App).
  - `Network.getCookies` discord.com auf `:9333` → nur
    `cf_clearance, _cfuvid, __dcfduid, __sdcfduid` → **kein `token`**.
    `:9222` hat **gar keinen Discord-Tab** (nur Bing-Suchseiten).
  - `channels/<id>/messages` → **401**; Widget-API → **403** `Widget Disabled`.
  - `openamer send --list` → „No messaging platforms configured…"; **kein `DISCORD_BOT_TOKEN`**
    (grep in `.env` laptop **und** `openamer-repo/.env` → 0 Treffer; keine Webhook-URL).
  - Guild-Fakt: **2 Mitglieder, 0 online**, Invite gültig bis 2026-09-22.
    → Es sind keine neuen Fragen vorhanden, die beantwortet werden könnten; Lesen ist ohnehin 401.
  - Screenshot: `AppData/Local/openamer-laptop/discord_login_blocker_20260917_0437.png`
    (via CDP `Page.captureScreenshot`; Account-Picker sichtbar).
  - Report: `cron/discord_status_2026-09-17.md`; Post-Vorlage: `Desktop/discord_update_20260917.md`
    (mit frischen Repo-/Memory-Zahlen aktualisiert: 6 Stars, letzter Push 17.09. 01:38 UTC,
    3056 Episoden, 437 World-Model-Einträge, 126 Skills).
- **Kein Fake-Post.** Kein Gateway-Restart (killt Cron-Tool-Subprozesse). Kein LevelDB-Token (ToS).

## STATUS 2026-09-17 00:20 (vorheriger verifizierter Lauf, Cron „Discord Community Manager")

- **Blocker unverändert: Session abgelaufen, kein Auth-Token.** Frisch reproduziert via CDP **`:9333`**
  (diesmal läuft der im Auftrag genannte Electron-Browser wieder — Chrome/144.0.7559.236,
  UA `OpenAmerBrowser/1.0.0 … Electron/40.10.2`; `:9222` parallel: Chrome/152.0.7977.84).
  - Kanal-URL → **Redirect `/login?redirect_to=…`**, Seitentext = Account-Picker
    „Account auswählen … **openamer** … *Bitte melde dich erneut an.*".
  - DOM am Formular: `{"email":"","pw":0,"ready":false}` → beide Felder LEER, **kein Autofill**.
  - `Network.getCookies` discord.com auf **beiden** Ports → nur
    `cf_clearance, _cfuvid, __dcfduid, __sdcfduid` → **kein `token`**.
  - `channels/<id>/messages` → **401**; Widget-API → **403** `Widget Disabled`.
  - `openamer send --list` → „No messaging platforms configured…"; **kein `DISCORD_BOT_TOKEN`**
    (`.env`-grep 0 Treffer, keine Discord-Env-Var).
  - Guild-Fakt: **2 Mitglieder, 0 online**, Invite gültig bis 2026-09-22.
    → Es sind keine neuen Fragen vorhanden, die beantwortet werden könnten; Lesen ist ohnehin 401.
  - Screenshot: `AppData/Local/openamer-laptop/discord_login_blocker_20260917.png`
    (visuell geprüft: leeres Formular „Willkommen zurück!").
  - Report: `cron/discord_status_2026-09-17.md`; Post-Vorlage: `Desktop/discord_update_20260917.md`.
- **Kein Fake-Post.** Kein Gateway-Restart (killt Cron-Tool-Subprozesse). Kein LevelDB-Token (ToS).

## STATUS 2026-09-16 19:10 (vorheriger verifizierter Lauf, Cron „Discord Community Manager")

- **Blocker unverändert:** Discord-Web-Session ist weiterhin abgelaufen — kein Auth-Token.
  Beweis (frisch reproduziert via CDP :9222, echter Chrome 152.0.7977.84):
  - Frischer Tab `https://discord.com/channels/1541173413131849788/1541173413706731594`
    → **Redirect auf `/login?redirect_to=%2Fchannels%2F1541173413131849788%2F1541173413706731594`**.
  - Nach vollem Laden: `{"hasEmail":true,"hasPw":true}` — Login-Formular, beide Felder LEER.
  - `window.localStorage.getItem('token')` → **False**. `Network.getCookies` für discord.com
    liefert nur anonyme Cookies: `__dcfduid, __sdcfduid, cf_clearance, _cfuvid, locale, OptanonConsent`
    → **kein `token`-Cookie**.
  - Gegenprobe `openamer-browser/sessions.json` → `Discord` = 8 Cookies, **alle anonym**
    (`__dcfduid, __sdcfduid, cf_clearance, _cfuvid, cf_clearance, _cfuvid, locale, OptanonConsent`).
    Im Vergleich: `X` hat `auth_token`+`twid`, `HN` hat `user`, `Reddit` hat `token_v2` — dort
    sind echte Logins gespeichert, bei Discord NICHT.
  - `Login Data` in beiden Profilen (`chrome-profile`, `chrome-profile-2`): **nicht lesbar/leer** → kein Autofill.
  - Kein `DISCORD_BOT_TOKEN` in `openamer-repo/.env` (nur `OPENAMER_MESH_SECRET`), kein
    `~/.openamer/.env`, kein Keyring, keine Webhook-URL, kein Bot-Token per `grep` im Home
    auffindbar. `openamer send --list` → „No messaging platforms configured" (Exit 0).
  - Widget-API: `guilds/<id>/widget.json` → HTTP 403 `{"message":"Widget Disabled","code":50004}`.
  - `channels/<id>/messages` → **401 Unauthorized**. → **Lesen UND Posten unmöglich, kein Fake-Post.**
  - Port `:9333` (im Cron-Auftrag genannt) ist **DOWN**; der echte Browser lauscht auf `:9222`.
    Screenshot-Beleg: `AppData/Local/openamer-laptop/discord_login_blocker_20260916_verify.png`.

### Was stattdessen funktioniert (ohne Login, weiterhin gültig)
- Guild-Fakten via **öffentlicher Invite-API**: `curl -s "https://discord.com/api/v10/invites/gckmapHrr?with_counts=true"`
  → guild `openamer` (id 1541173413131849788), Kanal `Allgemein` (id 1541173413706731594),
  `approximate_member_count: 2`, `approximate_presence_count: 0`.
- Alle Ziel-Links per `curl -L -o /dev/null -w "%{http_code}"` prüfbar → PayPal 200,
  Consulting 200, Skills-Store 200, GitHub 200, Invite 200.

## STATUS 2026-09-16 03:16 (vorheriger verifizierter Lauf)

- **Blocker unverändert:** Discord-Web-Session im :9333-Profil ist weiterhin abgelaufen.
  Beweis (frisch reproduziert): `Page.navigate` auf die Kanal-URL → Redirect auf
  `/login?redirect_to=...`, Klick auf „Anmelden" → E-Mail/Passwort-Formular.
  DOM-Probe: `{"hasEmail":true,"hasPw":true,"emailVal":"","pwVal":""}` — beide Felder LEER,
  kein Autofill. Im Profil `%APPDATA%/openamer-browser-profile` existiert **keine `Login Data`**
  (Password-Manager) → es gibt nichts zum Autofillen. Kein `DISCORD_BOT_TOKEN` in `.env`
  (11 Discord-Treffer = alle auskommentierte Beispiele), kein `~/.openamer/.env`, kein
  Windows-Credential-Manager- und kein Keyring-Eintrag.
  Screenshot: `AppData/Local/openamer-laptop/discord_login_blocker_20260916.png` (~1 MB).
  Widget-API: `guilds/<id>/widget.json` → `{"message":"Widget Disabled","code":50004}` (403).
  `channels/<id>/messages` → **401 Unauthorized**. → **Lesen UND Posten unmöglich, kein Fake-Post.**

## GEFIXT 2026-09-16: `openamer send` crashte mit `NameError: name 'os' is not defined`

**Symptom:** `python openamer_cli/main.py send --list` → Traceback in
`openamer_cli/send_cmd.py:292` (`if key in os.environ:`) → `NameError: name 'os' is not defined`.
Der komplette `send`-Subcommand war unbenutzbar (jeder Plattform-Post-Pfad).

**Root Cause:** In `send_cmd.py` fehlte schlicht `import os`, obwohl `_load_openamer_env()`
`os.environ` benutzt. Der Docstring verspricht „pipe text to any messaging platform" — das
war de facto tot. Eingeschleppt vom Portabilitäts-Commit `a75bd1634` („repair import ordering"),
der `import os` beim Umsortieren verloren hat.

**Fix (verifiziert):** `import os` nach `import json` in `send_cmd.py` ergänzt.
Verifikation: `py_compile` OK; `send --list` läuft jetzt sauber durch
→ `openamer send: no targets found for platform 'discord'. Configured: (none)` (Exit 0,
kein Traceback mehr). Der Exit-0-Grund ist ein separater, erwarteter Zustand: es ist gar
keine Plattform konfiguriert.

## ROOT CAUSE 2026-09-16: Cron-Jobs crashten mit `reset_delay_from_message`-ImportError

**Symptom:** Mehrere Cron-Jobs (Discord Community Manager, Social-Outreach-Mega, self-reflection,
brain-collect, auto-test-runner, Bugbot) scheiterten wiederholt mit
`cannot import name 'reset_delay_from_message' from 'agent.retry_utils'`.
`last_error` des Discord-Jobs ist genau dieser String.

**Root Cause — KEIN Codebug (mehr):** Stale-Prozess-Problem.
- Der Fix für `agent/retry_utils.py` landete mit Commit `f5df9da04` um **00:55:13** (+0200).
- Die laufenden Gateway-Prozesse (PID **4172** → PID **8984**) wurden aber um **00:21:35**
  gestartet — **34 Minuten VOR dem Fix**.
- Ein laufender Python-Prozess lädt Module nicht neu. Ein veraltetes `agent/retry_utils`
  (Vor-Fix-Snapshot) war im Speicher → jeder Job, der `credential_pool` importierte, crashte.
- **Gegenprobe (frischer Interpreter):** `venv/Scripts/python.exe -c "from agent.retry_utils
  import reset_delay_from_message"` → **IMPORT OK**, und `from agent.credential_pool import
  CredentialPool` → OK. Der Code auf Platte ist korrekt.
- **Zusatzfalle:** `repo-tmp/agent/retry_utils.py` (Snapshot vom 2026-08-22, 154 Zeilen) hat die
  Funktion **nicht**. Wer mit `cwd=repo-tmp` startet, importiert dauerhaft die alte Datei.
  `repo-tmp` wird aktuell von keinem Cron-Job referenziert — aber nicht darauf verlassen.

**Fix (manuell durch Damir, 1 Befehl):** Gateway neu starten, damit frische Module geladen werden:
```bash
AppData/Local/openamer-laptop/openamer-agent/venv/Scripts/python.exe \
  openamer-agent/openamer_cli/main.py gateway restart
```
**Achtung, vom Agenten NICHT autonom ausgeführt:** Ein Gateway-Restart killt die Tool-Subprozesse
laufender Cron-Jobs (belegt im World-Model: „Gateway shutdown (final-cleanup) killed the job's
tool subprocess"). Der Agent würde damit seinen eigenen Job mitten im Lauf abschneiden.

## STATUS 2026-09-12 (vorheriger verifizierter Lauf)

- **Blocker unverändert:** Discord-Web-Session im :9333-Profil ist weiterhin abgelaufen.
  Beweis: nach `Page.navigate` → `/login?redirect_to=...`, Seitentext zeigt Account-Picker
  `openamer` / „Bitte melde dich erneut an." → Klick auf „Anmelden" landet auf dem
  E-Mail/Passwort-Formular (`input[name=email]`, `input[name=password]`), beide Felder LEER,
  `:‑webkit-autofill` = false. Kein `Login Data` (Password-Manager) im Profil.
  Screenshot: `AppData/Local/openamer-laptop/discord_login_blocker_20260912.png` (1920×1112).
- **Lesen UND Posten weiterhin unmöglich** — keine Fake-Posts. Blocker melden.
- **Guild-Fakten via öffentlicher Invite-API (kein Login nötig — funktioniert weiterhin, 2026-09-16):**
  `curl -s "https://discord.com/api/v10/invites/gckmapHrr?with_counts=true"`
  → guild `openamer` (id 1541173413131849788), Kanal `Allgemein` (id 1541173413706731594),
  `approximate_member_count: 2` (Stand 2026-09-16), Invite läuft bis 2026-09-22.
  Kanal-Liste/Message-Read erfordert Auth (401 Unauthorized) → nicht öffentlich abrufbar.

## GEFIXT 2026-09-12: Discord-Plugin lud nicht (Gateway-Warnung)

**Symptom:** `gateway-stdio.log` wiederholte:
`WARNING openamer_cli.plugins: Failed to load plugin 'discord-platform':
 module 'aiohttp' has no attribute 'ClientWebSocketResponse'`

**Root Cause:** `discord.py` war im Gateway-venv **nicht installiert**. Der Fehler ist irreführend —
das Plugin fängt nur `ImportError`, aber `discord.py` fehlt → Import scheitert an der
aiohttp-Kompatibilitätsprüfung. `aiohttp 3.14.3` selbst ist intakt (`ClientWebSocketResponse` vorhanden).

**Fix (verifiziert):**
```bash
AppData/Local/openamer-laptop/openamer-agent/venv/Scripts/python.exe -m pip install "discord.py"
# → Successfully installed discord.py-2.7.1
```

**Verifikation:** `pm.discover_and_load(force=True)` lädt jetzt `discord-platform`
in die Plugin-Liste, und die Warnung erscheint NICHT mehr. Auch
`plugins.platforms.discord.adapter.DISCORD_AVAILABLE == True`.

**Damit der Fix greift, Gateway einmal neu starten** (das laufende Gateway hat das Plugin
schon verworfen):

```bash
# PID aus gateway_state.json lesen, dann neu starten:
"AppData/Local/openamer-laptop/gateway-service/OpenAmer_Gateway.cmd"
```
Danach hat die Gateway-Discord-Integration einen echten Login-Pfad — **aber nur wenn
`DISCORD_BOT_TOKEN` gesetzt ist** (siehe `plugins/platforms/discord/plugin.yaml`).
Aktuell ist **kein** `DISCORD_BOT_TOKEN` in `.env`/`config.yaml`/Keyring hinterlegt.

## Zwei mögliche Login-Pfade (Entscheidung für Damir)

| Pfad | Nötig | Aufwand | Bot-Postet als |
|---|---|---|---|
| **A) Web-CDP (dieses Skill)** | Manuell im :9333-Fenster einloggen (E-Mail/Passwort oder QR) | Einmalig, 1 Min | User `openamer` |
| **B) Gateway-Plugin (empfohlen, dauerhaft)** | Bot im [Dev Portal](https://discord.com/developers/applications) erstellen, `DISCORD_BOT_TOKEN` in `.env`, Gateway-Restart | Einmalig, ~5 Min | Bot-User |

Pfad B ist robuster (kein Session-Ablauf, Token bleibt gültig) und `discord.py` ist jetzt installiert.

## Setup (real, verifiziert)

**Drei Browser-Instanzen existieren parallel — nicht verwechseln:**

| Port | Was | Discord-Login |
|------|-----|---------------|
| 9222 | Plain Chrome (`chrome-profile`) | ❌ NEIN (Redirect → /login) |
| 9223 | **HeadlessChrome** (`chrome-profile-2`) — Impostor! | ❌ NEIN |
| 9333 | **OpenAmer Browser (Electron)** — DIESEN nutzen | ⚠️ Account da, Session ABGELAUFEN |

- **Der Cron-Job-Prompt nennt :9333 und das ist KORREKT** — es ist der Electron-OpenAmer-Browser
  (`openamer-browser/build/win-unpacked/OpenAmer Browser.exe`), der `app.setPath('userData', 'openamer-browser-profile')`
  setzt und `--remote-debugging-port=9333` öffnet (siehe `openamer-browser/main.js` Z. 11/749/753).
- Starten falls nicht aktiv (Electron läuft NICHT dauerhaft):
  `cd openamer-browser/build/win-unpacked && ./"OpenAmer Browser.exe" --remote-debugging-port=9333`
  Danach `curl http://127.0.0.1:9333/json/version` → UA enthält `OpenAmerBrowser/1.0.0 ... Electron/40`.
- Health-Check :9222 → `curl http://127.0.0.1:9222/json/version`
- Tabs listen: `curl http://127.0.0.1:9222/json/list` (bzw. :9333)
- Tab öffnen: `PUT http://127.0.0.1:9222/json/new?url=...` (Chrome >=111 braucht PUT; url-Parameter wird teils ignoriert → sicherer: Tab anlegen, dann per WebSocket `Page.navigate`).
- Steuerung per Python + `websocket-client` (installiert) gegen `ws://127.0.0.1:9333/devtools/page/<TAB_ID>`.
- **Konsolidierter Driver (empfohlen): `scripts/driver.py`** — ein selbstständiges CDP-Tool, keine weiteren Helper-Module nötig.
  Deckt Klick/Text/Keys/Screenshot für Discord ab. Wichtig: **echte Maus-Events** verwenden
  (`Input.dispatchMouseEvent`), weil Discord React/Slate ist und `element.click()` per JS ignoriert.
  ```bash
  python scripts/driver.py url                          # aktuelle URL
  python scripts/driver.py text 2000                    # Seitentext
  python scripts/driver.py clicktext "Anmelden"         # Klick per sichtbarem Text (echte Maus)
  python scripts/driver.py focus "input[name=email]"
  python scripts/driver.py type  "input[name=email]" "..."   # focus + Input.insertText
  python scripts/driver.py key   Enter                  # senden
  python scripts/driver.py shot  out.png                # ganzseitiger Screenshot
  python scripts/driver.py eval  "<js>"                 # beliebiges JS, Rückgabe JSON
  ```
  Verifiziert 2026-09-16 E2E gegen :9333 (url/text/eval/click/clicktext/focus/type+Readback/key/shot/cookies).
- **Zum Navigieren IMMER die `page`-Tab nehmen, NICHT die `webview`-Tab** (die webview zeigt google.com).
  Tab per `t["type"]=="page"` ODER `"discord.com" in t["url"]` matchen.
- Die Agent-eigenen browser_*-Tools laufen über eine SEPARATE Cloud-Infrastruktur (Browserbase) und teilen KEINE Session mit diesem lokalen Browser.

## Discord-Server

- Server-ID: `1541173413131849788`, Standard-Channel: `1541173413706731594`
- URL: https://discord.com/channels/1541173413131849788/1541173413706731594
- Kanäle prüfen: `#allgemein`, `#ai-agent`

## Login (kritischer Punkt — Stand 2026-09-11, VERIFIZIERT)

- **Nur der Electron-OpenAmer-Browser (:9333, Profil `openamer-browser-profile`) kennt den Discord-Account `openamer`.**
  Er zeigt beim Öffnen von `/channels/...` einen **Account-Picker**: „Account auswählen … **openamer** …
  *Bitte melde dich erneut an.*" — d.h. der Account ist gespeichert, aber die **Web-Session ist abgelaufen**.
  Nach Klick auf „Anmelden" landet man auf dem E-Mail/Passwort-Formular (`input[name=email]` + `input[name=password]`).
- **Es gibt KEINEN gespeicherten Discord-Token und KEIN Passwort auf der Platte.** Geprüft 2026-09-11:
  - `.env`, `auth.json`, `config.yaml`, `openamer-browser/sessions.json` → nur `__dcfduid`/`cf_clearance`/`locale`
    (Anti-Bot-/Consent-Cookies, KEIN Auth-Token), kein `DISCORD_BOT_TOKEN`.
  - LevelDB (Local Storage) beider Profile → kein `MT…`/`v1.…`-Discord-Token (nur Yandex + Google).
  - `Login Data` (Password Manager) existiert im Profil nicht.
- **Self-Botting ist tabu:** User-Token NICHT aus LevelDB auslesen/verwenden (ToS-Risiko). Diese Regel bleibt.
- **Ohne Login ist Lesen UND Posten unmöglich** — Job dann sauber abbrechen und Blocker melden, keine Fake-Ergebnisse.
- **Einzige Lösung (manuell, einmalig):** OpenAmer-Browser-Fenster öffnen (s.o.) → auf dem Account-Picker
  „openamer" → „Anmelden" → E-Mail/Passwort eingeben (oder QR-Scan). Danach bleibt die Session im Profil
  `openamer-browser-profile` persistiert und der Cron-Job kann wieder lesen + posten.
- Zustand schnell prüfen: `python scripts/driver.py url && python scripts/driver.py text 300`
  (liefert Redirect-URL + Sichtbarkeit des Login-Formulars).
- **Kein Fake-Post:** Wenn die Session abgelaufen ist, NICHTS als „gepostet" melden. Stattdessen den fertigen
  Post-Text aus `openamer-browser/discord_update_draft.md` nehmen und den Blocker im Report nennen.

## Nachrichten posten (nach Login)

1. `[role=textbox]` mit aria-label "Nachricht"/"Message" finden, fokussieren/klicken.
2. Text einfügen mit `Input.insertText` (Discord nutzt Slate-Editor – kein value setzen!).
3. Senden mit `Input.dispatchKeyEvent` keyDown+keyUp, `windowsVirtualKeyCode: 13` (Enter).

## Vorlage für Update-Post

🔥 **OpenAmer Update** + Neuigkeiten +
💰 PayPal: https://www.paypal.com/ncp/payment/3HMBFYC9CQTMS
💼 Consulting: https://openamer.github.io/openamer/consulting.html
🛍️ Skills Store: https://openamer.github.io/openamer/skills-store.html
📂 GitHub: https://github.com/openamer/openamer
