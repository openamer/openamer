#!/usr/bin/env python3
"""Philips TV remote control over the local network.

Two independent transports on the same TV:

  1. JointSpace REST API (port 1925) -- remote keys, volume, apps, text entry,
     opening a URL in the TV browser, power state.
  2. UPnP MediaRenderer / DLNA (SSDP + port 2870) -- push photos, audio and
     video from this machine to the TV.

No pairing is required on models that advertise ``"pairing_type": "none"``
(e.g. Philips 58PUS6203/12, NetTV 4.6.0.1 / JointSpace 6.1.0).

Usage
-----
    python scripts/tv_remote.py discover
    python scripts/tv_remote.py info
    python scripts/tv_remote.py key VolumeUp
    python scripts/tv_remote.py volume 20
    python scripts/tv_remote.py mute
    python scripts/tv_remote.py open https://example.com
    python scripts/tv_remote.py app com.netflix.ninja
    python scripts/tv_remote.py power on|off|status
    python scripts/tv_remote.py screen on|off|status
    python scripts/tv_remote.py context

The host is cached in ``<OPENAMER_HOME>/tv.json`` after a successful discover,
so later calls do not have to scan the network again.

Security note: JointSpace has no authentication on these models. Anyone on the
LAN can control the TV. That is the TV's design, not a choice made here.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import socket
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

DEFAULT_API_PORT = 1925
# The OpenAmer Browser: a TV-first web app with an address bar. It understands
# ?u=<encoded url> and navigates there itself, which is how OpenAmer drives the
# TV browser with a single API call.
BROWSER_APP = "https://openamer.com/browser.html"
# The DIAL launch endpoint (POST /apps/<name>) answers on 56789; the DIAL
# device description (dd.xml) is served on 56790. Both are tried.
DIAL_PORTS = (56789, 56790)
# Probed by launch: 201 means installed, 404 means not installed. Measured on
# 58PUS6203/12: Netflix and YouTube answer 201, every other name 404.
DIAL_CANDIDATES = ("Netflix", "YouTube", "Amazon", "PrimeVideo", "Spotify",
                   "Deezer", "RakutenTV", "GooglePlay", "Browser", "Chrome",
                   "DisneyPlus", "AppleTV", "Plex", "Kodi", "VLC")
SSDP_ADDR = ("239.255.255.250", 1900)
_STATE = Path(os.environ.get("OPENAMER_HOME", Path.home() / ".openamer")) / "tv.json"

# Keys accepted by POST /6/input/key. Names are Philips' own.
KEYS = {
    "power": "Standby", "home": "Home", "back": "Back", "exit": "Exit",
    "up": "CursorUp", "down": "CursorDown", "left": "CursorLeft", "right": "CursorRight",
    "ok": "Confirm", "play": "Play", "pause": "Pause", "stop": "Stop",
    "next": "Next", "prev": "Previous", "rewind": "Rewind", "forward": "Forward",
    "info": "Info", "options": "Options", "source": "Source",
    "volup": "VolumeUp", "voldown": "VolumeDown", "mute": "Mute",
    "chup": "ChannelStepUp", "chdown": "ChannelStepDown",
    "red": "Red", "green": "Green", "yellow": "Yellow", "blue": "Blue",
}


# --------------------------------------------------------------------------- http

def _request(host: str, path: str, payload: dict | None = None, timeout: float = 6.0):
    """Call the JointSpace API. Returns (status, parsed-or-raw-body)."""
    url = f"http://{host}:{DEFAULT_API_PORT}{path}"
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/json"} if data else {},
        method="POST" if data else "GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read().decode("utf-8", "replace")
            status = r.status
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except (urllib.error.URLError, socket.timeout, OSError) as e:
        return 0, f"unreachable: {e}"
    try:
        return status, json.loads(body)
    except json.JSONDecodeError:
        return status, body.strip()


# ------------------------------------------------------------------------- discovery

def _ssdp_locations(wait: float = 4.0) -> list[str]:
    """Collect LOCATION URLs from SSDP responders."""
    msg = (
        "M-SEARCH * HTTP/1.1\r\nHOST: 239.255.255.250:1900\r\n"
        'MAN: "ssdp:discover"\r\nMX: 2\r\nST: ssdp:all\r\n\r\n'
    ).encode()
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.settimeout(1.0)
    locs: list[str] = []
    try:
        s.sendto(msg, SSDP_ADDR)
    except OSError:
        return locs
    deadline = time.time() + wait
    while time.time() < deadline:
        try:
            data, _ = s.recvfrom(2048)
        except socket.timeout:
            continue
        except OSError:
            break
        m = re.search(r"(?im)^LOCATION:\s*(\S+)", data.decode("utf-8", "ignore"))
        if m and m.group(1) not in locs:
            locs.append(m.group(1).strip())
    s.close()
    return locs


def _port_open(host: str, port: int, timeout: float = 0.6) -> bool:
    s = socket.socket()
    s.settimeout(timeout)
    try:
        return s.connect_ex((host, port)) == 0
    except OSError:
        return False
    finally:
        s.close()


def _is_philips(host: str) -> dict | None:
    if not _port_open(host, DEFAULT_API_PORT):
        return None
    status, body = _request(host, "/6/system", timeout=4)
    if status != 200 or not isinstance(body, dict):
        return None
    return {
        "host": host,
        "name": body.get("name", "?"),
        "api": body.get("api_version", {}),
        "nettv": body.get("nettvversion", "?"),
        "pairing": body.get("featuring", {}).get("systemfeatures", {}).get("pairing_type", "?"),
    }


def discover(write_cache: bool = True) -> list[dict]:
    """Find Philips TVs via SSDP, then confirm the JointSpace API answers."""
    hosts: list[str] = []
    for loc in _ssdp_locations():
        m = re.match(r"https?://([^:/]+)", loc)
        if m and m.group(1) not in hosts:
            hosts.append(m.group(1))

    # Fallback: touch port 1925 across the /24 that this machine lives in.
    if not hosts:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local = s.getsockname()[0]
            s.close()
            prefix = local.rsplit(".", 1)[0]
        except OSError:
            prefix = "192.168.1"
        import concurrent.futures
        cands = [f"{prefix}.{i}" for i in range(1, 255)]
        with concurrent.futures.ThreadPoolExecutor(max_workers=80) as ex:
            for ip, ok in zip(cands, ex.map(lambda h: _port_open(h, DEFAULT_API_PORT, 0.35), cands)):
                if ok:
                    hosts.append(ip)

    found = [r for r in (_is_philips(h) for h in hosts) if r]
    if found and write_cache:
        try:
            _STATE.parent.mkdir(parents=True, exist_ok=True)
            _STATE.write_text(json.dumps(found, indent=2), encoding="utf-8")
        except OSError:
            pass
    return found


def resolve_host(explicit: str | None = None) -> str:
    """Explicit flag -> cached state -> fresh discovery."""
    if explicit:
        return explicit
    if _STATE.exists():
        try:
            cached = json.loads(_STATE.read_text(encoding="utf-8"))
            if cached and _port_open(cached[0]["host"], DEFAULT_API_PORT):
                return cached[0]["host"]
        except (OSError, ValueError, KeyError, IndexError):
            pass
    found = discover()
    if not found:
        raise SystemExit("No Philips TV found. Same network? TV on? Try: discover")
    return found[0]["host"]


# ------------------------------------------------------------------------- actions

def cmd_discover(args) -> int:
    found = discover()
    if not found:
        print("No Philips TV with JointSpace on 1925 found.")
        return 1
    for f in found:
        api = f["api"]
        print(f"{f['host']:<15} {f['name']:<18} NetTV {f['nettv']:<10} "
              f"API {api.get('Major')}.{api.get('Minor')}.{api.get('Patch')}  pairing={f['pairing']}")
    print(f"\ncached in {_STATE}")
    return 0


def cmd_info(args) -> int:
    h = resolve_host(args.host)
    status, system = _request(h, "/6/system")
    if status != 200:
        print(f"TV unreachable at {h} (status {status}): {system}")
        return 1
    _, power = _request(h, "/6/powerstate")
    _, vol = _request(h, "/6/audio/volume")
    _, sw = _request(h, "/6/system/softwareversion")
    feats = system.get("featuring", {})
    print(f"host      {h}")
    print(f"model     {system.get('name')}")
    print(f"netTV     {system.get('nettvversion')}   os={feats.get('systemfeatures', {}).get('os_type')}")
    if isinstance(sw, dict) and sw.get("softwareversion"):
        print(f"firmware  {sw['softwareversion']}")
    print(f"pairing   {feats.get('systemfeatures', {}).get('pairing_type')}")
    print(f"power     {power.get('powerstate') if isinstance(power, dict) else power}")
    if isinstance(vol, dict):
        print(f"volume    {vol.get('current')}/{vol.get('max')}  muted={vol.get('muted')}")
    print(f"keys      {','.join(feats.get('jsonfeatures', {}).get('inputkey', [])) or 'unknown'}")
    print(f"content   {','.join(feats.get('systemfeatures', {}).get('content', [])) or 'unknown'}")
    return 0


def cmd_key(args) -> int:
    h = resolve_host(args.host)
    raw = args.key
    key = KEYS.get(raw.lower(), raw)
    status, body = _request(h, "/6/input/key", {"key": key})
    ok = status == 200
    print(f"{'OK' if ok else 'FAIL'}  key={key} (http {status})")
    return 0 if ok else 1


def cmd_volume(args) -> int:
    """Read or set volume.

    Measured on 58PUS6203/12 (NetTV 4.6, JointSpace 6.1): ``POST /6/audio/volume``
    answers HTTP 200 but does NOT change the level -- the API acknowledges the
    write and ignores it. Only the VolumeUp/VolumeDown keys actually move it,
    so a set is done as a key delta from the current value.
    """
    h = resolve_host(args.host)
    status, cur = _request(h, "/6/audio/volume")
    if args.level is None:
        print(cur)
        return 0
    if not isinstance(cur, dict):
        print(f"cannot read volume: {cur}")
        return 1
    target = int(args.level)
    target = max(cur.get("min", 0), min(cur.get("max", 60), target))
    delta = target - cur.get("current", 0)
    key = "VolumeUp" if delta > 0 else "VolumeDown"
    for _ in range(abs(delta)):
        _request(h, "/6/input/key", {"key": key})
        time.sleep(0.25)
    # The TV applies keys with a visible lag (measured >1s, ~2s on this model),
    # so poll for the target instead of sleeping a fixed amount.
    now = cur.get("current")
    for _ in range(14):
        time.sleep(0.5)
        _, after = _request(h, "/6/audio/volume")
        if isinstance(after, dict):
            now = after.get("current")
            if now == target:
                break
    ok = now == target
    print(f"volume {cur.get('current')} -> {now} (target {target}, {abs(delta)}x {key}) "
          f"{'OK' if ok else 'MISMATCH'}")
    return 0 if ok else 1


def cmd_mute(args) -> int:
    """Toggle mute with the Mute key (the JSON write is ignored, as with volume)."""
    h = resolve_host(args.host)
    _, vol = _request(h, "/6/audio/volume")
    want_muted = not args.off
    already = isinstance(vol, dict) and bool(vol.get("muted")) == want_muted
    if not already:
        _request(h, "/6/input/key", {"key": "Mute"})
        time.sleep(1.0)
        _, vol = _request(h, "/6/audio/volume")
    muted = vol.get("muted") if isinstance(vol, dict) else "?"
    ok = muted == want_muted
    print(f"muted={muted} (want {want_muted}) {'OK' if ok else 'MISMATCH'}")
    return 0 if ok else 1


def cmd_open(args) -> int:
    """Open a URL in the TV's built-in browser.

    The endpoint is ``POST /6/activities/<activity>``, NOT ``.../launch``.
    Measured on 58PUS6203/12: ``/6/activities/launch`` answers 405 Method Not
    Allowed for every method, while ``/6/activities/browser`` answers 200.
    """
    h = resolve_host(args.host)
    payload = {"intent": {"action": "android.intent.action.VIEW", "uri": args.url}}
    status, body = _request(h, "/6/activities/browser", payload)
    ok = status == 200
    print(f"open {args.url} -> http {status}{'' if ok else ' (expected 200)'}")
    return 0 if ok else 1


def cmd_activity(args) -> int:
    """Start one of the activities the TV actually advertises.

    Measured set on this model: ``tv`` and ``browser`` answer 200; any other
    name answers 405, i.e. the TV publishes no app launcher and no app
    inventory over JointSpace at all.
    """
    h = resolve_host(args.host)
    status, body = _request(h, f"/6/activities/{args.name}",
                            {"intent": {"action": "android.intent.action.MAIN"}})
    ok = status == 200
    print(f"activity {args.name} -> http {status}"
          f"{'' if ok else ' (only tv|browser answer 200 on this model)'}")
    return 0 if ok else 1


def _dial_launch(host: str, app: str) -> tuple[int, int | None]:
    """Start an installed app through the DIAL server.

    DIAL launch is a **POST** to ``/apps/<name>``; a GET only queries state and
    404s here. Measured on 58PUS6203/12:

        POST :56789/apps/Netflix               -> 201
        POST :56789/apps/YouTube               -> 201
        POST :56789/apps/Amazon|Spotify|zzz    -> 404

    A 404 for an invented name proves the 201s are a real inventory signal, not
    a rubber stamp. The launch endpoint lives on 56789 while the DIAL device
    description (``dd.xml``) is served on 56790, so both are tried.
    """
    body = (b'<?xml version="1.0"?><launch>'
            b'<param name="pairingCode" value=""/></launch>')
    last = 0
    for port in DIAL_PORTS:
        try:
            req = urllib.request.Request(
                f"http://{host}:{port}/apps/{app}", data=body, method="POST",
                headers={"Content-Type": "text/plain; charset=UTF-8"},
            )
            with urllib.request.urlopen(req, timeout=6) as r:
                status = r.status
        except urllib.error.HTTPError as e:
            status = e.code
        except (urllib.error.URLError, socket.timeout, OSError):
            status = 0
        if status == 201:
            return 201, port
        if status and not last:
            last = status
    return last, None


def cmd_browse(args) -> int:
    """Open the OpenAmer Browser on the TV, optionally with a page already loaded.

    The browser page accepts ``?u=<encoded url>`` and navigates there itself, so
    one API call both starts the shell and loads the destination. Only http(s)
    is accepted; a bare host becomes https.
    """
    h = resolve_host(args.host)
    target = BROWSER_APP
    if args.url:
        url = args.url.strip()
        if not re.match(r"^https?://", url, re.IGNORECASE):
            url = "https://" + url
        target = f"{BROWSER_APP}?u={urllib.parse.quote(url, safe='')}"
    status, _ = _request(
        h, "/6/activities/browser",
        {"intent": {"action": "android.intent.action.VIEW", "uri": target}},
    )
    ok = status == 200
    print(f"browser -> {target}  (http {status})")
    if not ok:
        print("  (die browser-Activity antwortet nicht mit 200 — siehe MISMATCH-Hinweis)")
    return 0 if ok else 1


def cmd_app(args) -> int:
    """Start an installed app (DIAL). 201 = started, 404 = not installed."""
    h = resolve_host(args.host)
    status, port = _dial_launch(h, args.name)
    if status == 201:
        print(f"{args.name}: gestartet (DIAL :{port}, 201)")
        return 0
    if status == 404:
        print(f"{args.name}: nicht installiert (404) — auf diesem Gerät "
              f"konnten nur Netflix und YouTube gestartet werden")
        return 1
    print(f"{args.name}: keine Antwort von der DIAL-Schnittstelle (status {status})")
    return 1


def cmd_apps(args) -> int:
    """Probe which apps are installed, by DIAL launch (201 = installed)."""
    h = resolve_host(args.host)
    found = []
    for app in DIAL_CANDIDATES:
        status, port = _dial_launch(h, app)
        if status == 201:
            found.append((app, port))
    if not found:
        print("keine der geprüften Apps ist installiert")
        return 1
    print("installiert und startbar:")
    for app, port in found:
        print(f"  {app:<16} DIAL :{port}")
    print(f"\ngeprüft: {len(DIAL_CANDIDATES)} Namen, {len(found)} Treffer")
    return 0


def cmd_power(args) -> int:
    h = resolve_host(args.host)
    if args.state == "status":
        status, body = _request(h, "/6/powerstate")
        print(body)
        return 0
    key = "Standby" if args.state == "off" else "PowerOn"
    status, body = _request(h, "/6/input/key", {"key": key})
    print(f"power {args.state} -> http {status}")
    return 0 if status == 200 else 1


def cmd_screen(args) -> int:
    """Read or set the panel state.

    ``GET /6/screenstate`` answers ``{"screenstate": "On"}``. Turning the panel
    off is **not** standby: audio and playback keep running, only the picture
    goes dark. The write is verified by reading the state back — a ``200`` from
    this API has proven meaningless often enough (see ``cmd_volume``).
    """
    h = resolve_host(args.host)
    if args.state == "status":
        status, body = _request(h, "/6/screenstate")
        if status != 200:
            print(f"screenstatus -> http {status} (not published by this model)")
            return 1
        print(json.dumps(body, ensure_ascii=False) if isinstance(body, dict) else body)
        return 0
    want = "On" if args.state == "on" else "Off"
    status, _ = _request(h, "/6/screenstate", {"screenstate": want})
    _, after = _request(h, "/6/screenstate")
    got = after.get("screenstate") if isinstance(after, dict) else "?"
    ok = status == 200 and got == want
    print(f"screen {args.state} -> http {status}, screenstate={got} "
          f"{'OK' if ok else 'MISMATCH'}")
    return 0 if ok else 1


def cmd_context(args) -> int:
    """Read ``/6/context`` — the only endpoint that could report what is shown.

    Measured on 58PUS6203/12: it answers, but every field stays ``"NA"`` even
    with Netflix in the foreground. So this is **not** a screen readback on
    this model; it is exposed here so the next model can be checked in one
    command instead of a code change.
    """
    h = resolve_host(args.host)
    status, body = _request(h, "/6/context")
    if status != 200:
        print(f"context -> http {status}")
        return 1
    if not isinstance(body, dict):
        print(body)
        return 0
    print(json.dumps(body, ensure_ascii=False))
    blind = all(str(v).strip().upper() == "NA"
                for k, v in body.items() if k.lower() != "recording")
    if blind:
        print("  (every field NA: this model does not report the screen)")
    return 0


# ----------------------------------------------------------------------------- cli

def add_tv_subcommands(p: argparse.ArgumentParser) -> None:
    """Attach the tv sub-actions to an existing parser.

    Shared by the standalone script entry point and ``openamer tv`` so both
    expose exactly the same surface from one definition.
    """
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("discover", help="Find TVs via SSDP").set_defaults(func=cmd_discover)
    sub.add_parser("info", help="Model, power, volume, capabilities").set_defaults(func=cmd_info)

    k = sub.add_parser("key", help=f"Send a remote key ({', '.join(sorted(KEYS))})")
    k.add_argument("key")
    k.set_defaults(func=cmd_key)

    v = sub.add_parser("volume", help="Read or set volume")
    v.add_argument("level", nargs="?", type=int)
    v.set_defaults(func=cmd_volume)

    m = sub.add_parser("mute", help="Mute (or --off to unmute)")
    m.add_argument("--off", action="store_true")
    m.set_defaults(func=cmd_mute)

    o = sub.add_parser("open", help="Open a URL in the TV browser")
    o.add_argument("url")
    o.set_defaults(func=cmd_open)

    br = sub.add_parser("browse", help="Open the OpenAmer Browser on the TV")
    br.add_argument("url", nargs="?", help="page to load immediately")
    br.set_defaults(func=cmd_browse)

    a = sub.add_parser("activity", help="Start a TV activity (only tv|browser exist)")
    a.add_argument("name", choices=["tv", "browser"])
    a.set_defaults(func=cmd_activity)

    ap = sub.add_parser("app", help="Start an installed app (Netflix, YouTube)")
    ap.add_argument("name")
    ap.set_defaults(func=cmd_app)

    sub.add_parser("apps", help="Probe which apps are installed").set_defaults(func=cmd_apps)

    pw = sub.add_parser("power", help="on | off | status")
    pw.add_argument("state", choices=["on", "off", "status"])
    pw.set_defaults(func=cmd_power)

    sc = sub.add_parser("screen", help="on | off | status — panel only, playback keeps running")
    sc.add_argument("state", nargs="?", choices=["on", "off", "status"], default="status")
    sc.set_defaults(func=cmd_screen)

    sub.add_parser("context", help="What the TV reports as its current context").set_defaults(
        func=cmd_context)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Control a Philips TV on the local network.")
    p.add_argument("--host", help="TV IP (default: cached / auto-discover)")
    add_tv_subcommands(p)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
