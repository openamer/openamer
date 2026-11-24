"""Pair an Android phone over Wi-Fi (Android 11+) and verify the connection.

The phone must be told once: Entwickleroptionen → Drahtloses Debugging →
"Gerät mit Kopplungscode koppeln". Then:

    python adb_wifi_pair.py --discover                 # what does mDNS see right now?
    python adb_wifi_pair.py --code 123456              # pair with the discovered port, then connect
    python adb_wifi_pair.py --code 123456 --address 192.168.1.100:37123

`adb mdns services` publishes two services while the dialog is open:
``_adb-tls-pairing`` (the port the code belongs to) and ``_adb-tls-connect`` (the
port a client connects to afterwards). Reading both from mDNS means nobody has to
copy a port number by hand — only the 6-digit code has to come from the phone.

Verified 2026-10-30: the discover path runs clean when wireless debugging is off
(reports "keine"), and the script exits 2 when no device reaches state "device".
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


def find_adb(explicit: str | None = None) -> str:
    if explicit:
        return explicit
    for candidate in ADB_CANDIDATES:
        if candidate == "adb":
            return candidate
        if os.path.isfile(candidate):
            return candidate
    raise SystemExit("adb not found — install Android platform-tools or pass --adb PATH")


def run(adb: str, *args: str, timeout: float = 25.0) -> str:
    try:
        out = subprocess.run(
            [adb, *args],
            capture_output=True,
            text=True,
            timeout=timeout,
            errors="replace",
            check=False,
        )
        return (out.stdout or "") + (out.stderr or "")
    except subprocess.TimeoutExpired:
        return f"<timeout after {timeout}s: adb {' '.join(args)}>"
    except OSError as exc:
        return f"<adb could not start: {exc}>"


def discover(adb: str) -> dict[str, list[tuple[str, int]]]:
    """Return {'pairing': [(ip, port)], 'connect': [(ip, port)]} from mDNS."""
    run(adb, "start-server", timeout=20.0)
    text = run(adb, "mdns", "services", timeout=15.0)
    found: dict[str, list[tuple[str, int]]] = {"pairing": [], "connect": []}
    for line in text.splitlines():
        match = re.search(r"(_adb-tls-pairing|_adb-tls-connect)\s+(\S+):(\d+)", line)
        if match:
            kind = "pairing" if "pairing" in match.group(1) else "connect"
            found[kind].append((match.group(2), int(match.group(3))))
    if not any(found.values()):
        # Older Androids do not publish mDNS services; show the raw lines so the
        # caller can still read an address out of them.
        for line in text.splitlines():
            if "_adb" in line:
                print(f"  (roh) {line.strip()}")
    return found


def main() -> int:
    parser = argparse.ArgumentParser(description="Pair an Android phone over Wi-Fi")
    parser.add_argument("--code", help="6-digit pairing code from the phone dialog")
    parser.add_argument("--address", help="IP:PORT from the pairing dialog")
    parser.add_argument("--discover", action="store_true", help="only show what mDNS sees")
    parser.add_argument("--adb", default=None)
    args = parser.parse_args()

    adb = find_adb(args.adb)
    print(f"adb: {adb}")
    services = discover(adb)

    if args.discover or not args.code:
        print(f"pairing services: {services['pairing'] or 'keine'}")
        print(f"connect services: {services['connect'] or 'keine'}")
        if not services["pairing"]:
            print(
                "\nNichts gefunden. Am Handy: Entwickleroptionen → Drahtloses Debugging einschalten,\n"
                "dann 'Gerät mit Kopplungscode koppeln' öffnen — erst dann erscheint der Dienst."
            )
        return 0

    target: tuple[str, int] | None = None
    if args.address and ":" in args.address:
        host, _, port = args.address.partition(":")
        target = (host, int(port))
    elif services["pairing"]:
        target = services["pairing"][0]

    if target is None:
        print("Kein Kopplungs-Endpunkt bekannt — bitte --address IP:PORT aus dem Dialog angeben.")
        return 1

    print(f"\n→ adb pair {target[0]}:{target[1]} {args.code}")
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
