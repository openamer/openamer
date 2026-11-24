---
name: lan-device-discovery
description: "Use when you must identify or reach a device on the LAN."
version: 1.0.0
author: OpenAmer Agent
license: MIT
platforms: [windows, linux, macos]
metadata:
  openamer:
    tags: [network, lan, discovery, mdns, oui, adb, ios, phone]
    related_skills: [windows-python-service-ops, remote-web, pen-tester]
---

# Welches Gerät ist das? (und wie erreiche ich es)

## Trigger

- „Finde raus, welches Gerät/welches Handy im WLAN ist"
- „Kannst du mit meinem Handy reden / es steuern?"
- Ein Dienst ist im LAN nicht erreichbar, das Gerät aber „im gleichen Netz"
- Inventar: was hängt alles im Heimnetz

## Regel 0 — ICMP lügt, ARP nicht

Ein Handy im Standby (Android Doze, iOS) verwirft Pings und fehlt in **jedem** Ping-Sweep.
Gemessen 30.10.26: Sweep fand 5 Geräte, das gesuchte Telefon war nicht dabei; nach
ARP-Erzwingung waren es 6. Um zu senden, muss ein Gerät **ARP** beantworten — das ist die
belastbare Ebene.

```python
# Ein UDP-Datagramm pro Adresse erzwingt die ARP-Auflösung
sock.sendto(b"\x00", (ip, 9))     # Port 9 muss nicht offen sein
```

Danach die Tabelle lesen — **pro Schnittstelle**! `arp -a` zeigt in MSYS oft nur eine; bei
mehreren Interfaces (WLAN + Ethernet im selben /24) ist das eine halbe Antwort:

```powershell
Get-NetNeighbor -AddressFamily IPv4 | Where State -ne 'Unreachable' |
  Select InterfaceAlias,IPAddress,LinkLayerAddress,State | Sort InterfaceAlias
```

Fertiges Werkzeug: `scripts/lan_inventory.py` (ARP-Zwang + OUI + mDNS in einem Lauf).

## Die drei Ebenen der Identifikation

| Ebene | Signal | Aussagekraft |
|---|---|---|
| **OUI** (erste 3 MAC-Bytes) | `https://api.macvendors.com/<mac>` | stark, wenn die MAC echt ist |
| **randomisierte MAC** | Bit 0x02 im ersten Byte gesetzt (z. B. `2a:…`, `12:…`) | Gerät mit MAC-Privacy = **Handy/Laptop** (iOS „Private Wi-Fi Address", Android 10+) |
| **Dienste** | unicast DNS-SD (QU-Bit), SSDP | nennt den Gerätetyp direkt |

Gemessene Beispiele für Dienst-Namen, die eine Zuordnung sofort erledigen:

```
_philipstv_rpc._tcp          → Philips-TV
_spotify-connect._tcp        → Amazon Echo / Spotify-Gerät
_companion-link._tcp         → iOS 13+/macOS
_apple-mobdev2._tcp          → gepaartes iPhone
_googlecast._tcp             → Chromecast / Android-TV
_airplay / _raop._tcp        → Apple-Gerät, Lautsprecher
_samsungtvrc._tcp            → Samsung-TV (nicht: Samsung-Handy)
```

**mDNS richtig fragen:** ein Multicast-Query von einem beliebigen Port wird von Handys
ignoriert. Der „one-shot"-Query an **die IP des Geräts selbst**, Port 5353, mit `qclass 0x8001`
(QU-Bit) bekommt Antworten — das macht `scripts/lan_inventory.py`.

## Zuordnung ohne Vendor-Beweis

Eine randomisierte MAC lässt sich **keinem** Hersteller zuordnen. Dann gilt Ausschluss-Logik,
und die muss man als solche benennen:

1. Alle Geräte mit echter OUI identifizieren (Router, Konsole, TV, Lautsprecher, eigener PC).
2. Port-Fingerprints der restlichen prüfen (siehe unten).
3. Was übrig bleibt, ist das gesuchte Gerät — als **Inferenz** ausweisen, nicht als Messung.

Live-Beispiel: `.100` randomisierte MAC **plus** offener Port 62078 = iPhone (62078 ist
`lockdownd`, iOS-only) → das gesuchte **Samsung** konnte nur das zweite randomisierte Gerät
sein (`.107`). Diese Umkehrung ist der Beweis; „randomisierte MAC = dein Handy" allein wäre
geraten gewesen.

## Port-Fingerprints, die wirklich unterscheiden

| Port | Bedeutung |
|---|---|
| **62078** | iOS `lockdownd` — **das** Merkmal eines iPhones im WLAN |
| 5555 / 5037 | ADB (nur wenn „Drahtloses Debugging" aktiv ist) |
| 445 / 139 | Windows/SMB |
| 9100 / 515 / 631 | Drucker |
| 8008/8009/8443 | Cast/Chromecast |
| 1900 | UPnP (SSDP-Responder) |

Ein **offener** Port ist ein Beweis; ein **geschlossener** ist keiner (Firewall, Doze).

## „Kannst du mit dem Handy reden?"

Die Reihenfolge, die Frust vermeidet:

1. **Erst messen, ob überhaupt ein Dienst existiert.** Standard-Handys haben **keinen**
   eingehenden Dienst — gleiches WLAN heißt nicht gleiches Recht.
2. **Wenn nichts lauscht:** die Richtung umdrehen. Das Handy ist ein Browser — ein lokaler
   HTTP-Dienst (z. B. das Dashboard auf `:8901`) macht aus „ich kann nicht" ein „hier ist die
   URL". Das ist echte Kommunikation, ohne eine einzige Einstellung am Gerät.
   Für die Erreichbarkeit im LAN gilt `windows-python-service-ops` (Firewall matcht Pfade).
3. **Wenn du das Gerät steuern willst** (Benachrichtigungen, SMS, Screenshot), bleibt ADB —
   und das braucht **eine** Freigabe am Gerät. Siehe unten.

### Android: ADB über WLAN (kein Konto, keine Cloud)

Am Gerät: Entwickleroptionen → Drahtloses Debugging → „Mit Kopplungscode koppeln".
Der Dialog zeigt `IP:PORT` und einen 6-stelligen Code; der **Connect-Port ist ein anderer**
als der Pairing-Port. Beide findet `adb mdns services` (`_adb-tls-pairing` /
`_adb-tls-connect`) — dann muss niemand einen Port abtippen:

```bash
adb pair    <ip>:<pairing-port> <code>
adb connect <ip>:<connect-port>
adb devices -l          # muss "<ip>:<port>   device" zeigen
```

Fertiges Werkzeug: `scripts/adb_wifi_pair.py` (`--discover`, `--code`, optional `--address`).
Ohne Kopplungscode geht es nicht — der Code muss **am Telefon** getippt werden; keine
Fernroutine ersetzt das, das ist der Sinn der Kopplung.

### iPhone: lockdownd spricht, verweigert aber ohne Pairing

`lockdownd` (TCP 62078) nimmt auch von ungekoppelten Clients die TCP-Verbindung an und
**resettet sie sofort** (`ConnectionResetError [WinError 10054]`) — selbst `QueryType`, das
der Dienst ohne Vertrauen beantworten könnte. Ein Pairing-Record liegt unter
`%ProgramData%\Apple\Lockdown\*.plist` (Windows); fehlt er, hilft nur Kabel + „Vertrauen".
Das Wire-Format (4-Byte-Länge + XML-Plist) prüft `--selftest` im Werkzeug
`<home>/tools/ios_lockdown_probe.py` gegen einen Mock-Server, ohne Gerät.

## Fallstricke (alle live getroffen)

- **`/dev/tcp` gibt es in MSYS-Bash nicht.** Ein „kein SSH/Banner"-Ergebnis daraus ist
  wertlos. Ports mit Python-Sockets prüfen.
- **Ping-Ausgabe ist OEM-kodiert**: `subprocess.run(['ping', …], text=True)` wirft
  `UnicodeDecodeError` — `encoding="oem", errors="replace"` setzen.
- **Die eigene Abfrage matcht sich selbst**: `CommandLine -match 'gateway'` zählt das
  PowerShell-Query mit. Für Zählungen argv-Shape prüfen (`argv[-2:] == ['gateway','run']`)
  oder die eigene PID ausschließen.
- **`arp -a` ist pro Schnittstelle** — bei mehreren Interfaces `Get-NetNeighbor` nutzen.
- **TTL ≈ 64** heißt Linux/Android/iOS; 255 heißt Netzgerät (Router, Drucker) — als Hinweis
  brauchbar, nie als Beweis.
- **Nichts „steuern" versprechen**, was einen Login braucht: Router (OpenWrt) = root-Passwort,
  Telefon = Pairing, TV = Hersteller-API. Passwörter raten ist keine Fähigkeit, sondern ein
  Angriff — auch im eigenen Netz.

## Antwortform

Gerätetabelle mit `IP | MAC | Hersteller/Grund | Gerät`, dann **ein** Satz, welches Signal
welche Zeile stützt, dann die ehrliche Grenze (randomisierte MAC = Inferenz), dann der Weg
zum Zugriff. Keine Vermutung als Messung verkleiden — die Korrektur der eigenen
Fehlzuordnung gehört ausdrücklich in die Antwort.
