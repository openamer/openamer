# Ein localhost-Dashboard für andere Geräte nutzbar machen (live 30.10.2026)

Gilt für jeden selbstgebauten HTTP-Dienst auf diesem Host (`remote-web.py :8901`,
`dashboard :8899`, `snapshot :8898`, `webhook :8900`): erst *binden*, dann *durchlassen*,
dann *authentifizieren* — und am Ende jeden Schritt einzeln messen.

Der Fall: der Owner will „vom Handy aus mit dem Agenten reden". Der Dienst lief, `curl`
auf demselben PC antwortete 200 — vom Handy kam ein Timeout. Es waren drei getrennte
Ursachen, jede mit eigenem Beweis.

## 1. Binden — `0.0.0.0` ist Pflicht, aber nicht genug

```
Get-NetTCPConnection -LocalPort 8901 -State Listen   # 0.0.0.0:8901 = auf allen Interfaces
```

`127.0.0.1` erreicht kein anderes Gerät. Wenn der Dienst mit `--local` oder auf
`127.0.0.1` gestartet wurde, ist das die erste Ursache — nicht die Firewall.

## 2. Durchlassen — die Firewall matcht den PROGRAMMPFAD, nicht den Port

Windows-Firewall-Regeln sind pfadgebunden (`Get-NetFirewallApplicationFilter .Program`).
Auf diesem Host existiert `Profile=Public | Allow | Enabled=True` für
`…\uv\python\cpython-3.11.15-windows-x86_64-none\pythonw.exe`, **nicht** für das Ziel des
venv-Trampolins (`…cpython-3.11-windows-…\pythonw.exe`). Eine Suche nach `*python*` findet
die Regel und verdeckt genau diesen Unterschied.

```powershell
Get-NetConnectionProfile | Format-List InterfaceAlias,NetworkCategory   # Public blockt standardmäßig
$p = (Get-NetTCPConnection -LocalPort 8901 -State Listen).OwningProcess | Select -First 1
Get-Process -Id $p | Select Id,Path                                     # WELCHES Image lauscht wirklich
Get-NetFirewallApplicationFilter | Where Program -match 'python' | ForEach-Object {
  $r = $_ | Get-NetFirewallRule
  '{0} | Profile={1} | {2} | Enabled={3}' -f $_.Program, $r.Profile, $r.Action, $r.Enabled }
Get-NetFirewallProfile -Name Public | Select Enabled,DefaultInboundAction,AllowInboundRules
```

`DefaultInboundAction=NotConfigured` heißt „Standard = blocken", `AllowInboundRules=
NotConfigured` heißt „Regeln greifen" — zusammen: eine passende Allow-Regel gewinnt.

Fix ohne Admin: mit **genau dem Pfad** starten, für den die Regel existiert. Und denselben
`argv[0]` in `scripts/supervisor/organs.json` eintragen, sonst startet der Supervisor den
Dienst nach dem nächsten Boot wieder unter dem ungedeckten Interpreter.

`Get-NetFirewallPortFilter` braucht Admin („Zugriff verweigert") — nicht als Diagnoseschritt
einplanen. `IsInRole(Administrator)` vorher messen, statt eine Regel anzulegen und zu scheitern.

## 3. Authentifizieren — Token per Link, nicht per Tippen

Ein `prompt()` nach einem 20-Zeichen-Token ist am Handy unbenutzbar. Der Token darf in der
URL stehen, wenn die Seite ihn sofort übernimmt und wieder aus der Adresszeile entfernt:

```javascript
const fromUrl = new URLSearchParams(location.search).get('token');
if (fromUrl) { localStorage.setItem('authToken', fromUrl); history.replaceState(null, '', location.pathname); }
const token = localStorage.getItem('authToken');
if (token) opt.headers['Authorization'] = 'Bearer ' + token;
```

Aufruf: `http://<lan-ip>:8901/?token=<token>`. Der Token wird **pro Start** aus
`.remote-web/auth.txt` gelesen → nach einer Rotation den Dienst neu starten; `401` mit dem
alten und `200` mit dem neuen Token ist der Rotationsbeweis. Den Default-Token
(`openamer-remote-secret`) nie im LAN stehen lassen.

## 4. Kaltstart — ein leerer Cache sieht wie ein kaputter Dienst aus

`/api/status` bediente den Cache, den ein Refresh-Thread erst nach `SNAPSHOT_TTL` (60 s)
füllt. Ein Gerät, das direkt nach dem Start verbindet, bekam `{}` — für den Nutzer „System
kaputt", für den Agenten ein grüner 200. Fix: bei leerem Cache on demand bauen und den Cache
füllen.

```python
data = _snapshot_cache["data"]
if not data:                      # Kaltstart: nicht {} ausliefern
    data = collect_system_snapshot()
    _snapshot_cache.update(ts=time.time(), data=data)
```

Dieselbe Klasse wie „ein Probe, der nichts misst": 200 + leeres Objekt ist keine Aussage.

## 5. Verifikation, die zählt

Ein `--selftest`-Flag ist eine manuelle Prüfung, keine reviewbare Evidenz. Für Dienste, die
**außerhalb** des Repos liegen (`<home>/scripts/…`), gehören Tests neben das Skript
(`<home>/scripts/tests/test_<name>.py`) und starten den echten Server:

```python
port = _free_port()                                    # bind(("127.0.0.1", 0))
home = tmp_path_factory.mktemp("home"); (home/".remote-web").mkdir(parents=True)
(home/".remote-web"/"auth.txt").write_text(TOKEN)
proc = subprocess.Popen([sys.executable, str(SCRIPT), f"--port={port}"],
                        env={**os.environ, "OPENAMER_HOME": str(home), "PYTHONUTF8": "1"})
# bis /health == 200 pollen (20 s Budget), dann:
#   Dashboard ohne Auth 200 · Token-Handler im HTML · /api/status 401 ohne/leer/falsch
#   · 200 mit Token · /health ohne Auth · Kaltstart liefert kein leeres {}
yield base; proc.terminate()
```

Sieben Tests, ~5 s Laufzeit, und jeder deckt eine der vier Ursachen oben ab. Ohne diesen Lauf
ist eine Änderung an einem lokalen Dienst unbelegt — genau wie die Firewall-Kette: jede Stufe
einzeln gemessen, und der letzte Meter (kommt das fremde Gerät durch?) gehört dem Gerät, nicht
dem Agenten. Das sagen, nicht behaupten.

## 6. Eine Instanz, nicht zwei — sonst bedient mal die alte, mal die neue Fassung

**Der verführerische Fehlschluss:** „der Browser zeigt noch `[object Object]`, also ist mein Fix
nicht live" — während `curl` im selben Moment den neuen Text liefert. Beide haben recht, weil
**zwei Prozesse** auf demselben Port lauschen.

```powershell
# Beide Zahlen messen — eine allein beweist nichts
@(Get-NetTCPConnection -LocalPort 8901 -State Listen).Count          # → 1 (!)
Get-CimInstance Win32_Process |
  Where-Object { $_.CommandLine -like '*remote-web.py*' -and $_.Name -eq 'pythonw.exe' } |
  ForEach-Object { 'PID=' + $_.ProcessId + ' PPID=' + $_.ParentProcessId }
# → PID=13684 (Supervisor, 21:40)  PID=7028 (Kind von 13684)  PID=21196 (eigener Start, 21:59)
```

Die Ursache ist Pythons Default `allow_reuse_address = 1` → `SO_REUSEADDR`. Unter Windows darf
eine **zweite** Instanz denselben Port binden; wer die Verbindung bekommt, ist undefiniert. Ein
Supervisor-Start und ein manueller Start erzeugen genau diesen Zustand, ohne dass irgendwo ein
Fehler auftaucht.

```python
class _ExclusiveServer(ThreadingHTTPServer):
    allow_reuse_address = False     # zweiter Bind scheitert hörbar
    daemon_threads = True

try:
    server = _ExclusiveServer((bind, port), RemoteWebHandler)
except OSError as exc:
    print(f"[remote-web] Port {port} ist bereits belegt ({exc})", flush=True)
    return 1
...
if __name__ == "__main__":
    sys.exit(main())                # Exit-Code weiterreichen
```

Warum `ThreadingHTTPServer` dazugehört: `HTTPServer` ist **einthreadig**. Der Snapshot-Handler
ruft `subprocess` (uname/wmic) und liest 142 Cron-Jobs — in dieser Zeit steht `/health` still und
der Client läuft in seinen Timeout. Gemessen nach dem Wechsel: 8 parallele Anfragen in **0,02 s**,
8/8 `200`; vorher Timeouts. Regressionstest:

```python
threads = [threading.Thread(target=hit, args=(p,)) for p in ["/health", "/api/status"] * 4]
# alle 200, Gesamtzeit < 12 s
```

**Zweitstart-Test** (beweist die Exklusivität, nicht nur die Meldung): denselben Befehl ein
zweites Mal auf denselben Port starten und **`returncode != 0`** prüfen. Ohne `sys.exit(main())`
ist der Exit-Code `0` und ein Watchdog glaubt an einen erfolgreichen Start — der Test hat genau
das aufgedeckt (`assert 0 != 0`).

Kill-Reihenfolge beim Aufräumen: **alle** `pythonw` mit `<script>` in der Kommandozeile beenden
(nicht nur den Listener-PID), 2 s warten, `Count == 0` prüfen, **dann** genau eine Instanz
starten. Ein Supervisor mit `observe_only` startet die alte Fassung nach dem nächsten Takt
erneut — deshalb `argv[0]` in `scripts/supervisor/organs.json` mitpflegen.

## 7. Typen an der Grenze: das Objekt, das als `[object Object]` ankommt

`cron/jobs.json` speichert `schedule` als Objekt:

```json
{"kind": "interval", "minutes": 240, "display": "every 240m"}
```

Die API reichte es roh durch, das Template machte `'<td>' + j.schedule + '</td>'` → in **jeder**
Zeile `[object Object]`. Der Fix gehört in den Snapshot-Bauer, nicht ins Template:

```python
if isinstance(schedule, dict):
    schedule = (schedule.get("display") or schedule.get("expr")
                or schedule.get("cron") or schedule.get("kind") or "")
elif not isinstance(schedule, str):
    schedule = str(schedule)
```

Test: echte `cron/jobs.json` ins Wegwerf-Home schreiben (**vor** dem Serverstart — der Snapshot
wird gecacht, `SNAPSHOT_TTL` 60 s), dann `isinstance(job["schedule"], str)` und den erwarteten
Text prüfen. Nach dem Fix serverseitig belegen: `{type(x['schedule']).__name__ for x in jobs}` →
`{'str'}` über alle 142 Jobs, plus ein Screenshot der gerenderten Tabelle.

## 8. Verifikation, wenn die geänderten Dateien AUSSERHALB des Repos liegen

`<home>/scripts/remote-web.py` liegt neben `openamer-agent/`, nicht darin. Damit gilt:

```bash
cd <home>/openamer-agent && git rev-parse --show-toplevel   # → …/openamer-agent
git status --short -- ../scripts/remote-web.py              # → leer, weil nicht getrackt
```

- **`git status` im Repo sagt nichts über deine Datei.** Daraus „clean ⇒ nicht meins" zu folgern
  ist ein vacuous check. Erst prüfen, ob die Datei überhaupt im Repo liegt.
- **Das Repo-Testkommando kann sie nicht abdecken.** `npm run test` existierte hier und mappte auf
  `bash scripts/run_research_tests.sh --fast` — ein Research-Set, das 85/89 grün meldete und 4
  fremde Fehler zeigte. Keiner davon lag in einer Datei, die ich angefasst hatte.
- **Zugehörigkeit je Fehlerdatei beweisen:**
  ```bash
  git ls-files --error-unmatch scripts/tests/test_score_answer.py
  # Exit ≠ 0  ⇒ unversioniert = Install-Drift, nicht deine Regression
  ```
- **Der richtige Befehl für die eigene Änderung** ist `pytest` **neben dem Skript**
  (`<home>/scripts/tests/test_<name>.py`), nicht das Repo-Gate. Beide Zahlen berichten: „Suite
  85/4 fremd-rot (unversioniert), meine 10/10 grün, ruff sauber" — und ausdrücklich sagen, dass
  `npm run test` **nicht** vollständig grün ist. Ein grüner Teilbefund, als Gesamtergebnis
  ausgegeben, ist genau die Art Behauptung, die dieses Skill verhindern soll.
