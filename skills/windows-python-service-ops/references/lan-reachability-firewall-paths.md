# LAN-Erreichbarkeit eines lokalen Dienstes (Windows, ohne Admin)

Fall vom 30.10.2026: `scripts/remote-web.py` (Dashboard, Port 8901) lief, `/health` antwortete
lokal mit 200 — vom Handy im **selben** WLAN kam nur ein Timeout. Das ist der Moment, in dem man
geneigt ist „gleiches WLAN reicht nicht" zu sagen. Es reichte; die Firewall war das Problem.

## Die Kette, die man messen muss

| Ebene | Frage | Werkzeug |
|---|---|---|
| L3 | Ist das Gerät überhaupt erreichbar? | `ping` — **lügt bei Handys im Standby** |
| L4 | Lauscht der Dienst, und auf welcher Adresse? | `Get-NetTCPConnection -LocalPort <p> -State Listen` |
| Bild | **Welches** Programm lauscht wirklich? | `Get-Process -Id <pid> \| Select Id,Path` |
| Policy | Deckt eine Regel genau dieses Bild? | `Get-NetFirewallApplicationFilter` + `Get-NetFirewallRule` |
| Profil | Ist das Netz Public/Private? | `Get-NetConnectionProfile` |

Der Sprung zwischen Zeile 2 und Zeile 3 ist der entscheidende: „Port offen" beschreibt einen
Socket, nicht ein Programm. Und der Sprung zwischen 3 und 4 ist der, der den Fehler macht —
Windows vergleicht **Programmpfade**, nicht Programmnamen.

## Warum `*python*`-Suchen in die Irre führen

Gemessener Regelbestand auf diesem PC (Auszug):

```
python.exe   …\uv\python\cpython-3.11.15-windows-x86_64-none\python.exe         Public Allow
pythonw.exe  …\uv\python\cpython-3.11.15-windows-x86_64-none\pythonw.exe        Public Allow
pythonw.exe  …\local\python\pythoncore-3.14-64\pythonw.exe                     Public Allow
```

Der laufende Dienst hatte aber:

```
Path : …\AppData\Roaming\uv\python\cpython-3.11-windows-x86_64-none\pythonw.exe
```

`3.11` vs `3.11.15` — ein anderer Ordner, also **kein** Regel-Treffer, obwohl „python" in beiden
Pfaden steht. Das venv-Trampolin (`venv/Scripts/pythonw.exe`) ist nur der Eltern-Prozess; das
Kind ist der uv-Interpreter, und **der** ist das Bild, das Windows prüft.

## Fixes, nach Verfügbarkeit von Adminrechten

**Ohne Admin (auf diesem PC der einzige Weg, `IsInRole(Administrator) = False`):**

```powershell
# Interpreter starten, dessen Pfad eine Allow-Regel hat
& "C:\Users\<user>\AppData\Roaming\uv\python\cpython-3.11.15-windows-x86_64-none\pythonw.exe" `
  "C:\Users\<user>\AppData\Local\openamer-laptop\scripts\remote-web.py"
```

Danach `Get-Process -Id <pid> | Select Path` prüfen — der Pfad muss **zeichengleich** dem der
Regel entsprechen. Nur so ist „erlaubt" belegt statt gehofft.

**Mit Admin:**

```powershell
New-NetFirewallRule -DisplayName "OpenAmer Remote Web 8901" -Direction Inbound `
  -LocalPort 8901 -Protocol TCP -Action Allow -Profile Private
```

## Dauerhaftigkeit

`scripts/supervisor/organs.json` enthält ein Organ `remote-web` mit `start.argv` und
`observe_only: true`. Steht dort das venv-Trampolin, ist der Dienst nach dem nächsten
Supervisor-Start wieder unerreichbar. `argv[0]` auf den gedeckten Interpreter setzen und das
JSON nach dem Schreiben erneut parsen (`json.loads`) — ein kaputtes `organs.json` nimmt alle
Organe mit.

## Was ohne Admin *nicht* prüfbar ist

- `Get-NetFirewallPortFilter` → „Zugriff verweigert" (System Error 5). Also nicht behaupten,
  es gäbe keine Port-Regel — nur, dass man sie nicht sehen kann.
- Ob ein **fremdes** Gerät durchkommt. Ein Loopback- oder Cross-Interface-Curl belegt nur, dass
  der Listener lebt; die Firewall wird dabei nicht durchquert. Ehrliche Formulierung: „Pfad und
  Regel sind belegt, der letzte Meter gehört dem Gerät."

## Nebenbefund: Token-Rotation vor LAN-Freigabe

Das Default-Token des Dashboards (`openamer-remote-secret`) ist dokumentiert und damit im Netz
bekannt. Vor dem Öffnen auf `0.0.0.0` ein neues Token setzen (32 Byte → base32, 20 Zeichen) und
den Dienst **danach** neu starten — gelesen wird es nur beim Start. Prüfbar ohne Browser:
`api/status` muss mit dem alten Token `401` und mit dem neuen `200` liefern.
