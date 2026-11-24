#!/usr/bin/env python3
"""ADB über WLAN koppeln (Android 11+) — der einzige Weg, ein Telefon zu STEUERN.

Am Gerät einmalig: Entwickleroptionen → Drahtloses Debugging → „Gerät mit
Kopplungscode koppeln". Der Dialog zeigt IP:PORT und einen 6-stelligen Code.
Der Pairing-Port ist NICHT der Connect-Port; beide publiziert mDNS
(`_adb-tls-pairing` / `_adb-tls-connect`), deshalb muss niemand einen Port
abtippen.

    python adb_wifi_pair.py --discover
    python adb_wifi_pair.py --code 123456
    python adb_wifi_pair.py --code 123456 --address 192.168.1.107:37123

Der Kopplungscode muss am Telefon getippt werden — keine Fernroutine ersetzt
das. `adb` liegt hier unter %LOCALAPPDATA%\\Android\\Sdk\\platform-tools\\adb.exe.
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import time

ADB_CANDIDATES = [
    os.path.expandvars(r"%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe"),
    "adb",
]


def find_adb() -> str:
    for candidate in ADB_CANDIDATES:
        if candidate == "adb" or os.path.isfile(candidate):
            return candidate
    raise SystemExit("adb not found — Android platform-tools installieren oder --adb PATH")


def run(adb: str, *args: str, timeout: float = 25.0) -> str:
    try:
        out = subprocess.run(
            [adb, *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=timeout,
        )
        return (out.stdout or "") + (out.stderr or "")
    except subprocess.TimeoutExpired:
        return f"<timeout nach {timeout}s: adb {' '.join(args)}>"


def discover(adb: str) -> dict[str, list[tuple[str, int]]]:
    run(adb, "start-server", timeout=20.0)
    text = run(adb, "mdns", "services", timeout=15.0)
    found: dict[str, list[tuple[str, int]]] = {"pairing": [], "connect": []}
    for line in text.splitlines():
        match = re.search(r"(_adb-tls-pairing|_adb-tls-connect)\s+(\S+):(\d+)", line)
        if match:
            kind = "pairing" if "pairing" in match.group(1) else "connect"
            found[kind].append((match.group(2), int(match.group(3))))
    return found


def main() -> int:
    parser = argparse.ArgumentParser(description="Android-Telefon über WLAN koppeln")
    parser.add_argument("--code", help="6-stelliger Kopplungscode aus dem Telefon-Dialog")
    parser.add_argument("--address", help="IP:PORT aus dem Dialog (wenn mDNS nichts findet)")
    parser.add_argument("--discover", action="store_true", help="nur zeigen, was mDNS sieht")
    parser.add_argument("--adb", default=None)
    args = parser.parse_args()

    adb = args.adb or find_adb()
    print(f"adb: {adb}")
    services = discover(adb)

    if args.discover or not args.code:
        print(f"pairing services: {services['pairing'] or 'keine'}")
        print(f"connect services: {services['connect'] or 'keine'}")
        if not services["pairing"]:
            print(
                "\nNichts gefunden. Am Telefon: Entwickleroptionen → Drahtloses Debugging ein,\n"
                "dann 'Gerät mit Kopplungscode koppeln' öffnen — erst dann erscheint der Dienst."
            )
        return 0

    target = None
    if args.address and ":" in args.address:
        host, _, port = args.address.partition(":")
        target = (host, int(port))
    elif services["pairing"]:
        target = services["pairing"][0]
    if target is None:
        print("Kein Kopplungs-Endpunkt bekannt — bitte --address IP:PORT aus dem Dialog angeben.")
        return 1

    print(f"\n→ adb pair {target[0]}:{target[1]}")
    print(run(adb, "pair", f"{target[0]}:{target[1]}", args.code, timeout=40.0).strip())

    connect_target = services["connect"][0] if services["connect"] else target
    for attempt in range(1, 4):
        print(f"→ adb connect {connect_target[0]}:{connect_target[1]} (Versuch {attempt})")
        output = run(adb, "connect", f"{connect_target[0]}:{connect_target[1]}", timeout=25.0).strip()
        print(output)
        if "connected to" in output.lower():
            break
        time.sleep(2)

    time.sleep(1)
    devices = run(adb, "devices", "-l", timeout=20.0).strip()
    print("\n=== adb devices -l ===")
    print(devices)
    return 0 if re.search(r"\tdevice", devices) else 2


if __name__ == "__main__":
    sys.exit(main())
