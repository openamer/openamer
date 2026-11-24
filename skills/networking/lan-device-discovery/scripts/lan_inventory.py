#!/usr/bin/env python3
"""LAN-Inventar: ARP-Zwang für alle Adressen, dann OUI + unicast mDNS.

Warum nicht einfach pingen: ein Handy im Standby (Doze) verwirft ICMP und fehlt
in jedem Ping-Sweep — gemessen 30.10.26 fand der Sweep 5 von 6 Geräten. ARP kann
kein Gerät ignorieren, das im Netz bleiben will: ein UDP-Datagramm pro Adresse
erzwingt die Auflösung, danach ist die Nachbar-Tabelle vollständig.

Read-only: ICMP/UDP-Datagramme, ein Standard-Multicast-Query und eine
OUI-Abfrage. Kein Portscan, kein Login-Versuch, keine Zustandsänderung.

    python lan_inventory.py                 # 192.168.1.0/24
    python lan_inventory.py 10.0.0           # anderes /24
    python lan_inventory.py 192.168.1 --no-mdns
"""
from __future__ import annotations

import concurrent.futures
import re
import socket
import subprocess
import sys
import time
import urllib.request

SERVICES = [
    "_services._dns-sd._udp.local",
    "_companion-link._tcp.local",
    "_apple-mobdev2._tcp.local",
    "_airplay._tcp.local",
    "_googlecast._tcp.local",
    "_philipstv_rpc._tcp.local",
    "_spotify-connect._tcp.local",
    "_samsungtvrc._tcp.local",
    "_ipp._tcp.local",
    "_smb._tcp.local",
]


def force_arp(ip: str) -> None:
    """Jedes ausgehende Datagramm zwingt den Kernel, die MAC aufzulösen."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.sendto(b"\x00", (ip, 9))
    except OSError:
        pass
    finally:
        sock.close()


def neighbours() -> dict[str, tuple[str, str]]:
    """{ip: (mac, interface)} über ALLE Schnittstellen (arp -a zeigt oft nur eine)."""
    table: dict[str, tuple[str, str]] = {}
    if sys.platform == "win32":
        script = (
            "Get-NetNeighbor -AddressFamily IPv4 -ErrorAction SilentlyContinue | "
            "Where-Object {$_.State -ne 'Unreachable'} | "
            "ForEach-Object { '{0} {1} {2}' -f $_.IPAddress, $_.LinkLayerAddress, $_.InterfaceAlias }"
        )
        out = subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command", script],
            capture_output=True,
            text=True,
            encoding="oem",
            errors="replace",
            check=False,
            timeout=60,
        ).stdout
        for line in out.splitlines():
            parts = line.split()
            if len(parts) >= 2 and re.match(r"^\d+\.\d+\.\d+\.\d+$", parts[0]):
                mac = parts[1].lower().replace(":", "-")
                if re.match(r"^([0-9a-f]{2}-){5}[0-9a-f]{2}$", mac):
                    table[parts[0]] = (mac, parts[2] if len(parts) > 2 else "")
        return table

    out = subprocess.run(["ip", "neigh"], capture_output=True, text=True, check=False, timeout=30).stdout
    for line in out.splitlines():
        parts = line.split()
        if parts and re.match(r"^\d+\.\d+\.\d+\.\d+$", parts[0]) and "lladdr" in parts:
            mac = parts[parts.index("lladdr") + 1].lower().replace(":", "-")
            table[parts[0]] = (mac, parts[-1])
    return table


def vendor(mac: str) -> str:
    first = int(mac.split("-")[0], 16)
    if first & 0x02:
        return "randomisiert (locally administered = MAC-Privacy)"
    cached = _VENDOR_CACHE.get(mac[:8])
    if cached:
        return cached
    try:
        with urllib.request.urlopen(f"https://api.macvendors.com/{mac}", timeout=8) as response:
            name = response.read(80).decode("utf-8", "replace").strip() or "?"
    except Exception:
        name = "(OUI-Abfrage fehlgeschlagen)"
    _VENDOR_CACHE[mac[:8]] = name
    return name


_VENDOR_CACHE: dict[str, str] = {}


def mdns_unicast(ip: str) -> list[str]:
    """Unicast DNS-SD mit QU-Bit — Handys ignorieren Multicast-Queries."""

    def encode(name: str) -> bytes:
        return b"".join(bytes([len(p)]) + p.encode() for p in name.split(".")) + b"\x00"

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(1.0)
    for service in SERVICES:
        packet = (
            b"\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00"
            + encode(service)
            + b"\x00\x0c\x80\x01"  # PTR, qclass IN|QU
        )
        try:
            sock.sendto(packet, (ip, 5353))
        except OSError:
            break
        time.sleep(0.03)
    found: set[str] = set()
    deadline = time.time() + 1.8
    while time.time() < deadline:
        try:
            data, _ = sock.recvfrom(9000)
        except (socket.timeout, OSError):
            break
        for token in re.findall(rb"[A-Za-z0-9_.-]{3,}\._(?:tcp|udp)\.local", data):
            found.add(token.decode("ascii", "replace"))
    sock.close()
    return sorted(found)


def main(argv: list[str]) -> int:
    prefix = argv[1] if len(argv) > 1 and not argv[1].startswith("-") else "192.168.1"
    do_mdns = "--no-mdns" not in argv
    prefix = prefix.rstrip(".")
    hosts = [f"{prefix}.{i}" for i in range(1, 255)]

    with concurrent.futures.ThreadPoolExecutor(max_workers=128) as pool:
        list(pool.map(force_arp, hosts))

    table = neighbours()
    print(f"{'IP':<16}{'MAC':<19}{'Hersteller / Grund':<44}{'Dienste'}")
    print("-" * 124)
    for ip in sorted(table, key=lambda x: [int(p) for p in x.split(".") if p.isdigit()]):
        mac, iface = table[ip]
        services = ", ".join(mdns_unicast(ip))[:34] if do_mdns else ""
        print(f"{ip:<16}{mac:<19}{vendor(mac)[:42]:<44}{services}")
    print(f"\n{len(table)} Geräte auf Ebene 2 ({prefix}.0/24)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
