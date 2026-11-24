# LAN identification — measured session evidence (2026-10-30)

Owner's question: *"ich bin mit meinem Handy auf gleichem WLAN, finde raus welches
Handy"*. Host: Windows, git-bash, one Ethernet interface (192.168.1.101) and one
WLAN interface (192.168.1.105) in the same /24.

## What each method actually produced

| Method | Result | Verdict |
|---|---|---|
| ICMP sweep (254 hosts, 64 workers, 250 ms) | 5 alive: .1, .100, .101, .105, .106, .108 | needed as the *enabler* for ARP |
| `arp -a` after the sweep | 7 entries incl. .104 (never answered ICMP but is in ARP) | **ARP is the device list**, ICMP alone misses sleeping devices |
| OUI API (`api.macvendors.com/<mac>`) | Zyxel, Nintendo, Amazon, "China Dragon" | named 4 of 6 devices without touching them |
| mDNS **multicast** (224.0.0.251, `ssdp:all`-style sweep of 9 service types) | 1 responder (.108) | nearly useless on its own |
| mDNS **unicast QU** (`<ip>:5353`, qclass `0x8001`) | .106 = `_philipstv_rpc`, .108 = `_spotify-connect` | **the step that identified the TV and the speaker** |
| NBNS (137) wildcard | nothing | phones/TVs do not answer |
| TCP probe with Python sockets | router: only 80/443 | no SSH anywhere |

## The resulting inventory

| IP | MAC | OUI | Device |
|---|---|---|---|
| 192.168.1.1 | 5c:64:8e:fa:e0:ab | Zyxel | router, **runs OpenWrt**, only 80/443 open |
| 192.168.1.100 | 2a:d3:b3:a8:e7:ac | **randomized** (0x2a → locally administered) | the phone (by elimination) |
| 192.168.1.101 | — | — | this PC, Ethernet |
| 192.168.1.104 | e0:ef:bf:fc:e9:39 | Nintendo | console |
| 192.168.1.105 | 58:02:05:c5:91:32 | — | this PC, WLAN |
| 192.168.1.106 | a0:9d:c1:dd:9f:35 | China Dragon | Philips TV (`_philipstv_rpc`) |
| 192.168.1.108 | 4c:60:ad:17:59:fd | Amazon | Echo / speaker (`_spotify-connect`) |

## Two measurement mistakes worth remembering

**1. `/dev/tcp` does not exist in MSYS bash.** The first port check was

```bash
timeout 4 bash -c "exec 3<>/dev/tcp/$ip/22 && head -c 60 <&3"
```

and it failed for **every** host, router included. That was read as "no SSH
anywhere". A Python `socket.connect_ex` probe gave the real answer (router: 80/443
only). A method that fails uniformly is a broken method, not a finding — check the
method against a host you *know* is open (the router's own port 80) before
concluding anything.

**2. A silent device is not an absent device.** .100 answered nothing at all —
no mDNS, no NBNS, no SSDP, no open port of the probed set. That is exactly what a
phone in Doze looks like. The honest claim was "identifiable only by elimination",
not "this is your phone, proven".

## The elimination argument that was actually defensible

Every other device resolved to a real vendor and to a device class. The only
unresolved one carried a locally-administered MAC — the signature of iOS "Private
Wi-Fi Address" / Android 10+ randomization. So: *the phone is .100*, labelled as an
inference, with a 10-second self-check offered (flight mode → IP stops answering;
router DHCP lease list holds the hostname).

## Control, priced per device

The user asked earlier whether "every device in the WLAN" could be controlled. From
the same measurements:

- router (OpenWrt, no SSH, custom UI at `/` — the standard `/cgi-bin/luci/` and
  `/ubus/` paths both returned **404**): needs the root password; then `ubus` gives
  Wi-Fi, leases, firewall.
- Philips TV: DIAL/jointSPACE on 1925/1926 is the realistic unauthenticated surface.
- Echo: no usable local API.
- phone: ADB needs on-device pairing; iPhone has no remote-control surface.

Conclusion delivered: **discovery yes, control no** — and the one useful lever found
was the always-on OpenWrt router as a candidate replication peer.
