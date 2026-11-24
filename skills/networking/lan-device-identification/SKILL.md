---
name: lan-device-identification
description: "Identify which device on the LAN is which."
version: 1.0.0
author: OpenAmer Agent
license: MIT
platforms: [windows, linux, macos]
metadata:
  openamer:
    tags: [network, lan, discovery, mdns, oui, inventory]
    related_skills: [ssh-manager, windows-python-service-ops]
---

# LAN device identification — "welches Gerät ist das?"

Use when the owner asks *which* device on their network is what: "ich bin mit dem
Handy im WLAN, finde raus welches", "was hängt alles im Netz", "ist das mein
Drucker?", or before any device-control claim.

The job is **attribution without credentials**. Discovery is easy; naming a device
is not, and the difference between "I found 6 devices" and "your phone is .100" is
a method, not a guess.

Runnable helpers (all stdlib only, no device needed to check them):

* `scripts/lan_device_identify.py` — sweep + OUI + unicast DNS-SD + NBNS.
* `scripts/adb_wifi_pair.py` — `--discover` shows whether a phone is advertising
  ADB over Wi-Fi at all; `--code <6 digits>` pairs and connects.
* `scripts/ios_lockdown_probe.py` — `[ip]` handshakes with `lockdownd`, `--selftest`
  proves the plist framing against a mock so the wire format is verified without a
  phone in hand.

Method notes and pitfalls: `references/lan-device-identification.md`.

## Four steps, in this order

1. **Presence — force ARP, do not trust a ping sweep.** An ICMP sweep is optional:
   a phone in Doze drops pings and never appears. ARP is not optional — to stay on
   the network a device must answer ARP. Send one datagram per address to make the
   kernel resolve the MAC, then read the neighbour table:

   ```python
   for ip in hosts:                       # 1..254
       s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
       s.sendto(b"\x00", (ip, 9))         # any port; only the ARP resolution matters
       s.close()
   ```

   ```powershell
   Get-NetNeighbor -AddressFamily IPv4 | Where-Object {$_.State -ne 'Unreachable'} |
     Select-Object InterfaceAlias,IPAddress,LinkLayerAddress,State
   ```

   **Measured failure (2026-10-30):** the ICMP sweep found 6 devices and missed the
   owner's phone entirely; the forced-ARP pass surfaced `192.168.1.107` — the phone —
   and the identification was wrong until then. `arp -a` printed **one** interface's
   table on a two-interface host (Ethernet + WLAN, both in the same /24), so half the
   neighbours were invisible: use `Get-NetNeighbor` (all interfaces) and always name
   the interface you measured on.
2. **Vendor from the MAC (OUI).** `https://api.macvendors.com/<mac>` resolves the
   first three octets. This alone named four devices in one session: Nintendo,
   Amazon, Zyxel, "China Dragon" (TV panel). A randomized MAC has **no** vendor —
   see below.
3. **Unicast DNS-SD with the QU bit.** This is the step people get wrong. A normal
   *multicast* mDNS query on 224.0.0.251 is ignored by phones and most TVs. Send the
   query **directly to `<ip>:5353`** with `qclass = 0x8001` (unicast-response bit) and
   they answer with their service types:
   `_philipstv_rpc` → Philips TV, `_spotify-connect` → Echo/speaker,
   `_companion-link` / `_apple-mobdev2` → iPhone, `_googlecast` → Chromecast.
4. **NBNS (137) / LLMNR** for Windows and SMB boxes; printers answer `_ipp._tcp`.

Cross-check with the ports you are allowed to touch (a phone in standby answers
nothing — that is a finding, not a failure).

## Randomized MAC = phone/laptop, and the identification is by ELIMINATION

If the first MAC octet has the **locally-administered bit** set (`0x02`; e.g. `2a:…`,
`d2:…`, `da:…`), the address is spoofed on purpose — iOS "Private Wi-Fi Address",
Android 10+. No OUI lookup can resolve it, by design.

Say exactly that, then identify by elimination: when every other device on the
network resolves to a real vendor (router, TV, console, speaker, your own PC on its
two interfaces), the single randomized one is the phone. Label it as an inference
with its evidence, never as a name — and give the owner a 10-second self-check
(flight mode on → the IP stops answering; or the router's DHCP lease list, which
holds the hostname).

**With TWO randomized devices the elimination is not finished — fingerprint, then
ask.** Measured 2026-10-30: `.100` (randomized) and `.107` (randomized) were both
candidates; the assistant named `.100` as "your phone by elimination", the owner
answered *"meine Handy ist samsung"*, and it was `.107`. What separated them was a
port probe, not elimination:

```
.100  TCP 62078 connect OK, then immediate RST  → iOS lockdownd  → an iPhone
.107  62078/5555/445/7000/… all closed, TTL 64  → Android in standby → the Samsung
```

So: check 62078 on **every** randomized candidate first (an open one is iOS and out
of the running), then report the remaining one as the Android/other device with its
TTL and silence as evidence. And when the owner volunteers the platform ("it's a
Samsung"), treat that as a **test of the measurement**, not as new information to
absorb politely — re-measure and say which candidate the correction eliminates.
A confidently wrong "your phone is X" costs more than "two candidates, here is how
to tell them apart in ten seconds".

## Discovery is not control — say so in the same breath

Finding a device proves nothing about controlling it. Control needs **protocol +
credential** per device class, and the honest answer is a table:

| Device | What control would require |
|---|---|
| OpenWrt router | root password → `ubus`/LuCI: Wi-Fi on/off, DHCP leases, firewall rules |
| Philips TV | DIAL / jointSPACE on 1925/1926 (often unauthenticated — worth testing) |
| Echo / speaker | no usable local API; cloud account only |
| Android phone | ADB over Wi-Fi: *Drahtloses Debugging* on → `_adb-tls-pairing` in mDNS → `adb pair <ip>:<port> <code>` → `adb connect` (see below) |
| iPhone | a pairing record (`%ProgramData%\Apple\Lockdown`, created by USB + one "Vertrauen" tap) → `lockdownd` on 62078 gives device info and app management over Wi-Fi; without it there is no remote-control surface |
| Printer / NAS | HTTP API, SNMP, SMB credentials |

Never guess passwords and never work around a login, not even on the owner's own
network — state what credential would unlock which capability and stop there.

## "Wir sind doch im selben WLAN" — reachable, not addressable

The owner's most common objection, and it deserves measurements rather than a
lecture. Same subnet buys you ARP and ICMP; it buys nothing else, because a phone
runs no server. Measured on one iPhone (2026-10-30):

```
ping 192.168.1.100   3/3 replies, TTL 64, 5–66 ms              → reachable (L3)
22 80 443 445 548 7000 8080 8443 5223 5228 5555 1900          → all closed (L4)
62078                TCP connect OK in 46 ms, then immediate RST → a service exists
```

Report in exactly that order — *reachable, no service, one service that refuses* —
so "same WLAN" stops being a disagreement and becomes the first line of the table.

**An open 62078 is `lockdownd`, and that is a fingerprint.** iOS exposes it over
Wi-Fi only when the device was already paired with a computer for Wi-Fi sync, so an
open port says "this is an iPhone that was paired somewhere". It also refuses
cleanly: an unpaired client is reset (`ConnectionResetError`, WinError 10054) before
a single plist is exchanged. Port open ≠ usable.

The pairing record is the gate — `C:\ProgramData\Apple\Lockdown\*.plist` on Windows,
created by a USB connection plus one "Vertrauen" tap; nothing can create it
remotely, by design. Probe the service and prove the wire format without a device:
`scripts/ios_lockdown_probe.py [ip] [--selftest]`.

**Android without a cable — ADB over Wi-Fi (11+).** With *Entwickleroptionen →
Drahtloses Debugging* on, the phone publishes two mDNS services:
`_adb-tls-pairing` (the port the 6-digit code belongs to) and `_adb-tls-connect`:

```bash
adb mdns services                     # -> _adb-tls-pairing 192.168.1.x:37123
adb pair    <ip>:<pair-port> <code>   # code is displayed ON the phone
adb connect <ip>:<connect-port>
adb devices -l                        # must list "<ip>:<port>\tdevice"
```

`scripts/adb_wifi_pair.py --code 123456` runs both steps and takes the ports from
mDNS, so nobody copies a port by hand; `--discover` alone shows whether the phone is
advertising yet. The one thing that cannot be delegated is the code itself — it
appears on the phone and must be typed there. A cable ("USB-Debugging erlauben") is
the faster path when the owner is at the machine anyway.

## Pitfalls that produced wrong measurements here

- **MSYS/git-bash has no `/dev/tcp`.** `exec 3<>/dev/tcp/$ip/22` fails silently for
  *every* host, so "no SSH anywhere" was a false negative about the method, not
  about the network. Probe ports with Python `socket.connect_ex` and a real timeout.
- **A single mDNS multicast query returns almost nothing.** One responder out of six
  devices; the unicast QU probe then identified two more.
- **Silence is not absence.** A phone in Doze, a TV in standby and an IoT plug with
  mDNS off are all invisible to every step above. Report "not identifiable from this
  host" rather than "not present".
- **Custom OpenWrt builds 404 on the standard LuCI paths** (`/cgi-bin/luci/`,
  `/ubus/`) — do not read that as "no admin UI"; you have no session, that is all.
- **`ping` output is OEM/cp850.** `subprocess.run(..., text=True)` on it can raise
  `UnicodeDecodeError`; capture bytes and decode with `errors="replace"`.

## Verifying the probes themselves

A negative result from a probe is worth exactly as much as the probe. Two rules that
came out of getting this wrong:

**Check the instrument when everything returns the same answer.** The `/dev/tcp`
port sweep said "no SSH anywhere" for four hosts — and was a shell limitation, not a
network fact. A uniform negative across all targets is a broken instrument until a
positive control answers; re-probe with a different method before reporting.

**A script's `--selftest` is a manual check, not reviewable evidence.** Wrap the
contract in pytest next to the tool so `pytest <file> -q` yields `N passed`:

```python
spec = importlib.util.spec_from_file_location("probe", TOOLS / "probe.py")
probe = importlib.util.module_from_spec(spec); spec.loader.exec_module(probe)

def test_request_is_a_length_prefixed_xml_plist(): ...        # bytes on the wire
def test_reply_length_prefix_is_honoured_across_reads(): ...  # reply split over two segments
def test_closed_connection_raises_instead_of_returning_junk(): ...
def test_selftest_passes_without_a_device(): ...
```

Pin the contract (framing, split reads, failure path), never the happy path alone.
Two findings the repo's strict lint always raises on such tools: `subprocess.run(...)`
needs an explicit `check=False`, and `except Exception` (BLE001) must name its
exceptions — a blind catch hides the errors the probe exists to find.

## Report shape

One table (IP, MAC, vendor, service/name), then the elimination argument for the
ambiguous device, then the "discovery ≠ control" boundary with the credential that
would be needed. Numbers and vendors only when they came from this run.
