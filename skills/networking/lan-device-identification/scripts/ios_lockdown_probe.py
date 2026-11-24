"""Talk to an iPhone's lockdownd (TCP 62078) — and show exactly where it stops.

An open 62078 already tells you two things: this device is an iPhone, and it was
paired with a computer for Wi-Fi sync at some point (iOS only exposes lockdown on
Wi-Fi for known hosts). This script speaks the real protocol — 4-byte big-endian
length + XML plist, both directions, stdlib only — and reports what comes back.

Expected outcomes:

  QueryType -> {"Type": "com.apple.mobile.lockdown"}     device answers (unpaired)
  GetValue  -> {"Error": "PairRequired"}                 …and refuses content
  RST       -> ConnectionResetError (WinError 10054)    …or refuses the socket

All three mean "reachable, not addressable". The pairing record lives in
``C:\\ProgramData\\Apple\\Lockdown\\*.plist`` on Windows and can only be created by a
USB connection plus one trust tap on the phone — never remotely.

    python ios_lockdown_probe.py [ip]
    python ios_lockdown_probe.py --selftest     # proves the wire format, no device
"""
from __future__ import annotations

import plistlib
import socket
import struct
import sys

DEFAULT_HOST = "192.168.1.100"
LOCKDOWN_PORT = 62078

#: Everything that can go wrong while framing or decoding a lockdown exchange.
_PROTOCOL_ERRORS = (OSError, ValueError, KeyError, struct.error, plistlib.InvalidFileException)


def send(sock: socket.socket, message: dict) -> dict:
    """One length-prefixed XML-plist request/response over an open socket."""
    payload = plistlib.dumps(message, fmt=plistlib.FMT_XML)
    sock.sendall(struct.pack(">I", len(payload)) + payload)

    header = b""
    while len(header) < 4:
        chunk = sock.recv(4 - len(header))
        if not chunk:
            raise ConnectionError("connection closed while reading length")
        header += chunk
    (length,) = struct.unpack(">I", header)

    body = b""
    while len(body) < length:
        chunk = sock.recv(length - len(body))
        if not chunk:
            raise ConnectionError("connection closed while reading body")
        body += chunk
    return plistlib.loads(body)


def selftest() -> int:
    """Prove the framing against a local mock lockdownd — no iPhone needed.

    The real device answers differently (it resets an unpaired client), so the only
    thing verifiable without the phone is the wire format: a 4-byte big-endian length
    followed by an XML plist, in both directions.
    """
    import threading

    def serve(listener: socket.socket) -> None:
        conn, _ = listener.accept()
        with conn:
            conn.settimeout(5)
            for _ in range(2):
                header = conn.recv(4)
                if len(header) < 4:
                    return
                (length,) = struct.unpack(">I", header)
                request = plistlib.loads(conn.recv(length))
                reply = (
                    {"Type": "com.apple.mobile.lockdown"}
                    if request.get("Request") == "QueryType"
                    else {"Error": "PairRequired"}
                )
                body = plistlib.dumps(reply, fmt=plistlib.FMT_XML)
                conn.sendall(struct.pack(">I", len(body)) + body)

    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    threading.Thread(target=serve, args=(listener,), daemon=True).start()

    failures = 0
    with socket.create_connection(listener.getsockname(), timeout=5) as conn:
        conn.settimeout(5)
        reply = send(conn, {"Label": "selftest", "Request": "QueryType"})
        ok = reply == {"Type": "com.apple.mobile.lockdown"}
        print(f"  {'PASS' if ok else 'FAIL'}  QueryType -> {reply}")
        failures += 0 if ok else 1

        reply = send(
            conn, {"Label": "selftest", "Request": "GetValue", "Domain": "", "Key": "DeviceName"}
        )
        ok = reply == {"Error": "PairRequired"}
        print(f"  {'PASS' if ok else 'FAIL'}  GetValue  -> {reply}")
        failures += 0 if ok else 1
    listener.close()

    print(f"\nselftest: {'OK' if not failures else f'{failures} failure(s)'} (framing, both directions)")
    return 0 if not failures else 1


def main() -> int:
    if "--selftest" in sys.argv:
        return selftest()

    host = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_HOST
    print(f"-> {host}:{LOCKDOWN_PORT} (lockdownd)")
    try:
        sock = socket.create_connection((host, LOCKDOWN_PORT), timeout=8)
    except ConnectionRefusedError:
        print("   Port closed — no iPhone with Wi-Fi-sync pairing on this IP.")
        return 2
    except OSError as exc:
        print(f"   Unreachable: {exc}")
        return 2

    sock.settimeout(10)
    try:
        print("\n1) QueryType — the service names itself")
        try:
            print(f"   reply: {send(sock, {'Label': 'openamer', 'Request': 'QueryType'})}")
        except _PROTOCOL_ERRORS as exc:
            print(f"   error: {type(exc).__name__}: {exc}")

        print("\n2) GetValue DeviceName / ProductType / ProductVersion / UniqueDeviceID")
        for key in ("DeviceName", "ProductType", "ProductVersion", "UniqueDeviceID"):
            try:
                reply = send(
                    sock, {"Label": "openamer", "Request": "GetValue", "Domain": "", "Key": key}
                )
                print(f"   {key:<15} {reply.get('Value', reply.get('Error', reply))!r}")
            except _PROTOCOL_ERRORS as exc:
                print(f"   {key:<15} error: {type(exc).__name__}")
    finally:
        sock.close()

    print(
        "\nPairRequired or a reset means: talking works, content does not. Pairing needs a\n"
        "USB cable plus one trust tap on the phone — that step cannot be delegated."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
