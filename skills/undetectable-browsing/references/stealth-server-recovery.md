# Stealth Browser — Fehlerbehebung aus Cron-Session

## Symptom: Server startet nicht, Lock existiert nicht

```
❌ Start fehlgeschlagen. Log: .../stealth/server.log
```

**Die Lock-Datei (`browser.lock`) muss vorhanden sein** — ohne Lock ist kein WS-Endpunkt verfügbar.

## Bekannte Fehler + Fixes

### 1. `--user-data-dir` bei `launch()` (Playwright API Change)

**Fehler:**
```
browserType.launch: Pass userDataDir parameter to
'browserType.launchPersistentContext(userDataDir, options)'
instead of specifying '--user-data-dir' argument
```

**Fix:** `--user-data-dir` aus `chromium.launch({args:[...]})` entfernen. Das Flag gehört nur zu `launchPersistentContext()`.

### 2. `browser.process()` removed in Playwright ≥1.60

**Fehler:**
```
browser.process is not a function
TypeError: browser.process is not a function
```

**Ursache:** In Playwright ≥1.60 wurde `browser.process()` **komplett entfernt** — es existiert kein Ersatz. Der Aufruf crasht sofort, try/catch hilft nicht.

**Fix:** `browserPid = null` setzen und nicht mehr aufrufen:
```js
const browserPid = null; // Playwright ≥1.60 removed browser.process()
```

**Alte (kaputte) Version:**
```js
// Führt sofort zu TypeError, wird nicht von catch abgefangen:
let browserPid = null;
try { browserPid = browser.process()?.pid; } catch(e) {} // ❌
```

### 3. `cmd //c start` funktioniert nicht unter MSYS/git-bash

**Fehler:** Der `openamer-stealth.sh` startete den node-Prozess via `cmd //c start /B /MIN "" node ...` — der node-Prozess startete im MSYS-Kontext nicht korrekt, die Lock-Datei blieb leer.

**Fix:** `nohup node server.mjs > "$LOG" 2>&1 &` statt `cmd //c start`.

### 4. Stale Lock-Datei

**Symptom:** Lock existiert, aber die PID ist tot. Der Start-Check sieht die Datei und nimmt an der Server läuft.

**Fix:** Prüfe mit `kill -0 "$PID" 2>/dev/null || rm -f "$LOCK"` ob die PID noch lebt.

**Achtung:** Unter MSYS/git-bash gibt `kill -0` auch für **lebende** Windows-native Node-Prozesse false-negativ zurück ("PROCESS DEAD"). Die zuverlässigere Verifikation ist `curl http://127.0.0.1:9222/json/version` (siehe Punkt 5).

### 5. Verification nach Start

**Start gelungen?** Ausgabe zeigt:
```
✅ Stealth Browser gestartet
🔗 ws://127.0.0.1:9222/devtools/browser/...
```

**Health-Check (zuverlässig — auch wenn `kill -0` false-negativ ist):**
```bash
curl http://127.0.0.1:9222/json/version
# → {"Browser": "Chrome/151.0.7922.34", "webSocketDebuggerUrl": "ws://...", ...}
curl http://127.0.0.1:9222/json/list
# → [{"title":"about:blank","url":"about:blank",...}]
```

Wenn `curl` ein JSON-Objekt mit `webSocketDebuggerUrl` zurückgibt, läuft der
Server — unabhängig davon, was `kill -0` meldet.

### 6. Zombie Node-Prozesse aus alten Starts

**Symptom:** Nach mehreren `openamer-stealth.sh start`/`restart`-Aufrufen
sammeln sich alte Node-Prozesse an (`ps aux` zeigt mehrere Node-Instanzen).
Das Skript killt nur `chrome-headless-shell.exe`, nicht die Node-Prozesse aus
vorherigen Starts.

**Cleanup vor Neustart (PowerShell):**
```powershell
powershell "Get-CimInstance Win32_Process -Filter 'CommandLine like \"%stealth-server%\"' | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"
```

**Oder im Skript (pkill via MSYS):**
```bash
pkill -f "stealth-server.mjs" 2>/dev/null || true
```

### 7. Lock-PID ist die Node-PID, nicht die Chrome-PID (korrigiert)

`stealth-server.mjs` speichert `process.pid` (die **Node.js** PID) in der
Lock-Datei, nicht die Chrome PID. `browserPid` wird explizit auf `null`
gesetzt, weil Playwright ≥1.60 `browser.process()` entfernt hat.

Wenn der Node-Prozess stirbt, läuft Chrome (HeadlessShell) oft weiter auf
Port 9222 — die Lock-Datei zeigt dann auf eine tote PID während der Browser
noch antwortet. Verlass dich auf `curl`-Health-Checks, nicht auf PID-Prüfungen.

## Wiedergabe

```bash
cd /c/Users/damir/AppData/Local/openamer-laptop/scripts
npm install playwright   # Einmalig
node stealth-server.mjs
# In SEPARATEM Terminal nach 5s prüfen:
cat /c/Users/damir/AppData/Local/openamer-laptop/stealth/browser.lock
curl http://127.0.0.1:9222/json/version
```