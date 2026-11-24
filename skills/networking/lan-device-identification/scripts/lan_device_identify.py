#!/usr/bin/env python3
"""Identify the devices on the local LAN without credentials.

    python lan_device_identify.py                 # sweep the local /24 + fingerprint
    python lan_device_identify.py --net 10.0.0.  # other /24
    python lan_device_identify.py --json

Four read-only steps, in the order that actually produces answers:

1. Forced ARP           -> which IPs exist. One datagram per address makes the kernel
                           resolve every MAC; ARP is mandatory for any device that is
                           online, while ICMP is optional (a phone in Doze drops pings
                           and vanishes from a ping sweep — measured 2026-10-30).
2. OUI lookup              -> vendor per MAC (skipped for randomized MACs: they have none).
3. Unicast DNS-SD (QU)     -> service types. THIS is the step that identifies TVs and
                              speakers; a plain multicast mDNS query is ignored.
4. NBNS name               -> Windows/SMB boxes.

No login, no brute force, no state change on any device. Discovery is not control —
see SKILL.md for what controlling each device class would require.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import re
import socket
import struct
import subprocess
import sys
import time
import urllib.request

SERVICES = [
    "_services._dns-sd._udp.local",
    "_companion-link._tcp.local",      # iOS 13+ / macOS handoff  -> phone/Mac
    "_apple-mobdev2._tcp.local",       # iPhone paired with a computer
    "_raop._tcp.local",
    "_airplay._tcp.local",
    "_googlecast._tcp.local",          # Chromecast / Google Home / Android TV
    "_androidtvremote2._tcp.local",
    "_philipstv_rpc._tcp.local",       # Philips TV
    "_spotify-connect._tcp.local",     # Echo / speaker / Spotify Connect
    "_ipp._tcp.local",                 # printer
    "_smb._tcp.local",                 # NAS / Windows share
]


# ── step 1: presence ──────────────────────────────────────────────────────────

def ping(host: str) -> bool:
    try:
        done = subprocess.run(["ping", "-n", "1", "-w", "250", host], capture_output=True, timeout=3)
        return done.returncode == 0
    except Exception:
        return False


def sweep(prefix: str) -> list[str]:
    hosts = [f"{prefix}{i}" for i in range(1, 255)]
    with concurrent.futures.ThreadPoolExecutor(max_workers=64) as pool:
        return [host for host, ok in zip(hosts, pool.map(ping, hosts)) if ok]


def arp_table() -> dict[str, str]:
    try:
        out = subprocess.run(["arp", "-a"], capture_output=True, timeout=10)
        # ping/arp output is OEM-encoded on Windows: decoding as utf-8 raises
        text = out.stdout.decode("cp850", errors="replace")
    except Exception:
        return {}
    table = {}
    for line in text.splitlines():
        match = re.match(r"\s*(\d+\.\d+\.\d+\.\d+)\s+([0-9a-fA-F-]{17})\s+(\w+)", line)
        if match:
            table[match.group(1)] = match.group(2).lower()
    return table


def force_arp(host: str) -> None:
    """Make the kernel resolve this neighbour's MAC.

    Any outbound datagram triggers the ARP request; the payload and the port are
    irrelevant and nothing is expected back. This is what finds devices that ignore
    ICMP — measured: a sleeping phone answered no ping but did answer ARP.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.sendto(b"\x00", (host, 9))
    except OSError:
        pass
    finally:
        sock.close()


def neighbour_table() -> dict[str, str]:
    """ARP cache of ALL interfaces, not just the routing interface.

    `arp -a` prints only the routing interface on a multi-homed host (Ethernet +
    WLAN in the same /24 here), so half the neighbours were invisible. Get-NetNeighbor
    enumerates every interface; merge both, keeping whatever has a MAC.
    """
    table = arp_table()
    if sys.platform == "win32":
        cmd = [
            "powershell",
            "-NoProfile",
            "-Command",
            "Get-NetNeighbor -AddressFamily IPv4 | "
            "Where-Object { $_.LinkLayerAddress -match '^([0-9A-Fa-f]{2}-){5}' } | "
            'ForEach-Object { "$($_.IPAddress)|$($_.LinkLayerAddress)" }',
        ]
        try:
            out = subprocess.run(cmd, capture_output=True, timeout=25, check=False).stdout
            for line in out.decode("utf-8", errors="replace").splitlines():
                if "|" not in line:
                    continue
                ip, mac = (part.strip() for part in line.split("|", 1))
                if re.fullmatch(r"\d+\.\d+\.\d+\.\d+", ip) and mac:
                    table.setdefault(ip, mac.lower())
        except Exception:
            pass
    return table


# ── step 2: vendor ────────────────────────────────────────────────────────────

def is_randomized(mac: str) -> bool:
    """Locally-administered bit set -> random MAC (iOS/Android private address)."""
    try:
        first = int(mac.split("-")[0], 16)
    except ValueError:
        return False
    return bool(first & 0x02)


def vendor(mac: str, timeout: float = 6.0) -> str:
    if is_randomized(mac):
        return "randomisiert (kein Hersteller => Handy/Laptop mit MAC-Privacy)"
    try:
        with urllib.request.urlopen(f"https://api.macvendors.com/{mac}", timeout=timeout) as response:
            return response.read(80).decode("utf-8", "replace").strip() or "?"
    except Exception:
        return "? (OUI-Abfrage fehlgeschlagen)"


# ── step 3: unicast DNS-SD (QU bit) ───────────────────────────────────────────

def _encode_name(name: str) -> bytes:
    out = b""
    for label in name.rstrip(".").split("."):
        out += bytes([len(label)]) + label.encode()
    return out + b"\x00"


def _build_query(name: str) -> bytes:
    # qclass 0x8001 = IN + unicast response requested. Without the QU bit,
    # phones and TVs stay silent.
    return struct.pack("!HHHHHH", 0, 0, 1, 0, 0, 0) + _encode_name(name) + struct.pack("!HH", 12, 0x8001)


def _read_name(data: bytes, offset: int) -> tuple[str, int]:
    labels, guard = [], 0
    while guard < 32:
        guard += 1
        length = data[offset]
        if length == 0:
            offset += 1
            break
        if length & 0xC0:
            pointer = struct.unpack("!H", data[offset : offset + 2])[0] & 0x3FFF
            nested, _ = _read_name(data, pointer)
            labels.append(nested)
            offset += 2
            break
        offset += 1
        labels.append(data[offset : offset + length].decode("utf-8", "replace"))
        offset += length
    return ".".join(labels), offset


def _parse(data: bytes, sink: set[str]) -> None:
    try:
        _id, _flags, qd, an, ns, ar = struct.unpack("!HHHHHH", data[:12])
    except struct.error:
        return
    offset = 12
    for _ in range(qd):
        try:
            _, offset = _read_name(data, offset)
            offset += 4
        except Exception:
            return
    for _ in range(an + ns + ar):
        try:
            name, offset = _read_name(data, offset)
            rtype, _cls, _ttl, rdlength = struct.unpack("!HHIH", data[offset : offset + 10])
            offset += 10
            value = ""
            if rtype in (12, 33):
                value, _ = _read_name(data, offset)
            elif rtype == 1 and rdlength == 4:
                value = ".".join(str(b) for b in data[offset : offset + 4])
            elif rtype == 16:
                value = data[offset : offset + rdlength].decode("utf-8", "replace")
            offset += rdlength
            if rtype in (12, 33, 16) and value:
                sink.add(f"{name} = {value}"[:140])
        except Exception:
            return


def dns_sd(ip: str) -> set[str]:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(1.2)
    found: set[str] = set()
    for service in SERVICES:
        try:
            sock.sendto(_build_query(service), (ip, 5353))
        except OSError:
            break
        time.sleep(0.03)
    deadline = time.time() + 2.2
    while time.time() < deadline:
        try:
            data, _addr = sock.recvfrom(9000)
        except (socket.timeout, OSError):
            break
        _parse(data, found)
    sock.close()
    return found


# ── step 4: NBNS name ─────────────────────────────────────────────────────────

def nbns_name(ip: str) -> str:
    query = (
        struct.pack("!HHHHHH", 0x1234, 0, 1, 0, 0, 0)
        + b"\x20CKAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA\x00"
        + struct.pack("!HH", 0x0021, 0x0001)
    )
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(1.5)
    try:
        sock.sendto(query, (ip, 137))
        data, _ = sock.recvfrom(2048)
        return data[56 : 56 + 16].decode("ascii", "replace").strip()
    except Exception:
        return ""
    finally:
        sock.close()


def local_prefix() -> str:
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.connect(("192.0.2.1", 9))  # no packet is sent for UDP connect
        return probe.getsockname()[0].rsplit(".", 1)[0] + "."
    finally:
        probe.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--net", default="auto", help="prefix like 192.168.1.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    try:
        prefix = local_prefix() if args.net == "auto" else args.net
    except Exception:
        print("cannot determine the local subnet; pass --net 192.168.1.")
        return 1

    # ARP first (mandatory for any device that is online), ICMP afterwards — only the
    # ICMP answer is used to decide who gets an NBNS query.
    hosts = [f"{prefix}{i}" for i in range(1, 255)]
    with concurrent.futures.ThreadPoolExecutor(max_workers=128) as pool:
        list(pool.map(force_arp, hosts))
    alive = set(sweep(prefix))
    table = neighbour_table()
    rows = []
    for ip in sorted(
        {i for i in alive} | {i for i in table if i.startswith(prefix)},
        key=lambda value: [int(part) for part in value.split(".")],
    ):
        if ip.endswith(".255"):
            continue
        mac = table.get(ip, "")
        rows.append(
            {
                "ip": ip,
                "mac": mac,
                "randomized": is_randomized(mac) if mac else None,
                "vendor": vendor(mac) if mac else "",
                "dns_sd": sorted(dns_sd(ip))[:8],
                "nbns": nbns_name(ip) if ip in alive else "",
            }
        )

    if args.json:
        print(json.dumps(rows, indent=2, ensure_ascii=False))
        return 0

    print(f"{'IP':<16}{'MAC':<19}{'HERSTELLER':<34}DIENSTE / NAME")
    print("-" * 118)
    for row in rows:
        services = ", ".join(entry.split(" = ")[-1] for entry in row["dns_sd"]) or row["nbns"] or "-"
        print(f"{row['ip']:<16}{row['mac'] or '-':<19}{row['vendor'][:32]:<34}{services[:52]}")
    print()
    randomized = [row["ip"] for row in rows if row["randomized"]]
    if randomized:
        print(f"randomisierte MAC (Handy/Laptop mit Privacy-Address): {', '.join(randomized)}")
        if len(randomized) > 1:
            print(
                "  -> MEHRERE Kandidaten: Ausschluss reicht NICHT. Erst 62078 tippen "
                "(offen = iOS lockdownd, also iPhone und damit aus dem Rennen), dann aus "
                "TTL/Stille den verbleibenden Androiden zuordnen."
            )
        else:
            print(
                "  -> kein Hersteller aufloesbar; Identifikation per Ausschluss "
                "(alle anderen Geraete haben echte OUIs) und per Gegenprobe am Geraet."
            )
    return 0


if __name__ == "__main__":
    sys.exit(main())
